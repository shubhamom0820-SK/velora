"""Storage (T-4.1): `S3Storage` against the local S3 (SeaweedFS, D-086), as
`make infra-up` runs it and CI starts it; the endpoint gate; and the probe that
proves R2 where it runs.

The local S3 is shared by every run on the machine (P-55 gives it no slot), so
each test writes under a prefix of its own and deletes what it wrote; no
assertion looks at anything else in a bucket. R2 itself is proved by the probe
inside staging's machine (infra/STAGING.md §3), never by a local server passing.
"""

from __future__ import annotations

import asyncio
import io
import uuid
from collections.abc import AsyncIterator

import httpx
import pytest
from dotenv import dotenv_values

from app.core.config import Settings
from app.core.providers.storage import (
    FakeStorage,
    ObjectInfo,
    ObjectNotFound,
    S3Storage,
    storage_endpoint,
)
from app.tools import storage_probe
from app.tools.storage_probe import ProbeRefused, probe
from tests.conftest import make_test_settings
from tests.infra import (
    API_DIR,
    LOCAL_S3_URL,
    S3_DOWN_REASON,
    S3_UP,
    in_ci,
    infra_policy,
)
from tests.keys import r2_settings

PUBLIC, PRIVATE = "velora-public", "velora-private"
# A name nobody has listed anywhere, in any allowlist or test: a blacklist that
# names today's environments waves it through; an allowlist refuses it (rule 16).
UNNAMED_ENV = "env-nobody-has-named-2031"


def local_s3_settings() -> Settings:
    """Local settings for the local S3, as `api/.env.example` has them."""
    return make_test_settings().model_copy(
        update={
            "STORAGE_PROVIDER": "s3",
            "R2_ENDPOINT_URL": LOCAL_S3_URL,
            "R2_ACCESS_KEY_ID": "velora-local",
            "R2_SECRET_ACCESS_KEY": "velora-local-secret",
            "R2_BUCKET_PUBLIC": PUBLIC,
            "R2_BUCKET_PRIVATE": PRIVATE,
            "PUBLIC_CDN_URL": f"{LOCAL_S3_URL}/{PUBLIC}",
        }
    )


@pytest.fixture
async def storage() -> AsyncIterator[S3Storage]:
    decision = infra_policy(reachable=S3_UP, ci=in_ci())
    if decision == "skip":
        pytest.skip(S3_DOWN_REASON)
    if decision == "fail":
        pytest.fail(
            f"CI requires the local S3, and it is not reachable ({S3_DOWN_REASON})."
        )
    s3 = S3Storage(local_s3_settings())
    try:
        yield s3
    finally:
        await s3.aclose()


@pytest.fixture
def prefix() -> str:
    return f"test/{uuid.uuid4()}"


@pytest.fixture
async def http() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(timeout=10) as client:
        yield client


async def _cleanup(storage: S3Storage, *objects: tuple[str, str]) -> None:
    for bucket, key in objects:
        await storage.delete(bucket, key)


# --- Presigned URLs: what the browser gets ------------------------------------------


async def test_a_presigned_put_stores_exactly_what_the_browser_sends(
    storage: S3Storage, prefix: str, http: httpx.AsyncClient
) -> None:
    key = f"{prefix}/upload.jpg"
    try:
        signed = await storage.presign_put(PRIVATE, key, "image/jpeg", 8 * 1024 * 1024)
        response = await http.put(
            signed.url, content=b"jpeg bytes", headers=dict(signed.headers)
        )

        assert response.status_code == 200
        assert signed.headers == {"Content-Type": "image/jpeg"}
        assert await storage.head(PRIVATE, key) == ObjectInfo(10, "image/jpeg")
    finally:
        await _cleanup(storage, (PRIVATE, key))


async def test_a_presigned_put_refuses_another_content_type(
    storage: S3Storage, prefix: str, http: httpx.AsyncClient
) -> None:
    """The type is signed: a URL issued for a JPEG can't store a page of HTML."""
    key = f"{prefix}/upload.jpg"
    try:
        signed = await storage.presign_put(PRIVATE, key, "image/jpeg", 1024)
        response = await http.put(
            signed.url, content=b"<script>", headers={"Content-Type": "text/html"}
        )

        assert response.status_code == 403
        with pytest.raises(ObjectNotFound):
            await storage.head(PRIVATE, key)
    finally:
        await _cleanup(storage, (PRIVATE, key))


async def test_an_expired_presigned_put_is_refused(
    storage: S3Storage, prefix: str, http: httpx.AsyncClient
) -> None:
    key = f"{prefix}/late.jpg"
    try:
        signed = await storage.presign_put(PRIVATE, key, "image/jpeg", 1024, ttl=1)
        await asyncio.sleep(2)
        response = await http.put(
            signed.url, content=b"x", headers=dict(signed.headers)
        )

        assert response.status_code == 403
        with pytest.raises(ObjectNotFound):
            await storage.head(PRIVATE, key)
    finally:
        await _cleanup(storage, (PRIVATE, key))


async def test_a_presigned_get_returns_the_bytes(
    storage: S3Storage, prefix: str, http: httpx.AsyncClient
) -> None:
    key = f"{prefix}/selfie.jpg"
    try:
        await storage.put_bytes(PRIVATE, key, b"private bytes", "image/jpeg")

        response = await http.get(await storage.presign_get(PRIVATE, key))

        assert (response.status_code, response.content) == (200, b"private bytes")
        unsigned = await http.get(f"{LOCAL_S3_URL}/{PRIVATE}/{key}")
        assert unsigned.status_code == 403  # the private bucket answers no one unsigned
    finally:
        await _cleanup(storage, (PRIVATE, key))


# --- The server's own reads and writes ------------------------------------------------


async def test_bytes_go_in_and_come_back_with_their_type(
    storage: S3Storage, prefix: str
) -> None:
    key = f"{prefix}/photo.jpg"
    try:
        await storage.put_bytes(PRIVATE, key, b"\xff\xd8 re-encoded", "image/jpeg")

        assert await storage.get_bytes(PRIVATE, key) == b"\xff\xd8 re-encoded"
        assert await storage.head(PRIVATE, key) == ObjectInfo(13, "image/jpeg")
    finally:
        await _cleanup(storage, (PRIVATE, key))


async def test_copy_crosses_buckets_and_delete_removes(
    storage: S3Storage, prefix: str
) -> None:
    src, dst = f"{prefix}/raw", f"{prefix}/p.jpg"
    try:
        await storage.put_bytes(PRIVATE, src, b"approved", "image/jpeg")

        await storage.copy(PRIVATE, src, PUBLIC, dst)
        assert await storage.get_bytes(PUBLIC, dst) == b"approved"

        await storage.delete(PUBLIC, dst)
        with pytest.raises(ObjectNotFound):
            await storage.get_bytes(PUBLIC, dst)
    finally:
        await _cleanup(storage, (PRIVATE, src), (PUBLIC, dst))


async def test_a_missing_object_is_object_not_found(
    storage: S3Storage, prefix: str
) -> None:
    missing = f"{prefix}/never-written"

    with pytest.raises(ObjectNotFound):
        await storage.get_bytes(PRIVATE, missing)
    with pytest.raises(ObjectNotFound):
        await storage.head(PRIVATE, missing)
    with pytest.raises(ObjectNotFound):
        await storage.copy(PRIVATE, missing, PUBLIC, f"{prefix}/copy")
    await storage.delete(PRIVATE, missing)  # not an error


async def test_one_client_is_kept_and_closing_twice_is_safe(
    storage: S3Storage, prefix: str
) -> None:
    key = f"{prefix}/x"
    try:
        await storage.put_bytes(PRIVATE, key, b"1", "text/plain")
        first = storage._client
        await storage.head(PRIVATE, key)
        assert storage._client is first is not None

        await storage.aclose()
        await storage.aclose()
        assert storage._client is None
        # Reopened on next use.
        assert (await storage.head(PRIVATE, key)).size == 1
    finally:
        await _cleanup(storage, (PRIVATE, key))


async def test_the_fake_reports_size_and_type_too() -> None:
    fake = FakeStorage()
    await fake.put_bytes(PRIVATE, "k", b"abc", "image/png")

    assert await fake.head(PRIVATE, "k") == ObjectInfo(3, "image/png")
    with pytest.raises(ObjectNotFound):
        await fake.head(PRIVATE, "missing")


def test_the_example_env_is_the_local_s3_as_these_tests_use_it() -> None:
    """`api/.env.example` stores files in the local S3, so `make dev` and `make seed`
    write real objects; and as a whole it starts, s3 settings complete."""
    example = dotenv_values(API_DIR / ".env.example")
    expected = local_s3_settings()

    for name in (
        "STORAGE_PROVIDER",
        "R2_ENDPOINT_URL",
        "R2_ACCESS_KEY_ID",
        "R2_SECRET_ACCESS_KEY",
        "R2_BUCKET_PUBLIC",
        "R2_BUCKET_PRIVATE",
        "PUBLIC_CDN_URL",
    ):
        assert example[name] == getattr(expected, name), name
    started = Settings(_env_file=API_DIR / ".env.example")
    assert storage_endpoint(started) == LOCAL_S3_URL


# --- The endpoint: R2's own, except locally (rule 16) -----------------------------


def test_locally_the_endpoint_may_be_the_local_s3() -> None:
    assert storage_endpoint(local_s3_settings()) == LOCAL_S3_URL


@pytest.mark.parametrize("env", ["staging", "production", "preview", UNNAMED_ENV])
def test_anywhere_else_the_endpoint_is_r2s_own(env: str) -> None:
    """Even for settings `Settings` never checked (copied past validation): the
    override is honoured only where the allowlist names."""
    r2 = r2_settings()
    settings = local_s3_settings().model_copy(
        update={"ENV": env, "R2_ACCOUNT_ID": r2["R2_ACCOUNT_ID"]}
    )

    assert storage_endpoint(settings) == (
        f"https://{r2['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com"
    )


# --- The probe (D14): what proves R2 on staging -----------------------------------------


async def test_the_probe_passes_every_step_against_the_local_s3(
    storage: S3Storage, http: httpx.AsyncClient
) -> None:
    """The local public bucket allows anonymous reads (`infra/s3/s3.json`), so even
    the CDN step runs here."""
    report = await probe(local_s3_settings(), storage, http)

    assert not report.failed, report.lines
    assert all(line.startswith("ok") for line in report.lines)
    assert "every probe object is deleted" in report.lines[-1]
    # Rule 15 and the docstring: no URL in its output, since a presigned one
    # carries a signature.
    assert "://" not in "\n".join(report.lines)


async def test_a_bucket_these_keys_reach_is_reported_as_a_failure(
    storage: S3Storage, http: httpx.AsyncClient
) -> None:
    """The local keys reach every bucket: named as one they mustn't, the probe
    says so, so a token scoped too widely can't pass it."""
    report = await probe(local_s3_settings(), storage, http, refused_buckets=(PRIVATE,))

    assert report.failed
    assert f"FAIL these keys are refused on {PRIVATE}" in report.lines


async def test_a_failed_delete_is_reported_not_raised(
    storage: S3Storage, http: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Found running the probe against a server missing a bucket: a delete that
    raised in the cleanup lost the whole report. Now the report comes back,
    saying the objects weren't all deleted."""
    real_delete = storage.delete
    refused: list[str] = []

    async def first_delete_fails(bucket: str, key: str) -> None:
        if not refused:
            refused.append(key)
            raise RuntimeError("delete refused")
        await real_delete(bucket, key)

    monkeypatch.setattr(storage, "delete", first_delete_fails)
    report = await probe(local_s3_settings(), storage, http)

    assert report.lines[-1] == "FAIL every probe object is deleted"
    assert report.failed
    monkeypatch.undo()
    await storage.delete(PUBLIC, refused[0])  # the one left behind


@pytest.mark.parametrize("env", ["production", "preview", UNNAMED_ENV])
async def test_the_probe_refuses_outside_local_and_staging(env: str) -> None:
    settings = local_s3_settings().model_copy(update={"ENV": env})

    async with httpx.AsyncClient() as http:
        with pytest.raises(ProbeRefused, match="runs only where ENV is local, staging"):
            await probe(settings, S3Storage(settings), http)


async def test_the_probes_command_refuses_before_touching_storage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    production = local_s3_settings().model_copy(update={"ENV": "production"})
    monkeypatch.setattr(storage_probe, "get_settings", lambda: production)
    out, err = io.StringIO(), io.StringIO()

    status = await storage_probe.main([], out=out, err=err)

    assert status == 2
    assert out.getvalue() == ""
    assert "ENV=production" in err.getvalue()
