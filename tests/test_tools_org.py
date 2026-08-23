"""Tests for get_organization_info tool."""

from unittest.mock import AsyncMock, patch

import pytest

from datagouv_mcp_tn.helpers import api_client
from datagouv_mcp_tn.helpers.api_client import CKANError

ORG_DETAIL = {
    "id": "org-1",
    "name": "Institut National de la Statistique",
    "acronym": "INS",
    "description": "Tunisia's national statistics agency.",
    "url": "https://ins.tn",
    "metrics": {"members": 12, "datasets": 45},
}


@pytest.fixture
async def call_tool(mcp_client):
    async def _call(name: str, arguments: dict) -> str:
        result = await mcp_client.call_tool(name, arguments)
        part = result.content[0]
        assert part.type == "text"
        return part.text
    return _call


async def test_get_organization_info_shows_metadata(call_tool):
    with patch.object(
        api_client, "get_organization_details", new=AsyncMock(return_value=ORG_DETAIL)
    ):
        text = await call_tool("get_organization_info", {"organization_id": "org-1"})
    assert "Institut National de la Statistique" in text
    assert "Acronym: INS" in text
    assert "Website: https://ins.tn" in text
    assert "Members: 12" in text
    assert "Datasets published: 45" in text


async def test_get_organization_info_handles_api_error(call_tool):
    with patch.object(
        api_client,
        "get_organization_details",
        new=AsyncMock(side_effect=CKANError("connection refused")),
    ):
        text = await call_tool("get_organization_info", {"organization_id": "org-1"})
    assert text.startswith("Error:")
    assert "connection refused" in text


async def test_get_organization_info_handles_missing_org(call_tool):
    with patch.object(
        api_client, "get_organization_details", new=AsyncMock(return_value={})
    ):
        text = await call_tool("get_organization_info", {"organization_id": "missing"})
    assert "not found" in text
