from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from datagouv_mcp_tn.helpers.config import get_settings
from datagouv_mcp_tn.helpers.cors import (
    apply_security_to_http_app,
    get_host_origin_protection_config,
)
from datagouv_mcp_tn.helpers.logging_config import configure_logging
from datagouv_mcp_tn.helpers.rate_limit import build_rate_limit_middleware
from datagouv_mcp_tn.helpers.resources import (
    get_api_docs,
    get_config,
    get_portals_registry,
    get_schema,
)
from datagouv_mcp_tn.tools import register_tools

# Configure JSON logging with secrets/PII sanitization before anything else
_settings = get_settings()
configure_logging(_settings.log_level)

# FastMCP with strict input validation
mcp = FastMCP(
    "data.gouv.tn MCP server",
    instructions=(
        "Tools for exploring the Tunisian open data portal (data.gouv.tn), "
        "built on the uData platform. Start with search_datasets or "
        "search_organizations, then drill into datasets with "
        "get_dataset_info and list_dataset_resources. Tabular resources can "
        "be analyzed in memory with download_and_parse_resource and "
        "query_resource_data."
    ),
    strict_input_validation=_settings.strict_input_validation,
)

# --- Security middleware (order matters: rate limit first, then response limit) ---

# Rate limiting (sliding window, 100 req/min by default)
rate_limit_mw = build_rate_limit_middleware()
if rate_limit_mw:
    mcp.add_middleware(rate_limit_mw)

# Response size limiting (existing)
try:
    from fastmcp.server.middleware.response_limiting import ResponseLimitingMiddleware

    mcp.add_middleware(ResponseLimitingMiddleware(max_size=300_000))
except ImportError:  # pragma: no cover - optional middleware on older fastmcp
    pass


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "datagouv-mcp-tn"})


# --- MCP Resources (read-only, accessible via ckan:// URIs) ---


@mcp.resource("ckan://api/docs", name="CKAN API Documentation")
async def resource_api_docs() -> str:
    """CKAN API documentation and endpoint reference."""
    return await get_api_docs()


@mcp.resource("ckan://config", name="Server Configuration")
async def resource_config() -> str:
    """Current server configuration (JSON)."""
    return await get_config()


@mcp.resource("ckan://schema", name="CKAN API Schema Reference")
async def resource_schema() -> str:
    """CKAN API schema reference (abridged)."""
    return await get_schema()


@mcp.resource("ckan://portals", name="Tunisian CKAN Portals Registry")
async def resource_portals() -> str:
    """Known Tunisian CKAN portals registry."""
    return await get_portals_registry()


register_tools(mcp)

# Opt-in Generative UI
if _settings.enable_generative_ui:
    try:
        from fastmcp.apps.generative import GenerativeUI

        mcp.add_provider(GenerativeUI())
    except ImportError:  # pragma: no cover - fastmcp[apps] extra not installed
        pass


# Export a pre-configured HTTP app for uvicorn/fastmcp run
# This applies CORS + Host/Origin protection
def _create_http_app():
    return apply_security_to_http_app(mcp)


# For direct uvicorn usage: uvicorn datagouv_mcp_tn.server:app
# or: fastmcp run datagouv_mcp_tn/server.py:mcp
app = _create_http_app()

# When running via `python -m datagouv_mcp_tn.server` or `fastmcp run`,
# the host/origin protection is applied via the `run` call.
# Users can also call `mcp.run(...)` with the protection config:
if __name__ == "__main__":
    host_config = get_host_origin_protection_config()

    # Default to stdio for CLI/IDE integration (opencode, Claude Desktop, etc.)
    # Allow override via env var: TRANSPORT=stdio|http|sse
    import os

    transport = os.getenv("TRANSPORT", "stdio")

    if transport == "sse":
        # SSE transport for real-time streaming
        mcp.run(
            transport="sse",
            host="0.0.0.0",
            port=8000,
            **host_config,
        )
    elif transport == "http":
        # HTTP transport for web clients
        mcp.run(
            transport="http",
            host="0.0.0.0",
            port=8000,
            **host_config,
        )
    else:
        # Default: stdio for CLI/IDE integration (opencode, Claude Desktop, etc.)
        mcp.run(
            transport="stdio",
        )
