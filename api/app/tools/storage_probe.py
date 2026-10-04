"""Storage, proved where it runs (T-4.1): from inside a deployed machine, with
that machine's own settings and keys, against the real buckets.

    flyctl ssh console -a velora-api-staging -C \\
        "python -m app.tools.storage_probe --refused-bucket velora-prod-private"

Each step prints `ok` or `FAIL` and what it checked; the exit code is 1 if any
failed. It writes only under `probe/`, and deletes everything it wrote, even
after a failure. It never prints a URL: a presigned one carries a signature.

Runs only where `ENV` is in `PROBE_RUNS_IN`, an allowlist (rule 16): the copy in
production's image refuses, so it can't write test objects into production's
buckets.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TextIO

import httpx

from app.core.config import Settings, get_settings
from app.core.providers.storage import ObjectNotFound, S3Storage
from app.core.storage_keys import public_url

PROBE_RUNS_IN: frozenset[str] = frozenset({"local", "staging"})
PREFIX = "probe"


class ProbeRefused(Exception):
    """This environment isn't one the probe may write test objects in."""


@dataclass
class Report:
    lines: list[str] = field(default_factory=list)
    failed: bool = False

    def check(self, ok: bool, what: str) -> bool:
        self.lines.append(f"{'ok  ' if ok else 'FAIL'} {what}")
        self.failed = self.failed or not ok
        return ok


def refuse_unless_allowed(settings: Settings) -> None:
    if settings.ENV not in PROBE_RUNS_IN:
        raise ProbeRefused(
            f"ENV={settings.ENV}: the storage probe writes test objects, so it runs "
            f"only where ENV is {', '.join(sorted(PROBE_RUNS_IN))}."
        )


async def probe(
    settings: Settings,
    storage: S3Storage,
    http: httpx.AsyncClient,
    *,
    refused_buckets: tuple[str, ...] = (),
) -> Report:
    refuse_unless_allowed(settings)
    report = Report()
    run = uuid.uuid4()
    written: list[tuple[str, str]] = []
    public, private = settings.R2_BUCKET_PUBLIC, settings.R2_BUCKET_PRIVATE

    async def step(what: str, body: Callable[[], Awaitable[bool]]) -> None:
        try:
            report.check(await body(), what)
        except Exception as error:  # noqa: BLE001 — each step reports, the next runs
            report.check(False, f"{what} ({type(error).__name__})")

    try:
        for bucket, label in ((public, "public"), (private, "private")):
            key = f"{PREFIX}/{run}/presigned.txt"
            body = f"probe {run} {label}".encode()
            written.append((bucket, key))

            async def put_signed(
                bucket: str = bucket, key: str = key, body: bytes = body
            ) -> bool:
                signed = await storage.presign_put(bucket, key, "text/plain", 1024)
                response = await http.put(
                    signed.url, content=body, headers=dict(signed.headers)
                )
                return response.status_code == 200

            async def put_wrong_type(bucket: str = bucket, key: str = key) -> bool:
                signed = await storage.presign_put(
                    bucket, f"{key}.wrong", "text/plain", 1024
                )
                response = await http.put(
                    signed.url, content=b"x", headers={"Content-Type": "image/png"}
                )
                return response.status_code == 403

            async def head_matches(
                bucket: str = bucket, key: str = key, body: bytes = body
            ) -> bool:
                info = await storage.head(bucket, key)
                return (info.size, info.content_type) == (len(body), "text/plain")

            async def get_signed(
                bucket: str = bucket, key: str = key, body: bytes = body
            ) -> bool:
                response = await http.get(await storage.presign_get(bucket, key))
                return response.status_code == 200 and response.content == body

            async def get_direct(
                bucket: str = bucket, key: str = key, body: bytes = body
            ) -> bool:
                return await storage.get_bytes(bucket, key) == body

            await step(f"{label}: a presigned PUT stores the object", put_signed)
            await step(
                f"{label}: the same PUT with another Content-Type is refused",
                put_wrong_type,
            )
            await step(f"{label}: head() reads its size and type", head_matches)
            await step(f"{label}: a presigned GET returns the bytes", get_signed)
            await step(f"{label}: get_bytes() returns the bytes", get_direct)

        direct = f"{PREFIX}/{run}/direct.txt"
        copied = f"{PREFIX}/{run}/copied.txt"
        written += [(private, direct), (public, copied)]

        async def put_direct() -> bool:
            await storage.put_bytes(private, direct, b"direct", "text/plain")
            return await storage.get_bytes(private, direct) == b"direct"

        async def copy_across() -> bool:
            await storage.copy(private, direct, public, copied)
            return await storage.get_bytes(public, copied) == b"direct"

        async def served_publicly() -> bool:
            response = await http.get(public_url(settings, copied))
            return response.status_code == 200 and response.content == b"direct"

        async def private_not_at_cdn() -> bool:
            response = await http.get(public_url(settings, direct))
            return response.status_code in (403, 404)

        await step("private: put_bytes() stores, as the worker will", put_direct)
        await step("copy() from the private bucket to the public one", copy_across)
        await step("the public copy is served at PUBLIC_CDN_URL", served_publicly)
        await step(
            "a private object's key is not served at PUBLIC_CDN_URL", private_not_at_cdn
        )

        async def absent_is_404() -> bool:
            # The control for the refusals below: here, with access, a key that
            # doesn't exist is a 404, so a 403 elsewhere means no access.
            for bucket in (public, private):
                try:
                    await storage.head(bucket, f"{PREFIX}/{run}/absent")
                except ObjectNotFound:
                    continue
                return False
            return True

        await step("an absent key in these buckets is a 404, not a 403", absent_is_404)

        for refused in refused_buckets:

            async def no_access(refused: str = refused) -> bool:
                # HEAD of a key that doesn't exist: 404 with access, 403 without.
                # A read that writes nothing, so a wrong token learns nothing.
                try:
                    await storage.head(refused, f"{PREFIX}/{run}/absent")
                except ObjectNotFound:
                    return False
                except Exception as error:  # noqa: BLE001
                    code = getattr(error, "response", {}).get("Error", {}).get("Code")
                    return code in ("403", "AccessDenied", "Forbidden")
                return False

            await step(f"these keys are refused on {refused}", no_access)
    finally:
        # Every delete is tried, and a failed one is reported, never raised: the
        # report so far is what someone needs, and an exception would lose it.
        for bucket, key in written:
            try:
                await storage.delete(bucket, key)
            except Exception:  # noqa: BLE001, S110 — all_gone() reports it
                pass

        async def all_gone() -> bool:
            for bucket, key in written:
                try:
                    await storage.head(bucket, key)
                except ObjectNotFound:
                    continue
                return False
            return True

        await step("every probe object is deleted", all_gone)
    return report


async def main(
    argv: list[str], out: TextIO = sys.stdout, err: TextIO = sys.stderr
) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument(
        "--refused-bucket",
        action="append",
        default=[],
        help="a bucket these keys must not reach (another environment's)",
    )
    args = parser.parse_args(argv)
    settings = get_settings()
    try:
        refuse_unless_allowed(settings)
    except ProbeRefused as refusal:
        err.write(f"{refusal}\n")
        return 2
    storage = S3Storage(settings)
    try:
        async with httpx.AsyncClient(timeout=20) as http:
            report = await probe(
                settings, storage, http, refused_buckets=tuple(args.refused_bucket)
            )
    finally:
        await storage.aclose()
    out.writelines(f"{line}\n" for line in report.lines)
    return 1 if report.failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
