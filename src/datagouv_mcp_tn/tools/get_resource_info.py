from fastmcp import FastMCP

from datagouv_mcp_tn.helpers import api_client
from datagouv_mcp_tn.helpers.logging import log_tool
from datagouv_mcp_tn.helpers.mcp_tool_defaults import READ_ONLY_EXTERNAL_API_TOOL


def register_get_resource_info_tool(mcp: FastMCP) -> None:
    @mcp.tool(
        title="Get resource info",
        annotations=READ_ONLY_EXTERNAL_API_TOOL,
    )
    @log_tool
    async def get_resource_info(dataset_id: str, resource_id: str) -> str:
        """
        Get detailed metadata for a single resource (file) in a dataset.

        Args:
            dataset_id: Dataset ID or slug.
            resource_id: Resource ID (from list_dataset_resources results).

        Returns:
            Title, format, size, checksum, and download URL of the file.
        """
        try:
            resource = await api_client.get_resource_details(dataset_id, resource_id)
        except Exception as e:  # noqa: BLE001
            return f"Error: {e}"

        lines = [f"Resource: {resource.get('title') or resource.get('name') or 'Untitled'}"]
        lines.append(f"Resource ID: {resource['id']}")
        if resource.get("format"):
            lines.append(f"Format: {resource['format']}")
        if resource.get("mime"):
            lines.append(f"MIME type: {resource['mime']}")
        filesize = resource.get("filesize")
        if isinstance(filesize, int):
            lines.append(f"Size: {filesize} bytes")
        checksum = resource.get("checksum")
        if isinstance(checksum, dict) and checksum.get("value"):
            lines.append(f"Checksum ({checksum.get('type', 'sha1')}): {checksum['value']}")
        if resource.get("url"):
            lines.append(f"URL: {resource['url']}")

        return "\n".join(lines)
