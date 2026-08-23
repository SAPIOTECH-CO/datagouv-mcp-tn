from fastmcp import FastMCP

from datagouv_mcp_tn.helpers import api_client
from datagouv_mcp_tn.helpers.i18n import (
    Language,
    MessageKey,
    resolve_language,
    translate,
)
from datagouv_mcp_tn.helpers.logging import log_tool
from datagouv_mcp_tn.helpers.mcp_tool_defaults import READ_ONLY_EXTERNAL_API_TOOL


def register_suggest_datasets_tool(mcp: FastMCP) -> None:
    @mcp.tool(
        title="Suggest datasets",
        annotations=READ_ONLY_EXTERNAL_API_TOOL,
    )
    @log_tool
    async def suggest_datasets(
        partial_query: str,
        size: int = 10,
        language: Language | None = None,
    ) -> str:
        """
        Autocomplete dataset titles from a partial query.

        Lightweight alternative to search_datasets when the user is still
        typing or unsure of exact dataset names.

        Args:
            partial_query: Partial dataset title (a few letters suffice).
            size: Maximum number of suggestions (max 50).
            language: Output language (fr/ar/en); defaults to DEFAULT_LANGUAGE.

        Returns:
            A plain list of matching titles. Use search_datasets afterwards
            to get full IDs and metadata.
        """
        lang = resolve_language(language)

        try:
            suggestions = await api_client.suggest_datasets(partial_query, size=size)
        except Exception as e:  # noqa: BLE001
            return f"Error: {e}"

        if not suggestions:
            return translate(MessageKey.NO_SUGGESTIONS, lang)

        lines = [translate(MessageKey.SUGGESTIONS_TITLE, lang, query=partial_query)]
        for item in suggestions:
            title = item.get("title") if isinstance(item, dict) else item
            if title:
                lines.append(f"- {title}")

        return "\n".join(lines)
