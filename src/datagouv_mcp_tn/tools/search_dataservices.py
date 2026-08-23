from fastmcp import FastMCP
from fastmcp.tools import ToolResult

from datagouv_mcp_tn.helpers import api_client
from datagouv_mcp_tn.helpers.i18n import (
    Language,
    MessageKey,
    resolve_language,
    translate,
)
from datagouv_mcp_tn.helpers.logging import log_tool
from datagouv_mcp_tn.helpers.mcp_tool_defaults import READ_ONLY_EXTERNAL_API_TOOL
from datagouv_mcp_tn.helpers.prefab_views import dataservices_table
from datagouv_mcp_tn.models.common import PaginationInfo


def register_search_dataservices_tool(mcp: FastMCP) -> None:
    @mcp.tool(
        title="Search dataservices",
        annotations=READ_ONLY_EXTERNAL_API_TOOL,
        app=True,
    )
    @log_tool
    async def search_dataservices(
        query: str,
        page: int = 1,
        page_size: int = 20,
        language: Language | None = None,
    ) -> str | ToolResult:
        """
        Search for dataservices (published APIs) on data.gouv.tn.

        Args:
            query: Search keywords.
            page: 1-based page number for pagination.
            page_size: Number of results per page (max 100).
            language: Output language (fr/ar/en); defaults to DEFAULT_LANGUAGE.

        Returns:
            A formatted list of matching dataservices with their IDs so they
            can be passed to get_dataservice_info next.
        """
        lang = resolve_language(language)

        try:
            data = await api_client.search_dataservices(query, page=page, page_size=page_size)
        except Exception as e:  # noqa: BLE001
            return f"Error: {e}"

        results = data.get("data", [])
        pagination = PaginationInfo.from_udata(data, default_page=page, default_page_size=page_size)
        lines = [
            translate(
                MessageKey.RESULTS_FOUND,
                lang,
                count=pagination.total,
                what=translate(MessageKey.WHAT_DATASERVICES, lang),
                query=query,
            ),
            pagination.describe(lang),
            "",
        ]

        if not results:
            lines.append(translate(MessageKey.NO_RESULTS, lang))
            return "\n".join(lines)

        for i, service in enumerate(results, 1):
            title = service.get("title") or service.get("name") or "Unnamed"
            lines.append(f"{i}. {title}")
            if service.get("id"):
                lines.append(f"   Dataservice ID: {service['id']}")
            if service.get("base_api_url"):
                lines.append(f"   Base URL: {service['base_api_url']}")
            lines.append("")

        return ToolResult(content="\n".join(lines), structured_content=dataservices_table(results))
