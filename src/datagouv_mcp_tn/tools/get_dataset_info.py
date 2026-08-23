from fastmcp import FastMCP
from pydantic import ValidationError

from datagouv_mcp_tn.helpers import api_client
from datagouv_mcp_tn.helpers.logging import log_tool
from datagouv_mcp_tn.helpers.mcp_tool_defaults import READ_ONLY_EXTERNAL_API_TOOL
from datagouv_mcp_tn.models.dataset import Dataset


def register_get_dataset_info_tool(mcp: FastMCP) -> None:
    @mcp.tool(
        title="Get dataset info",
        annotations=READ_ONLY_EXTERNAL_API_TOOL,
    )
    @log_tool
    async def get_dataset_info(dataset_id: str) -> str:
        """
        Get full metadata for a single dataset on data.gouv.tn.

        Args:
            dataset_id: Dataset ID or slug (from search_datasets results).

        Returns:
            Title, description, tags, organization, license, and update date.
            Next step: use list_dataset_resources to see the files.
        """
        try:
            raw = await api_client.get_dataset_details(dataset_id)
        except Exception as e:  # noqa: BLE001
            return f"Error: {e}"

        try:
            dataset = Dataset.from_api(raw)
        except ValidationError:
            return f"Error: Dataset with ID '{dataset_id}' not found."

        lines = [f"Dataset: {dataset.display_title}"]
        lines.append(f"ID: {dataset.id}")
        if dataset.slug:
            lines.append(f"Slug: {dataset.slug}")
        if dataset.description:
            description = " ".join(dataset.description.split())
            if len(description) > 1000:
                description = description[:997] + "..."
            lines.append(f"Description: {description}")
        organization = dataset.organization
        if organization and organization.name:
            lines.append(f"Organization: {organization.name}")
        if dataset.tags:
            lines.append(f"Tags: {', '.join(dataset.tags)}")
        if license_info := dataset.license:
            label = license_info.title or license_info.id
            if label:
                lines.append(f"License: {label}")
        if dataset.last_update:
            lines.append(f"Last update: {dataset.last_update}")
        lines.append(f"Resources: {len(dataset.resources)} file(s)")
        lines.append("Next step: use list_dataset_resources to see the files.")

        return "\n".join(lines)
