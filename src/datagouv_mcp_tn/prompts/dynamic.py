"""Dynamic prompt templates for the CKAN open data MCP server.

Prompts use FastMCP's ``@mcp.prompt`` decorator with ``Context`` injection
so they can access runtime server state (default portal, language preference,
available portals) without hardcoding any data source.
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP
from fastmcp.server.context import Context

from datagouv_mcp_tn.helpers.config import get_settings
from datagouv_mcp_tn.portals import get_portal, list_portals


def _portal_context(ctx: Context) -> dict[str, Any]:
    """Build a context dict describing the current portal environment."""
    settings = get_settings()
    portal = get_portal(settings.default_portal)
    return {
        "default_portal_key": portal.key,
        "default_portal_name": portal.name,
        "default_portal_api_url": portal.api_url,
        "default_portal_catalog_url": portal.catalog_url,
        "default_language": settings.default_language,
        "available_portals": list_portals(),
    }


# ---------------------------------------------------------------------------
# Prompt 1: explore_portal
# ---------------------------------------------------------------------------


def register_explore_portal_prompt(mcp: FastMCP) -> None:
    @mcp.prompt
    async def explore_portal(ctx: Context, portal_key: str | None = None) -> str:
        """Guide the user through exploring a CKAN open data portal.

        Use this when the user wants to discover what data is available on
        a specific portal, browse datasets by topic, or understand the
        portal's structure.
        """
        info = _portal_context(ctx)
        key = portal_key or info["default_portal_key"]
        portal = get_portal(key)

        portal_list = "\n".join(f"  - {p['key']}: {p['name']}" for p in info["available_portals"])

        return (
            f"You are an open data assistant for CKAN portals.\n\n"
            f"Current default portal: {info['default_portal_name']} "
            f"(key: {info['default_portal_key']})\n"
            f"API base: {portal.api_url}\n"
            f"Catalog UI: {portal.catalog_url}\n\n"
            f"Available portals:\n{portal_list}\n\n"
            f"Suggested workflow:\n"
            f"1. Start with `search_datasets` or `search_organizations` to discover data.\n"
            f"2. Use `get_dataset_info` or `get_organization_info` for details.\n"
            f"3. Use `list_dataset_resources` to see available files.\n"
            f"4. Use `download_and_parse_resource` +\n"
            f"   `query_resource_data` to analyze tabular data.\n"
            f"5. Use `get_metrics` for usage statistics.\n\n"
            f"All tools accept an optional `portal` parameter (portal key) to override "
            f"the default portal. Use this when the user explicitly asks about a "
            f"different portal."
        )


# ---------------------------------------------------------------------------
# Prompt 2: search_and_analyze
# ---------------------------------------------------------------------------


def register_search_and_analyze_prompt(mcp: FastMCP) -> None:
    @mcp.prompt
    async def search_and_analyze(
        ctx: Context,
        topic: str,
        portal_key: str | None = None,
    ) -> str:
        """Search for datasets on a topic and guide analysis of tabular resources.

        Use this when the user asks to find data about a specific subject
        and wants to analyze it (e.g. 'find agricultural data and show trends').
        """
        info = _portal_context(ctx)
        key = portal_key or info["default_portal_key"]
        portal = get_portal(key)

        return (
            f'The user wants to find and analyze data about: "{topic}".\n\n'
            f"Target portal: {portal.name} (key: {portal.key})\n"
            f"API: {portal.api_url}\n\n"
            f"Follow this flow:\n"
            f'1. Call `search_datasets` with query="{topic}" and portal="{portal.key}".\n'
            f"2. Pick the most relevant dataset from the results.\n"
            f"3. Call `get_dataset_info` with that dataset ID.\n"
            f"4. Call `list_dataset_resources` to find tabular files (CSV, XLSX, ODS, JSON).\n"
            f"5. Call `download_and_parse_resource` to load the data in memory.\n"
            f"6. Call `query_resource_data` with a specific analysis question.\n\n"
            f"If no datasets are found, try a broader query or suggest switching portal "
            f"using the `portal` parameter."
        )


# ---------------------------------------------------------------------------
# Prompt 3: discover_portals
# ---------------------------------------------------------------------------


def register_discover_portals_prompt(mcp: FastMCP) -> None:
    @mcp.prompt
    async def discover_portals(ctx: Context) -> str:
        """Help the user discover and compare available CKAN portals.

        Use this when the user is unsure which portal to use, or wants to
        compare data availability across multiple portals.
        """
        info = _portal_context(ctx)
        portals = info["available_portals"]

        portal_descriptions = "\n".join(
            f"- **{p['key']}** ({p['name']})\n"
            f"  API: {p['api_url']}\n"
            f"  UI: {p['catalog_url']}\n"
            f"  {p.get('description', '')}"
            for p in portals
        )

        return (
            f"Available CKAN portals:\n\n{portal_descriptions}\n\n"
            f"Guidance:\n"
            f"- Use `search_datasets` with `portal=<key>` to query a specific portal.\n"
            f"- Use `search_organizations` to see publishers on a portal.\n"
            f"- Use `get_metrics` to compare usage across portals.\n"
            f"- The default portal is `{info['default_portal_key']}`.\n"
            f"- To add a new portal, set the `PORTAL_<KEY>_API_URL` environment variable."
        )


# ---------------------------------------------------------------------------
# Prompt 4: analyze_resource
# ---------------------------------------------------------------------------


def register_analyze_resource_prompt(mcp: FastMCP) -> None:
    @mcp.prompt
    async def analyze_resource(
        ctx: Context,
        resource_hint: str = "",
        portal_key: str | None = None,
    ) -> str:
        """Guide the user through analyzing a specific resource file.

        Use this when the user has a resource ID or URL and wants to inspect,
        parse, and query its contents.
        """
        info = _portal_context(ctx)
        key = portal_key or info["default_portal_key"]
        portal = get_portal(key)

        hint_section = ""
        if resource_hint:
            hint_section = (
                f'\nResource hint provided: "{resource_hint}". Use this to narrow the search.\n'
            )

        return (
            f"Resource analysis workflow for portal {portal.name}:\n"
            f"{hint_section}"
            f"1. If you have a dataset ID, call `list_dataset_resources` to list files.\n"
            f"2. If you have a resource ID, call `get_resource_info` to inspect it.\n"
            f"3. Call `download_and_parse_resource` with the resource URL or ID.\n"
            f"4. Once loaded, use `query_resource_data` to ask questions about the data.\n\n"
            f"Supported formats: CSV, XLSX, ODS, JSON, GeoJSON (tabular); "
            f"PDF, DOCX, PPTX, HTML, XML, images (via document inspector)."
        )


# ---------------------------------------------------------------------------
# Prompt 5: workflow_assistant
# ---------------------------------------------------------------------------


def register_workflow_assistant_prompt(mcp: FastMCP) -> None:
    @mcp.prompt
    async def workflow_assistant(ctx: Context) -> str:
        """General assistant prompt for navigating CKAN open data portals.

        This is the default entry point. Use it to orient the user and
        suggest the right tools for their task.
        """
        info = _portal_context(ctx)
        return (
            "You are an open data assistant connected to a CKAN MCP server.\n\n"
            f"Default portal: {info['default_portal_name']} "
            f"(key: {info['default_portal_key']})\n"
            f"Language: {info['default_language']}\n\n"
            "Available tools:\n"
            "- search_datasets / suggest_datasets: discover datasets\n"
            "- get_dataset_info: full dataset metadata\n"
            "- list_dataset_resources: list files in a dataset\n"
            "- get_resource_info: resource metadata\n"
            "- search_organizations / get_organization_info: publishers\n"
            "- search_dataservices / get_dataservice_info: published APIs\n"
            "- download_and_parse_resource: load files in memory\n"
            "- query_resource_data: analyze tabular data\n"
            "- get_metrics: usage statistics\n\n"
            "Available resources (read via ckan:// URIs):\n"
            "- ckan://api/docs: CKAN API reference\n"
            "- ckan://schema: object schemas\n"
            "- ckan://config: server configuration\n"
            "- ckan://portals/{key}: specific portal info\n\n"
            "Start by understanding what the user wants to find or analyze, "
            "then use the appropriate tool sequence."
        )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register_prompts(mcp: FastMCP) -> None:
    """Register all dynamic prompt templates with the FastMCP instance."""
    register_explore_portal_prompt(mcp)
    register_search_and_analyze_prompt(mcp)
    register_discover_portals_prompt(mcp)
    register_analyze_resource_prompt(mcp)
    register_workflow_assistant_prompt(mcp)
