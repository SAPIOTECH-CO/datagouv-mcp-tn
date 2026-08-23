"""Rate limiting configuration for the MCP server.

Wraps FastMCP's SlidingWindowRateLimitingMiddleware with settings-driven
parameters. Designed to be imported and applied once in server.py.
"""

from __future__ import annotations

from datagouv_mcp_tn.helpers.config import get_settings


def build_rate_limit_middleware():
    """Create the rate limiting middleware from settings.

    Returns the middleware instance, or None if rate limiting is disabled
    (rate_limit_enabled=False or max_requests <= 0).
    """
    settings = get_settings()

    if not settings.rate_limit_enabled or settings.rate_limit_max_requests <= 0:
        return None

    # Import lazily to avoid hard dependency at module load time
    from fastmcp.server.middleware.rate_limiting import SlidingWindowRateLimitingMiddleware

    return SlidingWindowRateLimitingMiddleware(
        max_requests=settings.rate_limit_max_requests,
        window_minutes=settings.rate_limit_window_minutes,
    )
