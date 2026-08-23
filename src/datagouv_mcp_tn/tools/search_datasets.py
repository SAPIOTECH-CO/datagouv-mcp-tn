import logging
from typing import Any

from fastmcp import FastMCP

from datagouv_mcp_tn.helpers import api_client
from datagouv_mcp_tn.helpers.i18n import (
    Language,
    MessageKey,
    resolve_language,
    translate,
)
from datagouv_mcp_tn.helpers.logging import MAIN_LOGGER_NAME, log_tool
from datagouv_mcp_tn.helpers.mcp_tool_defaults import READ_ONLY_EXTERNAL_API_TOOL
from datagouv_mcp_tn.helpers.query_cleaner import clean_search_query
from datagouv_mcp_tn.models.common import PaginationInfo

logger = logging.getLogger(MAIN_LOGGER_NAME)


def register_search_datasets_tool(mcp: FastMCP) -> None:
    @mcp.tool(
        title="Search datasets",
        annotations=READ_ONLY_EXTERNAL_API_TOOL,
    )
    @log_tool
    async def search_datasets(
        query: str,
        page: int = 1,
        page_size: int = 20,
        language: Language | None = None,
    ) -> str:
        """
        Search for datasets on data.gouv.tn by keywords.

        This is typically the first step in exploring the Tunisian open data
        portal. Use short, specific queries (French or Arabic work best; the
        API uses AND logic, so generic words may return zero results).

        Args:
            query: Search keywords.
            page: 1-based page number for pagination.
            page_size: Number of results per page (max 100).
            language: Output language (fr/ar/en); defaults to DEFAULT_LANGUAGE.

        Returns:
            A formatted list of matching datasets with their IDs so they can
            be passed to get_dataset_info or list_dataset_resources next.
        """
        lang = resolve_language(language)

        cleaned_query = clean_search_query(query)
        if not cleaned_query:
            return f"Error: {translate(MessageKey.GENERIC_QUERY_ERROR, lang)}"

        try:
            data = await api_client.search_datasets(cleaned_query, page=page, page_size=page_size)
        except Exception as e:  # noqa: BLE001
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

        return "\n".join(lines)
