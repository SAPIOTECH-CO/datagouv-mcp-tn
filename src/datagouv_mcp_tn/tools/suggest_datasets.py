from fastmcp import FastMCP

from datagouv_mcp_tn.helpers import api_client
from datagouv_mcp_tn.helpers.logging import log_tool
from datagouv_mcp_tn.helpers.mcp_tool_defaults import READ_ONLY_EXTERNAL_API_TOOL


def register_suggest_datasets_tool(mcp: FastMCP) -> None:
    @mcp.tool(
        title="Suggest datasets",
        annotations=READ_ONLY_EXTERNAL_API_TOOL,
    )
    @log_tool
    async def suggest_datasets(partial_query: str, size: int = 10) -> str:
        """
        Autocomplete dataset titles from a partial query.

        Lightweight alternative to search_datasets when the user is still
        typing or unsure of exact dataset names.

        Args:
            partial_query: Partial dataset title (a few letters suffice).
            size: Maximum number of suggestions (max 50).

        Returns:
            A plain list of matching titles. Use search_datasets afterwards
            to get full IDs and metadata.
        """
        try:
            suggestions = await api_client.suggest_datasets(partial_query, size=size)
        except Exception as e:  # noqa: BLE001
            return f"Error: {e}"

        if not suggestions:
            return f"No suggestions for '{partial_query}'."

        lines = [f"Suggestions for '{partial_query}':"]
        for item in suggestions:
            title = item.get("title") if isinstance(item, dict) else item
            if title:
                lines.append(f"- {title}")

        return "\n".join(lines)
