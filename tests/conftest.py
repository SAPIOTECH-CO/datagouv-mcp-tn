"""Test configuration and fixtures for isolated FastMCP instances."""

import pytest
from fastmcp import Client as FastMCPClient
from fastmcp import FastMCP

from datagouv_mcp_tn.helpers.config import Settings
from datagouv_mcp_tn.helpers.logging_config import configure_logging
from datagouv_mcp_tn.prompts import register_prompts
from datagouv_mcp_tn.tools import register_tools


def create_test_mcp() -> FastMCP:
    """Create a fresh FastMCP instance for testing with all tools and prompts registered."""
    # Use test settings
    test_settings = Settings(
        strict_input_validation=True,
        rate_limit_enabled=False,  # Disable rate limiting in tests
        cors_enabled=False,
        host_origin_protection=False,
        log_sanitization_enabled=True,
        log_level="DEBUG",
    )

    # Configure logging for test
    configure_logging(test_settings.log_level)

    mcp = FastMCP(
        "datagouv-mcp-tn MCP server (test)",
        instructions=(
            "Tools for exploring any CKAN open data portal. Start with "
            "search_datasets or search_organizations, then drill into datasets with "
            "get_dataset_info and list_dataset_resources. Tabular resources can "
            "be analyzed in memory with download_and_parse_resource and "
            "query_resource_data. Use the `portal` parameter to target a specific "
            "portal (default: configured default portal)."
        ),
        strict_input_validation=test_settings.strict_input_validation,
    )

    # Register all tools and prompts
    register_tools(mcp)
    register_prompts(mcp)

    return mcp


@pytest.fixture
async def mcp_client():
    """Provide a FastMCP client connected to a fresh test server."""
    mcp = create_test_mcp()
    async with FastMCPClient(mcp) as client:
        yield client


@pytest.fixture
def mcp_server():
    """Provide a fresh MCP server instance for testing."""
    return create_test_mcp()
