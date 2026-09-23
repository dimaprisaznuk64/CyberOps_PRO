from __future__ import annotations

import json
import logging

from app.services.logging_config import JSONFormatter, configure_logging


def _make_record(message: str, *args):
    return logging.LogRecord(
        name="app.tests",
        level=logging.INFO,
        pathname="app/tests/test_logging.py",
        lineno=1,
        msg=message,
        args=args,
        exc_info=None,
    )


def test_json_formatter_outputs_json():
    record = _make_record("hello %s", "world")
    record.extra_field = "value"
    payload = json.loads(JSONFormatter().format(record))
    assert payload["level"] == "info"
    assert payload["logger"] == "app.tests"
    assert payload["message"] == "hello world"
    assert payload["extra_field"] == "value"
    assert "ts" in payload


def test_configure_logging_switches_format():
    configure_logging(log_json=True)
    root = logging.getLogger()
    assert isinstance(root.handlers[0].formatter, JSONFormatter)
    configure_logging(log_json=False)
    assert not isinstance(root.handlers[0].formatter, JSONFormatter)