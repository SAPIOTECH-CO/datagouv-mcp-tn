from fastmcp import FastMCP

from datagouv_mcp_tn.helpers import api_client
from datagouv_mcp_tn.helpers.logging import log_tool
from datagouv_mcp_tn.helpers.mcp_tool_defaults import READ_ONLY_EXTERNAL_API_TOOL


def _human_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    if size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    return f"{size / (1024 * 1024 * 1024):.1f} GB"


def register_list_dataset_resources_tool(mcp: FastMCP) -> None:
    @mcp.tool(
        title="List dataset resources",
        annotations=READ_ONLY_EXTERNAL_API_TOOL,
    )
    @log_tool
    async def list_dataset_resources(dataset_id: str) -> str:
        """
        List all resources (files) in a dataset with their metadata.

        Args:
            dataset_id: Dataset ID or slug (from search_datasets results).

        Returns:
            Resource ID, title, format, size, and URL for each file.
            Next step: use get_resource_info with a Resource ID, or fetch the
            resource URL directly.
        """
        try:
            dataset = await api_client.get_dataset_details(dataset_id)
        except Exception as e:  # noqa: BLE001
            return f"Error: {e}"

        if not dataset.get("id"):
            return f"Error: Dataset with ID '{dataset_id}' not found."

        resources = dataset.get("resources", [])
        lines = [
            f"Resources in dataset: {dataset.get('title', 'Unknown')}",
            f"Dataset ID: {dataset_id}",
            f"Total resources: {len(resources)}\n",
        ]

        if not resources:
            lines.append("This dataset has no resources.")
            return "\n".join(lines)

        for i, resource in enumerate(resources, 1):
            resource_id = resource.get("id")
            if not resource_id:
                continue
            title = resource.get("title") or resource.get("name")
            lines.append(f"{i}. {title or 'Untitled'}")
            lines.append(f"   Resource ID: {resource_id}")
            if resource.get("format"):
                lines.append(f"   Format: {resource['format']}")
            filesize = resource.get("filesize")
            if isinstance(filesize, int):
                lines.append(f"   Size: {_human_size(filesize)}")
            if resource.get("mime"):
                lines.append(f"   MIME type: {resource['mime']}")
            if resource.get("url"):
                lines.append(f"   URL: {resource['url']}")
            lines.append("")

        return "\n".join(lines)
