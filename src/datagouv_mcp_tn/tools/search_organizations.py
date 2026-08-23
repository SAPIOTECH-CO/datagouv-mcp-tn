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
from datagouv_mcp_tn.helpers.prefab_views import organizations_table
from datagouv_mcp_tn.helpers.validators import validate_search_args
from datagouv_mcp_tn.models.common import PaginationInfo


def register_search_organizations_tool(mcp: FastMCP) -> None:
    @mcp.tool(
        title="Search organizations",
        annotations=READ_ONLY_EXTERNAL_API_TOOL,
        app=True,
    )
    @log_tool
    async def search_organizations(
        query: str,
        page: int = 1,
        page_size: int = 20,
        language: Language | None = None,
    ) -> str | ToolResult:
        """
        Search for publishing organizations (ministries, agencies...) on data.gouv.tn.

        Args:
            query: Search keywords.
            page: 1-based page number for pagination.
            page_size: Number of results per page (max 100).
            language: Output language (fr/ar/en); defaults to DEFAULT_LANGUAGE.

        Returns:
            A formatted list of matching organizations with their IDs so they
            can be passed to get_organization_info next.
        """
        lang = resolve_language(language)
        query, page, page_size, lang = validate_search_args(query, page, page_size, lang)

        try:
            data = await api_client.search_organizations(query, page=page, page_size=page_size)
        except Exception as e:  # noqa: BLE001
            return f"Error: {e}"

        results = data.get("data", [])
        pagination = PaginationInfo.from_udata(data, default_page=page, default_page_size=page_size)
        lines = [
            translate(
                MessageKey.RESULTS_FOUND,
                lang,
                count=pagination.total,
                what=translate(MessageKey.WHAT_ORGANIZATIONS, lang),
                query=query,
            ),
            pagination.describe(lang),
            "",
        ]

        if not results:
            lines.append(translate(MessageKey.NO_RESULTS, lang))
            return "\n".join(lines)

        for i, org in enumerate(results, 1):
            name = org.get("name") or "Unnamed"
            lines.append(f"{i}. {name}")
            if org.get("id"):
                lines.append(f"   Organization ID: {org['id']}")
            if org.get("acronym"):
                lines.append(f"   Acronym: {org['acronym']}")
            lines.append("")

        return ToolResult(content="\n".join(lines), structured_content=organizations_table(results))
