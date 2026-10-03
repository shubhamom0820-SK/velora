"""Logging (core/logging.py): what tests rely on to check rule 15 (P-48)."""

from __future__ import annotations

import structlog
from structlog.testing import capture_logs

from app.core.logging import configure_logging
from app.main import create_app
from tests.conftest import make_test_settings


def test_a_logger_used_before_logging_is_reconfigured_is_still_captured() -> None:
    """structlog binds a logger, at first use, to the processors configured
    then. Every create_app() reconfigures logging; before P-48 each call made
    a new list, so a logger used earlier never reached capture_logs, and a test
    that nothing secret was logged passed having captured nothing."""
    log = structlog.get_logger("p48.reconfigured")
    configure_logging(json_logs=False)
    log.info("first_use")
    configure_logging(json_logs=True)

    with capture_logs() as events:
        log.info("after_reconfiguring", n=1)

    assert events == [{"event": "after_reconfiguring", "n": 1, "log_level": "info"}]


def test_a_module_logger_is_captured_after_an_app_is_built() -> None:
    """The order a shuffled suite produces: a module's logger used, then an
    app built (each test's `app` fixture builds one), then a capture."""
    log = structlog.get_logger("p48.module")
    log.info("used_by_an_earlier_test")
    create_app(make_test_settings())

    with capture_logs() as events:
        log.warning("in_this_test")

    assert [e["event"] for e in events] == ["in_this_test"]
