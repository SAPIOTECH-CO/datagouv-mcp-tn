from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from datagouv_mcp_tn.tools import register_tools

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
)

# Cap tool output size so large data previews cannot blow up client contexts.
try:
    from fastmcp.server.middleware.response_limiting import ResponseLimitingMiddleware

    mcp.add_middleware(ResponseLimitingMiddleware(max_size=300_000))
except ImportError:  # pragma: no cover - optional middleware on older fastmcp
    pass


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "datagouv-mcp-tn"})


register_tools(mcp)
