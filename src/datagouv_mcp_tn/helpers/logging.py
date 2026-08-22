import functools
import logging

MAIN_LOGGER_NAME = "datagouv_mcp_tn"

logger = logging.getLogger(MAIN_LOGGER_NAME)


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
