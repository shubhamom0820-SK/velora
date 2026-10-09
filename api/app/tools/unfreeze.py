"""The founder's unfreeze (D-906, T-9.2), run by hand inside a deployed machine:

    flyctl ssh console -a velora-api-staging -C \\
        "python -m app.tools.unfreeze <user id> --by <your user id> --reason '<why>'"

**Why it exists before T-9.5.** Fraud scoring freezes accounts by itself (D-031,
D-900): three reports from people who shared a Thread with someone, or a score
above 80. However well it is tuned, it will freeze someone it shouldn't, a
woman reported by men who colluded among them. The founder, approving T-9.2's
plan on 9 October 2026: "bas ek chiz rakho ki by me hum koi bhi ladki ka
account open kar sakte hai kyuki fraud kitna bhi roke ho hi jayega" (keep one
thing: that we can open any woman's account afterwards, because however much
we stop fraud, it will happen anyway). Relayed with the reading that he undoes
it himself, from now, not only once T-9.5's panel exists; T-9.5 later gives
it a screen.

**What it does, and only that:** a frozen account, any account, becomes
`active`; its score goes to 0 and `normal`, and only signals from now on count
(`fraud_scores.counted_from`), so the next recompute can't freeze it again on
what was just set aside; one `audit_log` row, `fraud.unfreeze`, names `--by`,
who must be an active admin. It never signs in as the person, makes no session,
and reads no message. The person signs in again themselves.

It prints ids and statuses, never a phone number or a name.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence
from typing import TextIO
from uuid import UUID

from app.core.config import get_settings
from app.core.db import SessionOpener, build_engine, build_sessionmaker
from app.modules.safety import scoring


def parse(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m app.tools.unfreeze")
    parser.add_argument("user_id", help="the frozen account's id")
    parser.add_argument(
        "--by", required=True, help="your own account's id: an active admin"
    )
    parser.add_argument(
        "--reason", required=True, help="why, for the audit log (not shown to them)"
    )
    return parser.parse_args(list(argv))


async def run(args: argparse.Namespace, *, sessions: SessionOpener, out: TextIO) -> int:
    try:
        user_id, by = UUID(args.user_id), UUID(args.by)
    except ValueError:
        out.write("unfreeze: the account and --by are both ids (UUIDs).\n")
        return 2
    reason = args.reason.strip()
    if not reason:
        out.write("unfreeze: --reason can't be empty: the audit log keeps it.\n")
        return 2
    try:
        async with sessions() as session, session.begin():
            lifted = await scoring.unfreeze(session, user_id, by=by, reason=reason)
    except scoring.NotAnAdmin:
        out.write(f"unfreeze: {by} isn't an active admin. Nothing changed.\n")
        return 1
    except LookupError:
        out.write(f"unfreeze: no account {user_id}. Nothing changed.\n")
        return 1
    except scoring.NotFrozen:
        out.write(f"unfreeze: {user_id} isn't frozen. Nothing changed.\n")
        return 1
    out.write(
        f"unfreeze: {user_id} is active again; its score was "
        f"{lifted.score_before} ({lifted.band_before.value}) and starts again "
        "from now. They sign in again themselves. Recorded in audit_log as "
        f"{by}.\n"
    )
    return 0


async def main(argv: Sequence[str], out: TextIO = sys.stdout) -> int:
    args = parse(argv)
    settings = get_settings()
    engine = build_engine(settings.DATABASE_URL, hide_parameters=True)
    try:
        return await run(args, sessions=build_sessionmaker(engine), out=out)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
