from fastmcp import FastMCP

from datagouv_mcp_tn.tools.get_dataset_info import register_get_dataset_info_tool
from datagouv_mcp_tn.tools.get_organization_info import (
    register_get_organization_info_tool,
)
from datagouv_mcp_tn.tools.get_resource_info import register_get_resource_info_tool
from datagouv_mcp_tn.tools.list_dataset_resources import (
    register_list_dataset_resources_tool,
)
from datagouv_mcp_tn.tools.search_datasets import register_search_datasets_tool
from datagouv_mcp_tn.tools.search_organizations import (
    register_search_organizations_tool,
)
from datagouv_mcp_tn.tools.suggest_datasets import register_suggest_datasets_tool


def register_tools(mcp: FastMCP) -> None:
    """Register all MCP tools with the provided FastMCP instance."""
    register_search_datasets_tool(mcp)
    register_suggest_datasets_tool(mcp)
    register_get_dataset_info_tool(mcp)
    register_list_dataset_resources_tool(mcp)
    register_get_resource_info_tool(mcp)
    register_search_organizations_tool(mcp)
    register_get_organization_info_tool(mcp)
