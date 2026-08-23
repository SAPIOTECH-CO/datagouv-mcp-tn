from contextlib import asynccontextmanager

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from datagouv_mcp_tn.helpers.api_client import aclose
from datagouv_mcp_tn.helpers.config import get_settings
from datagouv_mcp_tn.helpers.cors import apply_security_to_http_app
from datagouv_mcp_tn.helpers.logging_config import configure_logging
from datagouv_mcp_tn.helpers.rate_limit import build_rate_limit_middleware
from datagouv_mcp_tn.helpers.resources import (
    get_api_docs,
    get_config,
    get_portal_info,
    get_portals_registry,
    get_schema,
)
from datagouv_mcp_tn.prompts import register_prompts
from datagouv_mcp_tn.tools import register_tools

# Configure JSON logging with secrets/PII sanitization before anything else
_settings = get_settings()
configure_logging(_settings.log_level)


@asynccontextmanager
async def lifespan(app):
    """Manage server lifespan - cleanup HTTP clients on shutdown."""
    try:
        yield
    finally:
        await aclose()


# FastMCP with strict input validation
mcp = FastMCP(
    "datagouv-mcp-tn MCP server",
    instructions=(
        "Tools for exploring any CKAN open data portal. Start with "
        "search_datasets or search_organizations, then drill into datasets with "
        "get_dataset_info and list_dataset_resources. Tabular resources can "
        "be analyzed in memory with download_and_parse_resource and "
        "query_resource_data. Use the `portal` parameter to target a specific "
        "portal (default: configured default portal)."
    ),
    strict_input_validation=_settings.strict_input_validation,
    lifespan=lifespan,
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


# --- MCP Resources (dynamic templates + static) ---


@mcp.resource("ckan://config", name="Server Configuration")
async def resource_config() -> str:
    """Current server configuration (JSON)."""
    return await get_config()


@mcp.resource("ckan://schema", name="CKAN API Schema Reference")
async def resource_schema() -> str:
    """CKAN API schema reference (abridged)."""
    return await get_schema()


@mcp.resource("ckan://portals", name="CKAN Portals Registry")
async def resource_portals() -> str:
    """All known CKAN portals registry."""
    return await get_portals_registry()


@mcp.resource("ckan://portals/{portal_key}/info", name="Portal Info")
async def resource_portal_info(portal_key: str) -> str:
    """Detailed information about a specific portal."""
    return await get_portal_info(portal_key)


@mcp.resource("ckan://portals/{portal_key}/api/docs", name="Portal API Docs")
async def resource_portal_api_docs(portal_key: str) -> str:
    """CKAN API documentation for a specific portal."""
    return await get_api_docs(portal_key)


register_tools(mcp)
register_prompts(mcp)

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
