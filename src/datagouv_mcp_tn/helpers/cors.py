"""CORS and Host/Origin protection configuration for the MCP server.

Provides:
- CORSMiddleware for browser-based clients
- Host/Origin protection (FastMCP's DNS rebinding guard) via
  http_app() / run() parameters

Both are driven from settings so they can be tuned via environment variables.
"""

from __future__ import annotations

from typing import Any

from datagouv_mcp_tn.helpers.config import get_settings


def build_cors_middleware() -> list[dict[str, Any]] | None:
    """Build CORS middleware configuration from settings.

    Returns a list of Middleware dicts for mcp.http_app(middleware=...),
    or None if CORS is disabled (cors_enabled=False).
    """
    settings = get_settings()

    if not settings.cors_enabled:
        return None

    # Import lazily
    from starlette.middleware.cors import CORSMiddleware

    return [
        {
            "middleware_class": CORSMiddleware,
            "options": {
                "allow_origins": settings.cors_allowed_origins,
                "allow_methods": settings.cors_allowed_methods,
                "allow_headers": settings.cors_allowed_headers,
                "expose_headers": settings.cors_expose_headers,
                "allow_credentials": settings.cors_allow_credentials,
                "max_age": settings.cors_max_age,
            },
        }
    ]


def get_host_origin_protection_config() -> dict[str, Any]:
    """Return host/origin protection kwargs for mcp.http_app() or mcp.run().

    Returns a dict with keys: host_origin_protection, allowed_hosts, allowed_origins.
    """
    settings = get_settings()

    return {
        "host_origin_protection": settings.host_origin_protection,
        "allowed_hosts": settings.allowed_hosts if settings.allowed_hosts else None,
        "allowed_origins": settings.allowed_origins if settings.allowed_origins else None,
    }


def apply_security_to_http_app(mcp: Any) -> Any:
    """Apply CORS + host/origin protection to the HTTP app.

    Usage:
        from fastmcp import FastMCP
        from datagouv_mcp_tn.helpers.cors import apply_security_to_http_app

        mcp = FastMCP("My Server")
        # ... register tools ...
        app = apply_security_to_http_app(mcp)
        # then serve via uvicorn: uvicorn.run(app, ...)

    Returns the Starlette app with security middleware applied.
    """
    cors_middleware = build_cors_middleware()
    host_config = get_host_origin_protection_config()

    return mcp.http_app(middleware=cors_middleware, **host_config)