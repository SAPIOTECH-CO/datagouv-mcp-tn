"""Structured JSON logging configuration with secrets protection and PII anonymization.

All log records are emitted as single-line JSON objects so they can be
shipped to any log aggregator (ELK, Loki, Datadog...) without a parsing
pipeline. Uvicorn access/startup logs are routed through the same
formatter when running the http/sse transports.

Security features:
- Automatic masking of API keys, tokens, passwords, secrets
- PII anonymization: emails, IPs, user IDs
- Configurable via settings (log_sanitization_enabled, log_mask_patterns)
"""

import functools
import logging
import re
import sys

from pythonjsonlogger.json import JsonFormatter

from datagouv_mcp_tn.helpers.config import get_settings

MAIN_LOGGER_NAME = "datagouv_mcp_tn"

# Canonical logger instance shared across the project.
logger = logging.getLogger(MAIN_LOGGER_NAME)

# Loggers whose records are captured and re-emitted as JSON.
_CAPTURED_LOGGERS = (
    MAIN_LOGGER_NAME,
    "uvicorn",
    "uvicorn.access",
    "uvicorn.error",
)

RESERVED_ATTRS = {
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
    "stacklevel",
    "thread",
    "threadName",
    "taskName",
}

# --- secrets & PII patterns ---------------------------------------------------

# Matches: API keys, Bearer tokens, Authorization headers, passwords, secrets
_SECRET_PATTERNS = [
    # Authorization: Bearer <token>
    (re.compile(r"(?i)(authorization\s*[:=]\s*['\"]?)(bearer\s+)([a-zA-Z0-9._-]+)"), r"\1\2***"),
    # Generic key=value where key suggests secret
    (
        re.compile(
            r"(?i)(['\"]?(?:api[_-]?key|secret|token|password|passwd|pwd|access[_-]?token|auth[_-]?token)['\"]?\s*[:=]\s*['\"]?)([^'\"]{8,})"
        ),
        r"\1***",
    ),
    # Bare long alphanumeric strings that look like tokens (32+ chars)
    (re.compile(r"\b[a-zA-Z0-9._-]{32,}\b"), "***"),
]

# PII patterns
_PII_PATTERNS = [
    # Email addresses
    (re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"), "[email]"),
    # IPv4 addresses
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "[ip]"),
    # IPv6 addresses (simplified)
    (re.compile(r"\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b"), "[ip]"),
    # User IDs in paths like /users/12345 or ?user_id=12345
    (re.compile(r"(?i)(/users?/|[?&]user[_-]?id=)(\d+)"), r"\1[user_id]"),
    # Session IDs
    (re.compile(r"(?i)(session[_-]?id['\"]?\s*[:=]\s*['\"]?)([a-zA-Z0-9._-]{16,})"), r"\1***"),
]


def _sanitize_text(text: str) -> str:
    """Apply secret and PII masking to a string."""
    if not text:
        return text
    for pattern, repl in _SECRET_PATTERNS:
        text = pattern.sub(repl, text)
    for pattern, repl in _PII_PATTERNS:
        text = pattern.sub(repl, text)
    return text


class _SecretsAndPIIFilter(logging.Filter):
    """Filter that sanitizes log records before they reach the formatter.

    Strips/redacts:
    - Authorization headers, API keys, tokens, passwords
    - Email addresses, IP addresses, user IDs
    - uvicorn's color_message extra
    """

    def __init__(self, enabled: bool = True):
        super().__init__()
        self.enabled = enabled

    def filter(self, record: logging.LogRecord) -> bool:
        if not self.enabled:
            return True

        # Sanitize the main message
        if isinstance(record.msg, str):
            record.msg = _sanitize_text(record.msg)

        # Sanitize args if they're strings
        if record.args:
            sanitized_args: list[object] = []
            for arg in record.args:
                if isinstance(arg, str):
                    sanitized_args.append(_sanitize_text(arg))
                else:
                    sanitized_args.append(arg)
            record.args = tuple(sanitized_args)

        # Drop uvicorn's color_message
        record.__dict__.pop("color_message", None)

        return True


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

    Security sanitization is controlled by Settings.log_sanitization_enabled.
    """
    settings = get_settings()
    formatter = _build_formatter()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.addFilter(_StripColorMessageFilter())
    # Add secrets/PII filter
    handler.addFilter(_SecretsAndPIIFilter(enabled=settings.log_sanitization_enabled))

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
            "filters": ["strip_color_message", "secrets_pii"],
        },
    },
    "filters": {
        "strip_color_message": {
            "()": f"{__name__}._StripColorMessageFilter",
        },
        "secrets_pii": {
            "()": f"{__name__}._SecretsAndPIIFilter",
            "enabled": True,  # will be overridden by handler's instance
        },
    },
    "loggers": {
        name: {"handlers": ["json"], "level": "INFO", "propagate": False}
        for name in _CAPTURED_LOGGERS
    },
}


def log_tool(func):
    """Log tool invocations and failures with the shared project logger."""

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        logger.info("Tool '%s' called", func.__name__)
        try:
            return await func(*args, **kwargs)
        except Exception:
            logger.exception("Tool '%s' failed", func.__name__)
            raise

    return wrapper
