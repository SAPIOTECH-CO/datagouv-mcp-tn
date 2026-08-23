from fastmcp import FastMCP
from pydantic import ValidationError

from datagouv_mcp_tn.helpers import api_client
from datagouv_mcp_tn.helpers.logging import log_tool
from datagouv_mcp_tn.helpers.mcp_tool_defaults import READ_ONLY_EXTERNAL_API_TOOL
from datagouv_mcp_tn.models.dataservice import Dataservice
from datagouv_mcp_tn.portals import get_portal

_DESCRIPTION_LIMIT = 500


def register_get_dataservice_info_tool(mcp: FastMCP) -> None:
    @mcp.tool(
        title="Get dataservice info",
        annotations=READ_ONLY_EXTERNAL_API_TOOL,
    )
    @log_tool
    async def get_dataservice_info(dataservice_id: str, portal: str | None = None) -> str:
        """
        Get full metadata for a single dataservice (API) from a Tunisian CKAN portal.

        Args:
            dataservice_id: Dataservice ID or slug (from search_dataservices).
            portal: Portal key (data-gov-tn, industrie, culture, transport, agridata).
                   Defaults to configured default portal.

        Returns:
            Title, description, base API URL, endpoints, and update date.
            Next step: use get_dataservice_openapi_spec to explore its schema.
        """
        portal_obj = get_portal(portal)
        try:
            raw = await api_client.get_dataservice_details(
                dataservice_id, portal_key=portal_obj.key
            )
        except api_client.CKANError as e:
            return f"Error: {e}"

        try:
            service = Dataservice.from_api(raw)
        except ValidationError:
            return f"Error: Dataservice with ID '{dataservice_id}' not found on {portal_obj.name}."

        lines = [f"Dataservice: {service.display_title}"]
        lines.append(f"ID: {service.id}")
        lines.append(f"Portal: {portal_obj.name}")
        if service.description:
            description = " ".join(service.description.split())
            if len(description) > _DESCRIPTION_LIMIT:
                description = description[: _DESCRIPTION_LIMIT - 3] + "..."
            lines.append(f"Description: {description}")
        if service.base_api_url:
            lines.append(f"Base API URL: {service.base_api_url}")
        if service.organization and service.organization.name:
            lines.append(f"Organization: {service.organization.name}")
        for endpoint in service.endpoints:
            label = endpoint.name or "Endpoint"
            if endpoint.url:
                lines.append(f"Endpoint ({label}): {endpoint.url}")
        if service.openapi_spec_url:
            lines.append(f"OpenAPI spec URL: {service.openapi_spec_url}")
        else:
            lines.append("Next step: use get_dataservice_openapi_spec to inspect the API schema.")
        if service.last_update:
            lines.append(f"Last update: {service.last_update}")

        return "\n".join(lines)
