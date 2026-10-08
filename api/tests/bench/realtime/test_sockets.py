"""The load test's verdict (T-7.4): every socket open, every event arrived,
and the most the server held under 256 MB. The run itself is by hand."""

from __future__ import annotations

from bench.realtime.sockets import LIMIT_MB, verdict


def test_a_clean_run_passes() -> None:
    assert verdict(1000, 1000, 1000, LIMIT_MB - 0.1) == []


def test_each_shortfall_is_named() -> None:
    assert verdict(1000, 990, 980, LIMIT_MB) == [
        "10 of 1000 sockets didn't open",
        "20 of 1000 events didn't arrive",
        "256.0 MB at most, not under 256",
    ]
