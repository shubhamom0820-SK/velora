"""The founder's selfie review (D-264, T-4.5), run by hand inside a deployed
machine:

    flyctl ssh console -a velora-api-staging -C "python -m app.tools.selfie_review"
    flyctl ssh console -a velora-api-staging -C \\
        "python -m app.tools.selfie_review --verdict <verification id> same"

**Why a person looks at every one.** The threshold is SFace's published number
on celebrities' photos, not ours (D-260), and face matching alone doesn't stop
the attack that matters: a man with a woman's photos and one real selfie of
her. That selfie matches her photos closely, far from the threshold, so a list
of near-threshold results would show nothing. So this lists **every** decision
of the last `--days` not yet reviewed, newest first, a woman's included
whatever its number, marking those near the threshold and approved profiles
whose other photos didn't match ("mixed", P-162). `--near` narrows it to those.

**Each verdict is a measurement.** `--verdict <id> same|different` writes into
the selfie's record whether the selfie and the photos show the same person.
Those verdicts, gathered from real decisions as they are made, are the data
P-160 needs to measure the threshold. It changes nothing else: undoing a
decision is P-163's.

**It prints links, deliberately, unlike `storage_probe`.** The founder has to
see each selfie, and a selfie is never public: each is a signed link to the
private bucket that lasts 10 minutes. They go to the terminal of whoever runs
this over `flyctl ssh`, behind Fly's own login, and never into a log. That is
the exception, with its reason (D-264), so nobody "fixes" it: building an API
endpoint that lists women's selfies would be the worse risk. Photos compared
with are public already: their CDN address. Claude never runs this against
real people's selfies; on staging, only its own test accounts' (D-264).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence
from datetime import timedelta
from typing import TextIO, cast
from uuid import UUID

from app.core import clock
from app.core.config import Settings, get_settings
from app.core.db import build_engine, build_sessionmaker
from app.core.providers import build_providers
from app.core.providers.storage import StorageProvider
from app.core.storage_keys import public_url
from app.modules.verification import rules
from app.modules.verification import service as verification_service
from app.modules.verification.service import ForReview, Sessions

LINK_TTL_S = 600  # 10 minutes: long enough to look, short enough to go stale


def parse(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m app.tools.selfie_review")
    parser.add_argument("--days", type=int, default=7, help="how far back (7)")
    parser.add_argument(
        "--near",
        action="store_true",
        help="only those near the threshold, or approved with mixed photos",
    )
    parser.add_argument(
        "--include-reviewed", action="store_true", help="those with a verdict too"
    )
    parser.add_argument(
        "--verdict",
        nargs=2,
        metavar=("VERIFICATION_ID", "same|different"),
        help="record whether the selfie and the photos show the same person",
    )
    return parser.parse_args(list(argv))


async def run(
    args: argparse.Namespace,
    *,
    sessions: Sessions,
    storage: StorageProvider,
    settings: Settings,
    out: TextIO,
) -> int:
    if args.verdict:
        return await _verdict(args.verdict, sessions=sessions, out=out)
    since = clock.now() - timedelta(days=args.days)
    found = await verification_service.for_review(
        sessions, since, include_reviewed=args.include_reviewed
    )
    if args.near:
        found = [item for item in found if item.near or item.mixed]
    out.write(
        f"selfie_review: {len(found)} to look at from the last {args.days} days "
        f"(threshold {rules.MATCH_THRESHOLD}, SFace's published number, not "
        "ours: D-260). Links last 10 minutes.\n"
    )
    for item in found:
        await _show(item, storage=storage, settings=settings, out=out)
    return 0


async def _verdict(given: Sequence[str], *, sessions: Sessions, out: TextIO) -> int:
    raw_id, verdict = given
    if verdict not in rules.VERDICTS:
        out.write("selfie_review: the verdict is `same` or `different`.\n")
        return 2
    try:
        verification_id = UUID(raw_id)
    except ValueError:
        out.write("selfie_review: that isn't a verification id.\n")
        return 2
    recorded = await verification_service.record_verdict(
        sessions, verification_id, cast(rules.Verdict, verdict)
    )
    if not recorded:
        out.write(f"selfie_review: no verification {verification_id}.\n")
        return 1
    out.write(f"selfie_review: {verification_id} recorded as {verdict}.\n")
    return 0


async def _show(
    item: ForReview, *, storage: StorageProvider, settings: Settings, out: TextIO
) -> None:
    marks = [m for m, on in (("NEAR", item.near), ("MIXED", item.mixed)) if on]
    best = "none" if item.best is None else f"{item.best:.5f}"
    out.write(
        f"\n{item.verification_id}  {item.decided_at:%Y-%m-%d %H:%M} UTC  "
        f"{item.gender or 'unknown'}  {item.outcome}  best {best}"
        f"{'  ' + ' '.join(marks) if marks else ''}\n"
    )
    selfie = await storage.presign_get(
        settings.R2_BUCKET_PRIVATE, item.selfie_key, ttl=LINK_TTL_S
    )
    out.write(f"  selfie:  {selfie}\n")
    # The face photo (D-391), private, by a signed link; then each shown photo
    # compared with the selfie for the badge (D-393), by its public link.
    if item.face is None:
        out.write("  face photo: none\n")
    else:
        where = (
            "gone"
            if item.face.key is None
            else await storage.presign_get(
                settings.R2_BUCKET_PRIVATE, item.face.key, ttl=LINK_TTL_S
            )
        )
        out.write(f"  face photo: {_similarity(item.face.similarity)}  {where}\n")
    for place, compared in enumerate(item.shown):
        where = "gone" if compared.key is None else public_url(settings, compared.key)
        out.write(f"  shown {place}: {_similarity(compared.similarity)}  {where}\n")
    if item.verdict is None:
        out.write(
            f"  verdict: none yet  (--verdict {item.verification_id} same|different)\n"
        )
    else:
        out.write(f"  verdict: {item.verdict}\n")


def _similarity(value: float | None) -> str:
    return "no face found" if value is None else f"{value:.5f}"


async def main(argv: Sequence[str], out: TextIO = sys.stdout) -> int:
    args = parse(argv)
    settings = get_settings()
    engine = build_engine(settings.DATABASE_URL, hide_parameters=True)
    storage = build_providers(settings).storage
    try:
        return await run(
            args,
            sessions=build_sessionmaker(engine),
            storage=storage,
            settings=settings,
            out=out,
        )
    finally:
        await storage.aclose()
        await engine.dispose()


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
