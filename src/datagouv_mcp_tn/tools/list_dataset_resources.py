from fastmcp import FastMCP
from fastmcp.tools import ToolResult
from pydantic import ValidationError

from datagouv_mcp_tn.helpers import api_client
from datagouv_mcp_tn.helpers.logging import log_tool
from datagouv_mcp_tn.helpers.mcp_tool_defaults import READ_ONLY_EXTERNAL_API_TOOL
from datagouv_mcp_tn.helpers.prefab_views import resources_table
from datagouv_mcp_tn.models.dataset import Dataset


def register_list_dataset_resources_tool(mcp: FastMCP) -> None:
    @mcp.tool(
        title="List dataset resources",
        annotations=READ_ONLY_EXTERNAL_API_TOOL,
        app=True,
    )
    @log_tool
    async def list_dataset_resources(dataset_id: str) -> str | ToolResult:
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
            raw = await api_client.get_dataset_details(dataset_id)
        except Exception as e:  # noqa: BLE001
            return f"Error: {e}"

        try:
            dataset = Dataset.from_api(raw)
        except ValidationError:
            return f"Error: Dataset with ID '{dataset_id}' not found."

        resources = dataset.resources
        lines = [
            f"Resources in dataset: {dataset.display_title}",
            f"Dataset ID: {dataset.id}",
            f"Total resources: {len(resources)}\n",
        ]

        if not resources:
            lines.append("This dataset has no resources.")
            return "\n".join(lines)

        for i, resource in enumerate(resources, 1):
            lines.append(f"{i}. {resource.display_title}")
            lines.append(f"   Resource ID: {resource.id}")
            if resource.format:
                lines.append(f"   Format: {resource.format}")
            if size := resource.human_size:
                lines.append(f"   Size: {size}")
            if resource.mime:
                lines.append(f"   MIME type: {resource.mime}")
            if resource.url:
                lines.append(f"   URL: {resource.url}")
            lines.append("")

        return ToolResult(content="\n".join(lines), structured_content=resources_table(resources))
