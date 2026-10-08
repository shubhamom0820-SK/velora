"""Time discovery's feed at 50k profiles, both of the plan's shapes (T-6.2, Q7).

    uv run python -m bench.discovery.run                  # from api/: 5 rounds
    uv run python -m bench.discovery.run --rounds 10 --count 50000

Run by hand on the founder's machine, never in `make test` or CI: a timing on
a shared runner fails at random and would block every session's landing
(the founder, 8 October 2026). Each shape gets a database of its own,
`velora_bench_discovery_<shape>`, dropped and made again from the migrations,
on this machine's Postgres only: never `velora`, never a test slot.

Each database holds `count` profiles (`crowd.py`) and one viewer, a man at
Phagwara's middle who has already swiped the nearest 2,000 women (one in 25
of the crowd), so the swipe
anti-join has real work. A round is, per shape, 10 warm-up requests, then 100
timed: each one the two statements a `GET /v1/discover` runs against the
database (the ranked page, then its cards), in one transaction, as the
service runs them; half first pages, half the page after a cursor 200 cards
deep. Rounds interleave the shapes, so neither always runs on a warmer cache.

It prints each round's p50 and p95 per shape, the range of each across
rounds, and `EXPLAIN ANALYZE` of each shape's first page once, and writes all
of it to `out/t-6.2-bench/`, git-ignored. Exit 1 if any spread round's p95 is
80 ms or over: the target (02-ARCHITECTURE §8), which holds for the spread
shape, what beta looks like. The launch shape is reported, never judged: it is
accepted above 80 ms, far beyond beta scale (D-495), until P-391's cell-first
ranking.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from alembic import command as alembic_command
from app.core.config import get_settings
from app.core.db import build_engine
from app.core.enums import Gender, Seeking
from app.modules.discovery import repository
from bench.discovery.crowd import PHAGWARA, Shape, crowd
from tests.infra import run_alembic

REPO: Final = Path(__file__).resolve().parents[3]
OUT: Final = REPO / "out" / "t-6.2-bench"
LOOPBACK: Final = frozenset({"127.0.0.1", "localhost", "::1"})
SHAPES: Final[tuple[Shape, ...]] = ("spread", "launch")
TARGET_MS: Final = 80.0
# The shape the target holds for (D-495).
JUDGED: Final[Shape] = "spread"
# The viewer has swiped one profile in this many: 2,000 at 50k.
SWIPED_ONE_IN: Final = 25
WARM: Final = 10
TIMED: Final = 100
DEEP: Final = 200
RADIUS_M: Final = 25_000.0


def say(line: str) -> None:
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def bench_url(server_url: str, shape: Shape) -> str:
    url = make_url(server_url)
    if url.host not in LOOPBACK:
        raise SystemExit(
            f"DATABASE_URL points at {url.host!r}: the bench makes databases only "
            "on this machine's Postgres."
        )
    return url.set(database=f"velora_bench_discovery_{shape}").render_as_string(
        hide_password=False
    )


async def fresh_database(server_url: str, shape: Shape) -> AsyncEngine:
    url = bench_url(server_url, shape)
    admin = create_async_engine(
        server_url, poolclass=NullPool, isolation_level="AUTOCOMMIT"
    )
    name = make_url(url).database
    async with admin.connect() as connection:
        await connection.execute(text(f'drop database if exists "{name}" with (force)'))
        await connection.execute(text(f'create database "{name}"'))
    await admin.dispose()
    engine = build_engine(url)
    await run_alembic(engine, alembic_command.upgrade, "head")
    return engine


async def seed(engine: AsyncEngine, shape: Shape, count: int) -> repository.Viewer:
    async with AsyncSession(engine) as session, session.begin():
        await crowd(session, count, shape, tag="bench")
        viewer = uuid4()
        await session.execute(
            text(
                "INSERT INTO users (id, phone_hash, phone_enc, gender, dob, role, status,"
                " onboarding_step, is_verified, referral_code) VALUES (:id, 'bench-viewer',"
                " '\\x00'::bytea, 'male', DATE '1997-03-01', 'user', 'active', 'done',"
                " false, 'BENCHVIEWER')"
            ),
            {"id": viewer},
        )
        await session.execute(
            text(
                "INSERT INTO profiles (user_id, first_name, username, about, hometown,"
                " city, seeking, location, completeness) VALUES (:id, 'Viewer',"
                " 'benchviewer', :about, 'Phagwara', 'Phagwara', 'women',"
                " ST_SnapToGrid(ST_SetSRID(ST_MakePoint(:lng, :lat), 4326), 0.01)"
                "::geography, 50)"
            ),
            {"id": viewer, "lat": PHAGWARA[0], "lng": PHAGWARA[1], "about": "x" * 40},
        )
        # The nearest women, one profile in 25's worth, as a keen man's history
        # would be: 2,000 at 50k.
        await session.execute(
            text(
                "INSERT INTO swipes (swiper_id, target_id, dir) SELECT :id, u.id, 'pass'"
                " FROM users u JOIN profiles p ON p.user_id = u.id"
                " WHERE u.gender = 'female' ORDER BY p.location <-> (SELECT location"
                " FROM profiles WHERE user_id = :id) LIMIT :n"
            ),
            {"id": viewer, "n": count // SWIPED_ONE_IN},
        )
        await session.execute(text("ANALYZE"))
    return repository.Viewer(
        id=viewer,
        gender=Gender.MALE,
        seeking=Seeking.WOMEN,
        shadowed=False,
        position=PHAGWARA,
    )


def page(
    viewer: repository.Viewer, as_of: datetime, after: tuple[float, UUID] | None
) -> dict[str, Any]:
    return {
        "as_of": as_of,
        "radius_m": RADIUS_M,
        "new_first": False,
        "online_since": None,
        "intent_ids": (),
        "badge_only": False,
        "after": after,
        "limit": 21,
    }


async def one_request(
    engine: AsyncEngine,
    viewer: repository.Viewer,
    as_of: datetime,
    after: tuple[float, UUID] | None,
) -> float:
    start = time.perf_counter()
    async with AsyncSession(engine) as session, session.begin():
        rows = await repository.feed(session, viewer, **page(viewer, as_of, after))
        await repository.cards(session, [row.user_id for row in rows])
    return (time.perf_counter() - start) * 1000


async def deep_cursor(
    engine: AsyncEngine, viewer: repository.Viewer, as_of: datetime
) -> tuple[float, UUID]:
    async with AsyncSession(engine) as session, session.begin():
        rows = await repository.feed(
            session, viewer, **{**page(viewer, as_of, None), "limit": DEEP}
        )
        # A small crowd may hold fewer: then the deepest there is.
    last = rows[-1] if rows else None
    if last is None:
        raise SystemExit("the feed is empty: nothing to page through")
    return (last.score, last.user_id)


async def explain(
    engine: AsyncEngine, viewer: repository.Viewer, as_of: datetime
) -> str:
    statement = repository.feed_query(viewer, **page(viewer, as_of, None))
    async with engine.connect() as connection:
        compiled = statement.compile(
            dialect=connection.dialect, compile_kwargs={"render_postcompile": True}
        )
        params = compiled.construct_params()
        result = await connection.exec_driver_sql(
            "EXPLAIN (ANALYZE, BUFFERS) " + str(compiled),
            tuple(params[name] for name in compiled.positiontup or []),
        )
        return "\n".join(row[0] for row in result)


def percentile(values: list[float], share: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(share * (len(ordered) - 1)))]


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--count", type=int, default=50_000)
    args = parser.parse_args()
    server_url = get_settings().DATABASE_URL
    OUT.mkdir(parents=True, exist_ok=True)
    as_of = datetime.now(UTC)  # noqa: TID251 — the bench's own wall clock, not app code
    engines: dict[Shape, AsyncEngine] = {}
    viewers: dict[Shape, repository.Viewer] = {}
    deep: dict[Shape, tuple[float, UUID]] = {}
    report: dict[str, Any] = {"count": args.count, "rounds": [], "plans": {}}
    for shape in SHAPES:
        say(f"{shape}: a fresh database, {args.count} profiles…")
        engines[shape] = await fresh_database(server_url, shape)
        viewers[shape] = await seed(engines[shape], shape, args.count)
        deep[shape] = await deep_cursor(engines[shape], viewers[shape], as_of)
        report["plans"][shape] = await explain(engines[shape], viewers[shape], as_of)
        (OUT / f"plan-{shape}.txt").write_text(report["plans"][shape])
    over = False
    for number in range(1, args.rounds + 1):
        for shape in SHAPES if number % 2 else reversed(SHAPES):
            engine, viewer = engines[shape], viewers[shape]
            for _ in range(WARM):
                await one_request(engine, viewer, as_of, None)
            times = [
                await one_request(engine, viewer, as_of, None if i % 2 else deep[shape])
                for i in range(TIMED)
            ]
            p50, p95 = statistics.median(times), percentile(times, 0.95)
            over = over or (shape == JUDGED and p95 >= TARGET_MS)
            report["rounds"].append(
                {
                    "round": number,
                    "shape": shape,
                    "p50_ms": p50,
                    "p95_ms": p95,
                    "max_ms": max(times),
                }
            )
            say(
                f"round {number} {shape}: p50 {p50:.1f} ms, p95 {p95:.1f} ms, max {max(times):.1f} ms"
            )
    for shape in SHAPES:
        rows = [r for r in report["rounds"] if r["shape"] == shape]
        p95s = [r["p95_ms"] for r in rows]
        p50s = [r["p50_ms"] for r in rows]
        say(
            f"{shape}: p95 {min(p95s):.1f} to {max(p95s):.1f} ms, "
            f"p50 {min(p50s):.1f} to {max(p50s):.1f} ms, over {len(rows)} rounds"
        )
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")  # noqa: TID251 — the bench's own wall clock
    (OUT / f"run-{stamp}.json").write_text(json.dumps(report, indent=2))
    for engine in engines.values():
        await engine.dispose()
    say(
        f"written to {OUT}; {JUDGED}'s target p95 < {TARGET_MS:.0f} ms: "
        f"{'MISSED' if over else 'met'}"
    )
    return 1 if over else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
