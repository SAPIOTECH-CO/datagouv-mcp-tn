from fastmcp import FastMCP

from datagouv_mcp_tn.helpers import api_client
from datagouv_mcp_tn.helpers.logging import log_tool
from datagouv_mcp_tn.helpers.mcp_tool_defaults import READ_ONLY_EXTERNAL_API_TOOL
from datagouv_mcp_tn.models.resource import Resource
from datagouv_mcp_tn.portals import get_portal


def register_get_resource_info_tool(mcp: FastMCP) -> None:
    @mcp.tool(
        title="Get resource info",
        annotations=READ_ONLY_EXTERNAL_API_TOOL,
    )
    @log_tool
    async def get_resource_info(
        dataset_id: str, resource_id: str, portal: str | None = None
    ) -> str:
        """
        Get detailed metadata for a single resource (file) in a dataset.

        Args:
            dataset_id: Dataset ID or slug.
            resource_id: Resource ID (from list_dataset_resources results).
            portal: Portal key (data-gov-tn, industrie, culture, transport, agridata).
                   Defaults to configured default portal.

        Returns:
            Title, format, size, checksum, and download URL of the file.
        """
        portal_obj = get_portal(portal)
        try:
            raw = await api_client.get_resource_details(
                dataset_id, resource_id, portal_key=portal_obj.key
            )
            resource = Resource.from_api(raw)
        except api_client.CKANError as e:
            return f"Error: {e}"

        lines = [f"Resource: {resource.display_title}"]
        lines.append(f"Resource ID: {resource.id}")
        lines.append(f"Portal: {portal_obj.name}")
        if resource.format:
            lines.append(f"Format: {resource.format}")
        if resource.mime:
            lines.append(f"MIME type: {resource.mime}")
        if size := resource.human_size:
            raw_size = f"{resource.filesize} bytes"
            lines.append(f"Size: {size} ({raw_size})")
        if checksum := resource.checksum:
            if checksum.value:
                lines.append(f"Checksum ({checksum.type}): {checksum.value}")
        if resource.url:
            lines.append(f"URL: {resource.url}")

        return "\n".join(lines)
