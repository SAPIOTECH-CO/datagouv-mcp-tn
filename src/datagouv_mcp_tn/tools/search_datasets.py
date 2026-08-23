import logging
from typing import Any

from fastmcp import FastMCP
from fastmcp.tools import ToolResult

from datagouv_mcp_tn.helpers import api_client
from datagouv_mcp_tn.helpers.i18n import (
    Language,
    MessageKey,
    resolve_language,
    translate,
)
from datagouv_mcp_tn.helpers.logging import MAIN_LOGGER_NAME, log_tool
from datagouv_mcp_tn.helpers.mcp_tool_defaults import READ_ONLY_EXTERNAL_API_TOOL
from datagouv_mcp_tn.helpers.prefab_views import search_results_table
from datagouv_mcp_tn.helpers.query_cleaner import clean_search_query
from datagouv_mcp_tn.helpers.validators import validate_search_args
from datagouv_mcp_tn.models.common import PaginationInfo
from datagouv_mcp_tn.portals import get_portal

logger = logging.getLogger(MAIN_LOGGER_NAME)


def register_search_datasets_tool(mcp: FastMCP) -> None:
    @mcp.tool(
        title="Search datasets",
        annotations=READ_ONLY_EXTERNAL_API_TOOL,
        app=True,
    )
    @log_tool
    async def search_datasets(
        query: str,
        page: int = 1,
        page_size: int = 20,
        language: Language | None = None,
        portal: str | None = None,
    ) -> str | ToolResult:
        """
        Search for datasets across Tunisian CKAN open data portals.

        Use short, specific queries (French or Arabic work best; the
        API uses AND logic, so generic words may return zero results).

        Args:
            query: Search keywords.
            page: 1-based page number for pagination.
            page_size: Number of results per page (max 100).
            language: Output language (fr/ar/en); defaults to DEFAULT_LANGUAGE.
            portal: Portal key (data-gov-tn, industrie, culture, transport, agridata).
                   Defaults to configured default portal.

        Returns:
            A formatted list of matching datasets with their IDs so they can
            be passed to get_dataset_info or list_dataset_resources next.
        """
        lang = resolve_language(language)

        # Validate and sanitize all inputs
        query, page, page_size, lang = validate_search_args(query, page, page_size, lang)

        # Resolve portal
        portal_obj = get_portal(portal)

        cleaned_query = clean_search_query(query)
        if not cleaned_query:
            return f"Error: {translate(MessageKey.GENERIC_QUERY_ERROR, lang)}"

        try:
            data = await api_client.search_datasets(
                cleaned_query, page=page, page_size=page_size, portal_key=portal_obj.key
            )
        except api_client.CKANError as e:
            return f"Error: {e}"

        results: list[dict[str, Any]] = data.get("data", [])
        pagination = PaginationInfo.from_udata(data, default_page=page, default_page_size=page_size)
        lines = [
            translate(
                MessageKey.RESULTS_FOUND,
                lang,
                count=pagination.total,
                what=translate(MessageKey.WHAT_DATASETS, lang),
                query=cleaned_query,
            ),
            pagination.describe(lang),
            f"Portal: {portal_obj.name}",
            "",
        ]

        if not results:
            lines.append(translate(MessageKey.NO_RESULTS, lang))
            return "\n".join(lines)

        for i, dataset in enumerate(results, 1):
            title = dataset.get("title") or "Untitled"
            lines.append(f"{i}. {title}")
            if dataset.get("id"):
                lines.append(f"   Dataset ID: {dataset['id']}")
            if dataset.get("description"):
                description = " ".join(dataset["description"].split())
                if len(description) > 200:
                    description = description[:197] + "..."
                lines.append(f"   Description: {description}")

        return ToolResult(
            content="\n".join(lines), structured_content=search_results_table(results)
        )
