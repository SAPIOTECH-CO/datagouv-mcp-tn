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
        "get_dataset_info and list_dataset_resources."
    ),
)


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "datagouv-mcp-tn"})


register_tools(mcp)
