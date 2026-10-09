"""The worker's bootstrap (T-4.4): what it runs, how often it polls (D-091),
what it refuses to start without, what it logs, and a job queued by the API's
own code run end to end by a real ARQ worker, on this run's Redis and database.
"""

from __future__ import annotations

import asyncio
import contextlib
import copy
import io
import logging
import re
import shutil
import tomllib
import uuid
from collections.abc import AsyncIterator, MutableMapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from arq.constants import (
    default_queue_name,
    in_progress_key_prefix,
    job_key_prefix,
    result_key_prefix,
    retry_key_prefix,
)
from arq.worker import Worker, create_worker
from PIL import Image
from redis.asyncio import Redis
from sqlalchemy import select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core import clock as core_clock
from app.core.config import Settings
from app.core.db import build_engine
from app.core.enums import OnboardingStep, PhotoKind, ReviewStatus
from app.core.providers import FakeProviders
from app.core.queue import (
    BLUR_PHOTO,
    DELETE_FILES,
    ERASE_ACCOUNTS,
    EXPIRE_EXPORT,
    EXPORT_DATA,
    MATCH_PHOTO,
    MODERATE_PHOTO,
    VERIFY_SELFIE,
    WATERMARK_ALBUM,
    ArqQueue,
)
from app.core.redis import build_redis
from app.modules.photos import service as photos_service
from app.modules.photos.models import Photo
from app.modules.users.models import User
from app.modules.verification import service as verification_service
from app.modules.verification.models import Verification
from app.workers import main as worker
from tests.committed import fresh_man
from tests.conftest import CapturedLogs, make_test_settings
from tests.infra import TEST_DATABASE_URL, TEST_REDIS_URL, require_models
from tests.keys import random_keys, vapid_settings
from tests.modules.verification.test_race import forget_photos

PUBLIC, PRIVATE = "velora-public", "velora-private"


@pytest.fixture
async def arq_redis(test_redis: Redis) -> AsyncIterator[Redis]:
    """This run's Redis (P-55), with ARQ's queue and job keys cleared before
    and after, so a burst worker runs only what its test queued."""

    async def clear() -> None:
        await test_redis.delete(default_queue_name)
        for prefix in (
            job_key_prefix,
            result_key_prefix,
            retry_key_prefix,
            in_progress_key_prefix,
        ):
            async for key in test_redis.scan_iter(match=f"{prefix}*"):
                await test_redis.delete(key)

    await clear()
    try:
        yield test_redis
    finally:
        await clear()


def _settings(**values: Any) -> Settings:
    return make_test_settings().model_copy(update=values)


# --- What it runs, and how often (D-091) ---------------------------------------------


def test_it_runs_exactly_the_jobs_the_api_queues() -> None:
    jobs = {job.name: job for job in worker.JOBS}

    assert set(jobs) == {
        MODERATE_PHOTO,
        DELETE_FILES,
        VERIFY_SELFIE,
        MATCH_PHOTO,
        EXPORT_DATA,
        EXPIRE_EXPORT,
        BLUR_PHOTO,
        WATERMARK_ALBUM,
    }
    assert jobs[MODERATE_PHOTO].max_tries == 3
    assert jobs[BLUR_PHOTO].max_tries == 3
    assert jobs[VERIFY_SELFIE].max_tries == 5
    assert jobs[MATCH_PHOTO].max_tries == 3
    assert jobs[EXPORT_DATA].max_tries == 3
    assert jobs[EXPIRE_EXPORT].max_tries == 4
    assert jobs[WATERMARK_ALBUM].max_tries == 3


def test_the_erasure_runs_daily_at_0330_ist() -> None:
    """D-500: 22:00 UTC, which is 03:30 IST, in UTC whatever the machine's
    clock (`WorkerSettings.timezone`, D-483), so each deleted account is erased
    between day 29 and day 30."""
    built = create_worker(
        worker.WorkerSettings,  # type: ignore[arg-type]
        **worker.worker_options(make_test_settings()),
    )

    [erase] = [job for job in built.cron_jobs if job.name == ERASE_ACCOUNTS]
    # A copy: the module's own CronJob carries its next run between tests.
    job = copy.copy(erase)
    assert (job.hour, job.minute, job.second) == (22, 0, 0)
    assert job.unique and job.max_tries == 1 and job.run_at_startup is False
    assert built.timezone is UTC
    job.calculate_next(datetime(2026, 10, 8, 12, 0, tzinfo=UTC))
    assert job.next_run is not None
    assert job.next_run.replace(microsecond=0).astimezone(core_clock.IST) == datetime(
        2026, 10, 9, 3, 30, tzinfo=core_clock.IST
    )


async def test_the_erasure_costs_no_redis_command_until_it_is_due() -> None:
    """D-091's sum holds: ARQ checks its crons at every poll without Redis.
    With no pool at all, checks before 22:00 UTC pass; the one at 22:00
    reaches for the pool, the single enqueue a day the job costs."""
    built = create_worker(
        worker.WorkerSettings,  # type: ignore[arg-type]
        **worker.worker_options(make_test_settings()),
    )
    built.cron_jobs = [copy.copy(job) for job in built.cron_jobs]
    built._pool = None  # any Redis command now raises
    before = datetime(2026, 10, 8, 21, 30, tzinfo=UTC)
    await built.run_cron(before, delay=10)  # works out the next runs only
    await built.run_cron(before + timedelta(minutes=20), delay=10)

    with pytest.raises(AttributeError):
        await built.run_cron(before + timedelta(minutes=30), delay=10)


def test_it_polls_every_10_seconds_which_is_d091s_sum() -> None:
    """D-091: one look at the queue a poll, a health key once an hour (two
    commands), over a 30-day month: 260,640 commands, 52% of Upstash Free's
    500K. Changing either number changes the sum: redo it first."""
    settings = make_test_settings()
    assert settings.WORKER_POLL_DELAY_S == 10

    built = create_worker(
        worker.WorkerSettings,  # type: ignore[arg-type]
        **worker.worker_options(settings),
    )

    month_s = 30 * 24 * 3600
    polls = month_s / built.poll_delay_s
    health = 2 * month_s / built.health_check_interval
    assert polls + health == 260_640
    assert (polls + health) / 500_000 < 0.53
    assert built.max_jobs == worker.MAX_JOBS


def test_the_poll_delay_is_a_setting() -> None:
    built = create_worker(
        worker.WorkerSettings,  # type: ignore[arg-type]
        **worker.worker_options(_settings(WORKER_POLL_DELAY_S=2.5)),
    )

    assert built.poll_delay_s == 2.5


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "rediss://default:a-password@redis.example:6380/0",
            ("redis.example", 6380, 0, "a-password", True),
        ),
        ("redis://127.0.0.1:6379/3", ("127.0.0.1", 6379, 3, None, False)),
    ],
)
def test_it_reaches_the_apis_redis_with_tls_where_the_url_says(
    url: str, expected: tuple[Any, ...]
) -> None:
    redis = worker.redis_settings(_settings(REDIS_URL=url))

    assert (redis.host, redis.port, redis.database, redis.password, redis.ssl) == (
        expected
    )


# --- What it refuses to start without --------------------------------------------------


@pytest.mark.parametrize(
    ("keys", "named"),
    [
        ({}, "SIGHTENGINE_API_USER, SIGHTENGINE_API_SECRET"),
        ({"SIGHTENGINE_API_USER": "u"}, "SIGHTENGINE_API_SECRET:"),
        ({"SIGHTENGINE_API_SECRET": "s"}, "SIGHTENGINE_API_USER:"),
    ],
)
def test_sightengine_without_its_keys_is_refused_naming_them(
    keys: dict[str, str], named: str
) -> None:
    settings = _settings(MODERATION_PROVIDER="sightengine", **keys)

    with pytest.raises(worker.WorkerMisconfigured, match=named):
        worker.refuse_unless_ready(settings)


@pytest.mark.parametrize(
    "values",
    [
        {"MODERATION_PROVIDER": "fake"},
        {
            "MODERATION_PROVIDER": "sightengine",
            "SIGHTENGINE_API_USER": "u",
            "SIGHTENGINE_API_SECRET": "s",
        },
    ],
)
def test_with_what_it_needs_it_starts(values: dict[str, str]) -> None:
    worker.refuse_unless_ready(_settings(**values))


@pytest.mark.parametrize(
    ("damage", "named"),
    [
        ("missing", "face_recognition_sface_2021dec.onnx is missing from"),
        ("altered", "face_recognition_sface_2021dec.onnx is not D-088's SHA-256"),
        ("cut short", "face_recognition_sface_2021dec.onnx is 1024 bytes, not"),
    ],
)
def test_sface_without_d088s_exact_models_is_refused_naming_them(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, damage: str, named: str
) -> None:
    """D-088: OpenCV parses only the two files whose SHA-256 D-088 records.
    A model missing, altered (same size, one byte changed) or cut short stops
    the worker before any selfie is compared, as Fly's release command runs
    `--check` before a deploy."""
    from app.core import facemodels

    require_models()
    shutil.copy(facemodels.MODEL_DIR / facemodels.DETECTOR.name, tmp_path)
    recognizer = tmp_path / facemodels.RECOGNIZER.name
    if damage != "missing":
        data = bytearray(
            (facemodels.MODEL_DIR / facemodels.RECOGNIZER.name).read_bytes()
        )
        if damage == "altered":
            data[len(data) // 2] ^= 0xFF
        else:
            data = data[:1024]
        recognizer.write_bytes(bytes(data))
    monkeypatch.setattr(facemodels, "MODEL_DIR", tmp_path)

    with pytest.raises(worker.WorkerMisconfigured, match=re.escape(named)):
        worker.refuse_unless_ready(_settings(FACEMATCH_PROVIDER="sface"))
    worker.refuse_unless_ready(_settings(FACEMATCH_PROVIDER="fake"))


def test_check_says_why_it_wouldnt_start_and_never_echoes_a_value(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        worker,
        "get_settings",
        lambda: _settings(
            MODERATION_PROVIDER="sightengine", SIGHTENGINE_API_USER="who-the-user-is"
        ),
    )

    assert worker.main(["--check"]) == 2
    err = capsys.readouterr().err
    assert (
        "worker: refused. MODERATION_PROVIDER=sightengine needs SIGHTENGINE_API_SECRET"
        in err
    )
    assert "who-the-user-is" not in err


def test_check_passes_when_ready(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(worker, "get_settings", make_test_settings)

    assert worker.main(["--check"]) == 0
    assert capsys.readouterr().err == "worker: settings ready.\n"


# --- Running jobs, for real, through ARQ -------------------------------------------------


def _jpeg() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (900, 700), "purple").save(out, "JPEG")
    return out.getvalue()


async def _run_burst(fake: FakeProviders) -> Worker:
    """A real ARQ worker, built as `WorkerSettings` builds it, on the test
    settings and the test's fakes: it runs what's queued, then stops."""
    settings = make_test_settings()

    async def startup(ctx: MutableMapping[str, Any]) -> None:
        await worker.open_resources(ctx, settings, fake.as_providers())

    burst = Worker(
        functions=worker.JOBS,
        redis_settings=worker.redis_settings(settings),
        on_startup=startup,
        on_shutdown=worker.shutdown,
        burst=True,
        poll_delay=0.05,
        max_jobs=worker.MAX_JOBS,
        handle_signals=False,
    )
    try:
        await burst.main()
    finally:
        await burst.close()
    return burst


async def test_a_photo_the_api_completes_is_moderated_by_the_worker_through_arq(
    test_engine: AsyncEngine, arq_redis: Redis
) -> None:
    """The chain staging's demo rests on: `complete` queues the job with the
    API's own queue; a worker started as the real one is picks it up from
    Redis; the photo ends approved and published. Committed, on a fresh man."""
    fake = FakeProviders()
    man = await fresh_man(test_engine)
    photo_id = uuid.uuid4()
    async with AsyncSession(test_engine, expire_on_commit=False) as session:
        async with session.begin():
            await session.execute(
                update(User)
                .where(User.id == man)
                .values(onboarding_step=OnboardingStep.PHOTOS)
            )
            session.add(
                Photo(
                    id=photo_id,
                    user_id=man,
                    kind=PhotoKind.PUBLIC,
                    position=0,
                    raw_key=f"raw/{man}/{photo_id}",
                )
            )
        await fake.storage.put_bytes(
            PRIVATE, f"raw/{man}/{photo_id}", _jpeg(), "image/jpeg"
        )
        user = await session.get(User, man)
        assert user is not None
        await session.commit()
        queued = await photos_service.complete(
            session,
            user,
            photo_id,
            storage=fake.storage,
            queue=ArqQueue(arq_redis),
            settings=make_test_settings(),
        )
    assert queued.status is ReviewStatus.PENDING
    assert await arq_redis.zrange(default_queue_name, 0, -1) == [
        f"moderate_photo:{photo_id}".encode()
    ]

    ran = await _run_burst(fake)

    # Moderation, then the blur its approval queued (T-6.7, D-543).
    assert (ran.jobs_complete, ran.jobs_failed, ran.jobs_retried) == (2, 0, 0)
    async with AsyncSession(test_engine) as session:
        photo = await session.scalar(select(Photo).where(Photo.id == photo_id))
    assert photo is not None
    assert (photo.status, photo.public_key) == (
        ReviewStatus.APPROVED,
        f"p/{photo_id}.jpg",
    )
    assert (PUBLIC, f"p/{photo_id}.jpg") in fake.storage.objects
    assert photo.blur_key is not None
    assert (PUBLIC, photo.blur_key) in fake.storage.objects
    # Taken back: the blur migration's downgrade refuses while any photo has
    # one, and `test_migrations` downgrades this database.
    async with AsyncSession(test_engine) as session, session.begin():
        await session.execute(
            update(Photo).where(Photo.id == photo_id).values(blur_key=None)
        )


async def test_a_submitted_selfie_is_decided_by_the_wake_and_the_job_finds_it_done(
    test_engine: AsyncEngine, arq_redis: Redis
) -> None:
    """D-261's chain, on this run's Redis and database: `submit` commits,
    queues the job and publishes the wake; the listener the worker starts
    decides it at once, long before ARQ's next look; the queued job, run
    after, finds it decided and does nothing. Committed, on a fresh man."""
    fake = FakeProviders()
    settings = make_test_settings()
    man = await fresh_man(test_engine)
    photo_id, selfie_id = uuid.uuid4(), uuid.uuid4()
    async with AsyncSession(test_engine, expire_on_commit=False) as session:
        async with session.begin():
            await session.execute(
                update(User)
                .where(User.id == man)
                .values(onboarding_step=OnboardingStep.SELFIE)
            )
            session.add_all(
                [
                    # His face photo (T-4.12), approved, in the private bucket.
                    Photo(
                        id=photo_id,
                        user_id=man,
                        kind=PhotoKind.VERIFICATION,
                        raw_key=f"raw/{man}/{photo_id}",
                        status=ReviewStatus.APPROVED,
                        moderation={"faces": 1},
                    ),
                    Photo(
                        id=selfie_id,
                        user_id=man,
                        kind=PhotoKind.SELFIE,
                        raw_key=f"raw/{man}/{selfie_id}",
                    ),
                ]
            )
        await fake.storage.put_bytes(
            PRIVATE, f"raw/{man}/{photo_id}", _jpeg(), "image/jpeg"
        )
        await fake.storage.put_bytes(
            PRIVATE, f"raw/{man}/{selfie_id}", _jpeg(), "image/jpeg"
        )
        user = await session.get(User, man)
        assert user is not None
        await session.commit()
        started = await verification_service.start(session, user)

    ctx: dict[str, Any] = {"redis": arq_redis}
    await worker.open_resources(ctx, settings, fake.as_providers())
    listener = worker.listen_for_wakes(ctx, settings)
    listening = asyncio.create_task(listener.run())
    try:
        async with asyncio.timeout(5):
            await listener.subscribed.wait()
        async with AsyncSession(test_engine, expire_on_commit=False) as session:
            user = await session.get(User, man)
            assert user is not None
            await session.commit()
            sent = await verification_service.submit(
                session,
                user,
                started.id,
                selfie_id,
                storage=fake.storage,
                queue=ArqQueue(arq_redis),
                settings=settings,
            )
        assert (sent.status, sent.submitted) == (ReviewStatus.PENDING, True)

        decided = None
        async with asyncio.timeout(5):
            while decided is None:
                async with AsyncSession(test_engine) as session:
                    row = await session.get(Verification, started.id)
                    assert row is not None
                    if row.status is not ReviewStatus.PENDING:
                        decided = row.status
                        selfie = await session.get(Photo, selfie_id)
                await asyncio.sleep(0.05)
    finally:
        listening.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await listening
        await worker.shutdown(ctx)

    assert decided is ReviewStatus.APPROVED
    assert selfie is not None and selfie.moderation is not None
    assert selfie.moderation["decided_by"] == "wake"
    # The queued job is still there, the path sure to run; run, it finds it done.
    assert await arq_redis.zrange(default_queue_name, 0, -1) == [
        f"verify_selfie:{started.id}".encode()
    ]
    ran = await _run_burst(fake)
    assert (ran.jobs_complete, ran.jobs_failed) == (1, 0)
    async with AsyncSession(test_engine) as session:
        selfie = await session.get(Photo, selfie_id)
    assert selfie is not None and selfie.moderation is not None
    assert selfie.moderation["decided_by"] == "wake"
    await forget_photos(test_engine, man)


async def test_arq_never_logs_a_jobs_arguments_which_can_be_storage_keys(
    test_engine: AsyncEngine,
    arq_redis: Redis,
    caplog: pytest.LogCaptureFixture,
    captured_logs: CapturedLogs,
) -> None:
    """Rule 15: `delete_files` carries the keys it deletes, and ARQ writes a
    job's arguments into the line it logs as the job starts. Run for real."""
    arq_logger = logging.getLogger("arq.worker")
    filters = list(arq_logger.filters)
    caplog.set_level(logging.INFO, logger="arq.worker")
    worker.hide_job_arguments()
    fake = FakeProviders()
    gone = uuid.uuid4()  # no such user: the refusal committed
    key = f"raw/{gone}/{uuid.uuid4()}"
    await fake.storage.put_bytes(PRIVATE, key, b"photo", "image/jpeg")
    await ArqQueue(arq_redis).enqueue(
        DELETE_FILES,
        user_id=str(gone),
        banned_id=str(uuid.uuid4()),
        objects=[[PRIVATE, key]],
    )
    try:
        ran = await _run_burst(fake)
    finally:
        arq_logger.filters[:] = filters

    assert (ran.jobs_complete, ran.jobs_failed) == (1, 0)
    assert fake.storage.objects == {}
    started = [r.getMessage() for r in caplog.records if "→" in r.getMessage()]
    assert len(started) == 1 and "delete_files(…)" in started[0]
    assert "raw/" not in caplog.text
    assert "raw/" not in captured_logs.text
    captured_logs.assert_listening()


def test_the_started_line_keeps_the_jobs_name_and_timing() -> None:
    record = logging.LogRecord(
        "arq.worker",
        logging.INFO,
        __file__,
        1,
        "%6.2fs → %s(%s)%s",
        (0.5, "abc:delete_files", "objects=[['velora-private', 'raw/x/y']]", " try=2"),
        None,
    )

    assert worker.HideJobArguments().filter(record)
    assert record.getMessage() == "  0.50s → abc:delete_files(…) try=2"


# --- Its Fly config, and its engine ------------------------------------------------------

FLY = Path(__file__).resolve().parents[3] / "infra"
# The API's settings the worker has no use for: they shape HTTP responses.
API_ONLY = {"CORS_ORIGINS", "COOKIE_DOMAIN"}
# Each app's own pool, budgeted together in infra/STAGING.md.
OWN = {"DB_POOL_SIZE", "DB_MAX_OVERFLOW", "WORKER_POLL_DELAY_S"}


def _env(name: str) -> dict[str, str]:
    with (FLY / name).open("rb") as f:
        env: dict[str, str] = tomllib.load(f)["env"]
    return env


def test_the_worker_reads_the_same_settings_as_the_api_on_staging() -> None:
    """One `Settings` for both apps: a bucket, a CDN or a provider changed on
    the API alone would send the worker's photos somewhere else."""
    api, worker_env = _env("fly.api.toml"), _env("fly.worker.toml")

    assert set(api) - API_ONLY - OWN == set(worker_env) - OWN
    assert {k: v for k, v in worker_env.items() if k not in OWN} == {
        k: v for k, v in api.items() if k not in API_ONLY | OWN
    }
    assert worker_env["WORKER_POLL_DELAY_S"] == "10"  # D-091


def test_the_workers_fly_settings_start_as_staging_with_its_secrets() -> None:
    # fly.worker.toml says FACEMATCH_PROVIDER=sface, so the worker's check reads
    # the models (D-088): skipped without `make models` locally, failed in CI.
    require_models()
    values = {
        "DATABASE_URL": "postgresql+asyncpg://app:x@db.example:5432/postgres",
        "REDIS_URL": "rediss://default:x@redis.example:6379/0",
        **random_keys(),
        "R2_ACCESS_KEY_ID": "staging-token-id",
        "R2_SECRET_ACCESS_KEY": "staging-token-secret",
        "SIGHTENGINE_API_USER": "staging-user",
        "SIGHTENGINE_API_SECRET": "staging-secret",
        # The VAPID pair: two Fly secrets (T-9.4, D-856).
        **vapid_settings(),
        **_env("fly.worker.toml"),
    }

    settings = Settings(_env_file=None, **values)  # type: ignore[arg-type]

    worker.refuse_unless_ready(settings)
    assert (settings.ENV, settings.DB_POOL_SIZE + settings.DB_MAX_OVERFLOW) == (
        "staging",
        3,
    )


async def test_the_workers_database_errors_carry_no_values() -> None:
    """Rule 15: a failed query's error names its statement, never the values
    it carried, which can be storage keys. The plain engine's does: the check
    can see what it says is absent."""
    key = f"raw/{uuid.uuid4()}/{uuid.uuid4()}"
    plain = build_engine(TEST_DATABASE_URL)
    ctx: dict[str, Any] = {"redis": build_redis(TEST_REDIS_URL)}
    await worker.open_resources(
        ctx, make_test_settings(), FakeProviders().as_providers()
    )
    try:
        errors = []
        for engine in (plain, ctx["engine"]):
            async with AsyncSession(engine) as session:
                with pytest.raises(DBAPIError) as failure:
                    await session.execute(
                        text("select cast(:key as integer)"), {"key": key}
                    )
                errors.append(str(failure.value))
    finally:
        await worker.shutdown(ctx)
        await plain.dispose()
        await ctx["redis"].aclose()

    assert key in errors[0]
    assert key not in errors[1]
