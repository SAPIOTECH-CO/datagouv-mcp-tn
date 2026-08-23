"""Tests for Prefab UI views and the ToolResult wiring in app tools."""

from unittest.mock import AsyncMock, patch

from fastmcp import Client

from datagouv_mcp_tn.helpers import api_client
from datagouv_mcp_tn.helpers.prefab_views import (
    metrics_view,
    resources_table,
    search_results_table,
)
from datagouv_mcp_tn.models.dataset import Resource
from datagouv_mcp_tn.server import mcp


def test_search_results_table_builds():
    view = search_results_table(
        [
            {"title": "Recensement", "id": "abc-1", "description": "Population  " * 30},
            {"title": None, "id": None},
        ]
    )
    assert view is not None


def test_resources_table_builds():
    resources = Resource.from_api_list(
        [
            {"id": "r1", "title": "Pop CSV", "format": "csv"},
            {"id": "r2", "title": "Rapport PDF", "format": "pdf"},
        ]
    )
    view = resources_table(resources)
    assert view is not None


def test_metrics_view_with_values_and_empty():
    assert metrics_view("dataset", "x", {"views": 1200, "followers": 3}) is not None
    assert metrics_view("dataset", "x", {}) is not None
    # booleans are not chartable numerics
    assert metrics_view("dataset", "x", {"private": True}) is not None


def _text_of(result) -> str:
    part = result.content[0]
    assert part.type == "text"
    return str(getattr(part, "text", ""))


async def test_search_datasets_returns_tool_result():
    page = {
        "data": [{"id": "d1", "title": "Dataset Un", "description": "Desc"}],
        "total": 1,
        "page": 1,
        "page_size": 20,
    }
    async with Client(mcp) as client:
        with patch.object(api_client, "search_datasets", new=AsyncMock(return_value=page)):
            result = await client.call_tool("search_datasets", {"query": "recensement"})
    assert "Dataset Un" in _text_of(result)
    # structured_content carries the Prefab view alongside the text
    assert result.structured_content is not None


async def test_get_metrics_returns_tool_result():
    async with Client(mcp) as client:
        with patch.object(
            api_client,
            "get_object_metrics",
            new=AsyncMock(return_value={"views": 100, "followers": 4}),
        ):
            result = await client.call_tool(
                "get_metrics", {"object_type": "dataset", "object_id": "d-9"}
            )
    assert "Views: 100" in _text_of(result)
    assert result.structured_content is not None
