"""P-49's round-trip probe: numbers only, never a host or a URL, and only where
ENV is local or staging (app/tools/roundtrip_probe.py)."""

from __future__ import annotations

import io
import re
from urllib.parse import urlsplit

import pytest

from app.core import config
from app.tools import roundtrip_probe
from tests.infra import TEST_DATABASE_URL, TEST_REDIS_URL


async def test_it_measures_both_stores_and_prints_numbers_only() -> None:
    out = io.StringIO()

    code = await roundtrip_probe.measure(
        TEST_DATABASE_URL, TEST_REDIS_URL, out=out, queries=5, connects=2
    )

    text = out.getvalue()
    assert code == 0, text
    lines = text.splitlines()
    assert [line.split(":")[0] for line in lines] == [
        "postgres tcp connect",
        "redis tcp connect",
        "postgres connection opened",
        "postgres SELECT 1, warm connection",
        "redis PING",
    ]
    assert re.search(
        r"postgres SELECT 1, warm connection: median [\d.]+ ms, p95 [\d.]+ ms, over 5$",
        text,
        re.MULTILINE,
    )
    assert re.search(
        r"redis PING: median [\d.]+ ms, p95 [\d.]+ ms, over 5$", text, re.MULTILINE
    )
    assert re.search(
        r"postgres tcp connect: [\d.]+ ms \(AF_INET6?\)$", text, re.MULTILINE
    )
    for url in (TEST_DATABASE_URL, TEST_REDIS_URL):
        parts = urlsplit(url)
        assert parts.hostname and parts.hostname not in text
        assert str(parts.port) not in text.replace(" ms", "")
    assert "://" not in text


async def test_a_store_it_cant_reach_is_named_without_its_message() -> None:
    out = io.StringIO()
    unreachable = "postgresql+asyncpg://u:secret-password@127.0.0.1:1/x"

    code = await roundtrip_probe.measure(
        unreachable, TEST_REDIS_URL, out=out, queries=2, connects=1
    )

    text = out.getvalue()
    assert code == 1
    assert "postgres tcp connect: FAILED (" in text
    assert "postgres: FAILED (" in text
    assert "secret-password" not in text
    assert "127.0.0.1" not in text


@pytest.mark.parametrize("env", ["production", "env-nobody-has-named-2031"])
def test_it_refuses_outside_local_and_staging(
    env: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An allowlist (rule 16): a name nobody listed is refused like production."""
    settings = config.get_settings().model_copy(update={"ENV": env})
    monkeypatch.setattr(roundtrip_probe, "get_settings", lambda: settings)
    out = io.StringIO()

    assert roundtrip_probe.main(out) == 2
    assert (
        out.getvalue()
        == f"roundtrip_probe: refused, ENV={env} (only local and staging)\n"
    )


def test_the_summary_is_median_and_p95() -> None:
    samples = [i / 1000 for i in range(1, 21)]  # 1 ms to 20 ms

    assert roundtrip_probe.summary(samples) == "median 10.5 ms, p95 19.0 ms, over 20"
