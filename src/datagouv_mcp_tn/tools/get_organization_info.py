from fastmcp import FastMCP

from datagouv_mcp_tn.helpers import api_client
from datagouv_mcp_tn.helpers.logging import log_tool
from datagouv_mcp_tn.helpers.mcp_tool_defaults import READ_ONLY_EXTERNAL_API_TOOL
from datagouv_mcp_tn.portals import get_portal


def register_get_organization_info_tool(mcp: FastMCP) -> None:
    @mcp.tool(
        title="Get organization info",
        annotations=READ_ONLY_EXTERNAL_API_TOOL,
    )
    @log_tool
    async def get_organization_info(organization_id: str, portal: str | None = None) -> str:
        """
        Get full metadata for a single organization from a Tunisian CKAN portal.

        Args:
            organization_id: Organization ID or slug (from search_organizations results).
            portal: Portal key (data-gov-tn, industrie, culture, transport, agridata).
                   Defaults to configured default portal.

        Returns:
            Name, description, website, member count, and dataset count.
        """
        portal_obj = get_portal(portal)
        try:
            org = await api_client.get_organization_details(
                organization_id, portal_key=portal_obj.key
            )
        except api_client.CKANError as e:
            return f"Error: {e}"

        if not org.get("id"):
            return (
                f"Error: Organization with ID '{organization_id}' not found on {portal_obj.name}."
            )

        lines = [f"Organization: {org.get('name') or 'Unnamed'}"]
        lines.append(f"ID: {org['id']}")
        lines.append(f"Portal: {portal_obj.name}")
        if org.get("acronym"):
            lines.append(f"Acronym: {org['acronym']}")
        if org.get("description"):
            description = " ".join(org["description"].split())
            if len(description) > 800:
                description = description[:797] + "..."
            lines.append(f"Description: {description}")
        if org.get("url") or org.get("website"):
            lines.append(f"Website: {org.get('url') or org.get('website')}")
        metrics = org.get("metrics", {})
        if isinstance(metrics, dict):
            if metrics.get("members") is not None:
                lines.append(f"Members: {metrics['members']}")
            if metrics.get("datasets") is not None:
                lines.append(f"Datasets published: {metrics['datasets']}")

        return "\n".join(lines)
