"""D-094's check: real Sightengine answers, their shape compared with the fake's.

The worker is built and tested against a fake that answers in the shape
Sightengine documents (`core/providers/moderation.py`). If the real answer
spells, nests or types a field differently, every green test is a fiction, and
a call that returns 200 wouldn't show it. So this sends two real checks, each
the way the worker sends one: Sightengine's own documentation examples (a face,
and embedded text), re-encoded by `images.reencode`, through the provider
`build_providers` makes from `Settings`, on the plain image API. It prints the
shape of each answer, field names and JSON types only, never a value or a key,
and every difference from the fake's answer for the same case. Exit 0 when
there is none, 1 when there is, 2 when it can't run.

Run with the worker's settings, Sightengine's keys in the environment, never on
the command line (infra/STAGING.md §4), for instance inside the worker's
machine: `flyctl ssh console -a velora-worker-staging -C "python -m
app.tools.sightengine_shape"`. Each run costs 6 operations (3 models, twice).
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import Sequence
from typing import Any, Final, TextIO

import httpx

from app.core.config import get_settings
from app.core.images import reencode, sniff
from app.core.providers import build_providers
from app.core.providers.moderation import (
    FakeOutcome,
    ModerationFailed,
    SightengineModeration,
    fake_answer,
    parse_check,
)
from app.workers.main import WorkerMisconfigured, refuse_unless_ready

# Sightengine's own examples: the face-age page's, and the text model page's.
EXAMPLES: Final[Sequence[tuple[str, str, FakeOutcome]]] = (
    ("a face", "https://sightengine.com/assets/img/examples/example7.jpg", "approve"),
    (
        "embedded text",
        "https://sightengine.com/assets/img/examples/text1-1200.jpg",
        "text_overlay",
    ),
)


def shape(value: Any) -> Any:
    """Field names and JSON types, no values. A list's shape is its elements'
    merged; an empty list's is unknown, and compares with anything."""
    if isinstance(value, dict):
        return {key: shape(item) for key, item in sorted(value.items())}
    if isinstance(value, list):
        merged: Any = None
        for item in value:
            merged = _merge(merged, shape(item))
        return ["list", merged]
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int | float):
        return "number"
    if isinstance(value, str):
        return "string"
    if value is None:
        return "null"
    return type(value).__name__


def _merge(a: Any, b: Any) -> Any:
    if a is None:
        return b
    if isinstance(a, dict) and isinstance(b, dict):
        return {k: _merge(a.get(k), b.get(k)) for k in sorted({*a, *b})}
    return a if a == b else f"{a} | {b}"


def differences(real: Any, fake: Any, path: str = "") -> list[str]:
    """Every place the two shapes differ, by path."""
    if isinstance(real, dict) and isinstance(fake, dict):
        found: list[str] = []
        for key in sorted({*real, *fake}):
            here = f"{path}.{key}" if path else key
            if key not in fake:
                found.append(f"{here}: in the real answer, not the fake's")
            elif key not in real:
                found.append(f"{here}: in the fake's answer, not the real one")
            else:
                found += differences(real[key], fake[key], here)
        return found
    if isinstance(real, list) and isinstance(fake, list):
        if real[1] is None or fake[1] is None:
            return []  # an empty list says nothing about its elements
        return differences(real[1], fake[1], f"{path}[]")
    return [] if real == fake else [f"{path}: real {real}, fake {fake}"]


def lines(tree: Any, path: str = "") -> list[str]:
    if isinstance(tree, dict):
        return [
            line
            for key, item in tree.items()
            for line in lines(item, f"{path}.{key}" if path else key)
        ]
    if isinstance(tree, list):
        return [f"{path}: list"] + (
            lines(tree[1], f"{path}[]")
            if tree[1] is not None
            else [f"{path}[]: (empty)"]
        )
    return [f"{path}: {tree}"]


async def run(out: TextIO) -> int:
    settings = get_settings()
    try:
        refuse_unless_ready(settings)
    except WorkerMisconfigured as refusal:
        out.write(f"refused: {refusal}\n")
        return 2
    moderation = build_providers(settings).moderation
    if not isinstance(moderation, SightengineModeration):
        out.write(
            "refused: MODERATION_PROVIDER must be sightengine for a real check.\n"
        )
        return 2
    found: list[str] = []
    try:
        async with httpx.AsyncClient(timeout=30) as web:
            for name, url, outcome in EXAMPLES:
                example = (await web.get(url)).raise_for_status().content
                image_type = sniff(example[:16])
                if image_type is None:
                    out.write(f"{name}: the example isn't a JPEG, PNG or WebP\n")
                    return 2
                body = await moderation.check_raw(reencode(example, image_type).data)
                real = shape(json.loads(body))
                out.write(f"--- {name}: the real answer's shape\n")
                out.write("\n".join(lines(real)) + "\n")
                diff = differences(real, shape(fake_answer(outcome)))
                try:
                    parse_check(body)  # the worker's own reader
                except ModerationFailed:
                    diff.append("the worker's reader refuses it")
                out.write(f"--- {name}: {len(diff)} difference(s) from the fake's\n")
                out.write("".join(f"  {d}\n" for d in diff))
                found += diff
    except ModerationFailed as failure:
        out.write(f"failed: {failure}\n")
        return 2
    finally:
        await moderation.aclose()
    out.write("same shape\n" if not found else "shapes differ\n")
    return 0 if not found else 1


def main() -> int:
    return asyncio.run(run(sys.stdout))


if __name__ == "__main__":
    sys.exit(main())
