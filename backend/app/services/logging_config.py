from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

_RESERVED_ATTRS = {
    "name", "msg", "message", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName", "created",
    "msecs", "relativeCreated", "thread", "threadName", "processName", "process",
    "taskName",
}

_LOGGER_NAMES = ("uvicorn", "uvicorn.error", "uvicorn.access", "celery")


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key.startswith(("_", "@")) or key in _RESERVED_ATTRS:
                continue
            payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def _build_handler(log_json: bool) -> logging.Handler:
    handler = logging.StreamHandler()
    if log_json:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
    return handler


def configure_logging(log_json: bool, level: int = logging.INFO) -> None:
    root = logging.getLogger()
    root.setLevel(level)
    for handler in list(root.handlers):
        root.removeHandler(handler)
    root.addHandler(_build_handler(log_json))
    for name in _LOGGER_NAMES:
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = False
        logger.addHandler(_build_handler(log_json))


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)