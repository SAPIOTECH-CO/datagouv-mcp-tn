"""Tests for MCP resource handlers."""

import json
from unittest.mock import patch

import pytest

from datagouv_mcp_tn.helpers.resources import (
    get_api_docs,
    get_config,
    get_portal_info,
    get_portals_registry,
    get_schema,
)


@pytest.mark.asyncio
async def test_get_config_returns_json():
    with patch("datagouv_mcp_tn.helpers.resources.get_settings") as mock_settings:
        mock_settings.return_value.default_portal = "agridata"
        mock_settings.return_value.request_timeout = 30.0
        mock_settings.return_value.request_max_retries = 2
        mock_settings.return_value.retry_backoff_seconds = 0.5
        mock_settings.return_value.download_timeout = 120.0
        mock_settings.return_value.max_download_size_mb = 50
        mock_settings.return_value.default_language = "fr"
        mock_settings.return_value.log_level = "INFO"
        mock_settings.return_value.strict_input_validation = True
        mock_settings.return_value.rate_limit_enabled = True
        mock_settings.return_value.rate_limit_max_requests = 100
        mock_settings.return_value.rate_limit_window_minutes = 1
        mock_settings.return_value.cors_enabled = True
        mock_settings.return_value.host_origin_protection = True
        mock_settings.return_value.log_sanitization_enabled = True

        result = await get_config()

    config = json.loads(result)
    assert config["default_portal"] == "agridata"
    assert config["request_timeout"] == 30.0
    assert config["log_level"] == "INFO"


@pytest.mark.asyncio
async def test_get_schema_returns_string():
    result = await get_schema()
    assert "CKAN Action API Schema Reference" in result
    assert "Package (Dataset) Object" in result


@pytest.mark.asyncio
async def test_get_portals_registry_lists_all_portals():
    result = await get_portals_registry()
    assert "CKAN Portals Registry" in result
    assert "agridata" in result
    assert "data-gov-tn" in result


@pytest.mark.asyncio
async def test_get_portal_info_returns_portal_details():
    result = await get_portal_info("agridata")
    assert "Ministry of Agriculture" in result
    assert "catalog.agridata.tn" in result


@pytest.mark.asyncio
async def test_get_api_docs_returns_portal_specific_docs():
    result = await get_api_docs("agridata")
    assert "catalog.agridata.tn/api/3" in result
    assert "package_search" in result
