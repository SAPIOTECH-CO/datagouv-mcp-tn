"""Structured JSON logging configuration.

All log records are emitted as single-line JSON objects so they can be
shipped to any log aggregator (ELK, Loki, Datadog...) without a parsing
pipeline. Uvicorn access/startup logs are routed through the same
formatter when running the http/sse transports.
"""

import logging
import sys

from pythonjsonlogger.json import JsonFormatter

MAIN_LOGGER_NAME = "datagouv_mcp_tn"

# Loggers whose records are captured and re-emitted as JSON.
_CAPTURED_LOGGERS = (
    MAIN_LOGGER_NAME,
    "uvicorn",
    "uvicorn.access",
    "uvicorn.error",
)

RESERVED_ATTRS = {
    "args", "asctime", "created", "exc_info", "exc_text", "filename",
    "funcName", "levelname", "levelno", "lineno", "module", "msecs",
    "message", "msg", "name", "pathname", "process", "processName",
    "relativeCreated", "stack_info", "stacklevel", "thread", "threadName",
    "taskName",
}


class _StripColorMessageFilter(logging.Filter):
    """Drop uvicorn's ``color_message`` extra so it stays out of JSON."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.__dict__.pop("color_message", None)
        return True


def _build_formatter() -> JsonFormatter:
    return JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        rename_fields={
            "asctime": "timestamp",
            "levelname": "level",
            "name": "logger",
            "lineno": "line",
            "funcName": "function",
        },
        reserved_attrs=RESERVED_ATTRS,
        datefmt="%Y-%m-%dT%H:%M:%S%z",
        json_ensure_ascii=False,
    )


def configure_logging(level: str = "INFO") -> dict:
    """Install the JSON formatter on the root and captured loggers.

    Returns the uvicorn logging config dict so ``uvicorn.run`` (via
    FastMCP) emits JSON access logs too.
    """
    formatter = _build_formatter()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.addFilter(_StripColorMessageFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())

    for logger_name in _CAPTURED_LOGGERS:
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()
        logger.addHandler(handler)
        logger.propagate = False

    logging.getLogger("uvicorn.access").setLevel(level.upper())

    return UVICORN_LOGGING_CONFIG


UVICORN_LOGGING_CONFIG: dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": lambda: _build_formatter(),
        },
    },
    "handlers": {
        "json": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "stream": "ext://sys.stdout",
            "filters": ["strip_color_message"],
        },
    },
    "filters": {
        "strip_color_message": {
            "()": f"{__name__}._StripColorMessageFilter",
        },
    },
    "loggers": {
        name: {"handlers": ["json"], "level": "INFO", "propagate": False}
        for name in _CAPTURED_LOGGERS
    },
}
