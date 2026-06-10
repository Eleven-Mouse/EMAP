import json
import logging
import sys
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    _fixed_fields = (
        "event",
        "trace_id",
        "stage",
        "degrade_reason",
        "dependency",
    )
    _reserved_fields = {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "thread",
        "threadName",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in self._fixed_fields:
            payload[field] = record.__dict__.get(field)
        for key, value in record.__dict__.items():
            if (
                key in self._reserved_fields
                or key in self._fixed_fields
                or key.startswith("_")
            ):
                continue
            payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    root_logger = logging.getLogger()
    normalized_level = getattr(logging, str(level).upper(), logging.INFO)
    if getattr(root_logger, "_emap_configured", False):
        root_logger.setLevel(normalized_level)
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(normalized_level)
    root_logger._emap_configured = True  # type: ignore[attr-defined]


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
