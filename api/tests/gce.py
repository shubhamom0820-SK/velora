"""The VMs' own settings (P-49), read as Compose reads them on the VM.

`infra/gce/<env>.env` holds each environment's settings that aren't secret, for
the API and the worker alike; `infra/gce/compose.yml` adds the worker's own pool
and poll. Tests that ask "does staging's configuration start?" read these, so a
value Settings refuses goes red here, before a deploy stops on it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

GCE = Path(__file__).resolve().parents[2] / "infra" / "gce"


def gce_env(name: str) -> dict[str, str]:
    """`infra/gce/<name>.env` as Compose's `format: raw` reads it: one
    KEY=VALUE a line, blank lines and `#` comments skipped, and the value taken
    exactly as written, with no quotes removed and no `$` expanded."""
    env: dict[str, str] = {}
    for line in (GCE / f"{name}.env").read_text().splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, sep, value = line.partition("=")
        assert sep, f"{name}.env: {line!r} isn't KEY=VALUE"
        env[key] = value
    return env


def compose() -> dict[str, Any]:
    """`infra/gce/compose.yml`, parsed."""
    parsed: dict[str, Any] = yaml.safe_load((GCE / "compose.yml").read_text())
    return parsed


def worker_env(name: str) -> dict[str, str]:
    """What the worker's container starts with on that environment's VM,
    secrets aside: the shared settings, then compose.yml's own for the worker."""
    own: dict[str, str] = compose()["services"]["worker"].get("environment", {})
    return {**gce_env(name), **own}
