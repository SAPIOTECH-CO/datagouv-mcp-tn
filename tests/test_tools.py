from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastmcp import Client

from datagouv_mcp_tn.helpers import api_client
from datagouv_mcp_tn.helpers.api_client import UDataError
from datagouv_mcp_tn.server import mcp

SEARCH_PAGE = {
    "total": 2,
    "page": 1,
    "page_size": 20,
    "data": [
        {
            "id": "abc-1",
            "slug": "population-tunisie",
            "title": "Population",
            "description": "Population data for Tunisia",
        },
        {
            "id": "abc-2",
            "slug": "budget-2024",
            "title": "Budget 2024",
            "description": None,
        },
    ],
}

DATASET_DETAIL = {
    "id": "abc-1",
    "slug": "population-tunisie",
    "title": "Population",
    "description": "Population data\nfor Tunisia.",
    "tags": ["demographics", "tunisia"],
    "license": {"id": "cc-by", "title": "CC BY"},
    "last_update": "2026-01-15T00:00:00",
    "organization": {"name": "INS"},
    "resources": [
        {
            "id": "res-1",
            "title": "pop.csv",
            "format": "csv",
            "filesize": 2048,
            "url": "https://example.com/pop.csv",
        },
        {
            "id": "res-2",
            "title": "notes.pdf",
            "format": "pdf",
            "url": "https://example.com/notes.pdf",
        },
    ],
}

RESOURCE_DETAIL = {
    "id": "res-1",
    "title": "pop.csv",
    "format": "csv",
    "mime": "text/csv",
    "filesize": 2048,
    "checksum": {"type": "sha1", "value": "deadbeef"},
    "url": "https://example.com/pop.csv",
}

SUGGESTIONS = [
    {"id": "abc-1", "title": "Population"},
    {"id": "abc-3", "title": "Population active"},
]

ORG_PAGE = {
    "total": 1,
    "data": [{"id": "org-1", "name": "Institut National de la Statistique", "acronym": "INS"}],
}


async def call_tool(name: str, arguments: dict) -> str:
    async with Client(mcp) as client:
        result = await client.call_tool(name, arguments)
    return result.content[0].text


async def test_search_datasets_formats_results_with_ids():
    with patch.object(api_client, "search_datasets", new=AsyncMock(return_value=SEARCH_PAGE)):
        text = await call_tool("search_datasets", {"query": "population"})
    assert "Found 2 dataset(s)" in text
    assert "Population" in text
    assert "Dataset ID: abc-1" in text


async def test_search_datasets_reports_empty_results():
    empty = {**SEARCH_PAGE, "total": 0, "data": []}
    with patch.object(api_client, "search_datasets", new=AsyncMock(return_value=empty)):
        text = await call_tool("search_datasets", {"query": "zzz"})
    assert "No datasets found" in text


async def test_get_dataset_info_shows_metadata_and_next_step():
    with patch.object(
        api_client, "get_dataset_details", new=AsyncMock(return_value=DATASET_DETAIL)
    ):
        text = await call_tool("get_dataset_info", {"dataset_id": "abc-1"})
    assert "Population data for Tunisia." in text
    assert "Organization: INS" in text
    assert "License: CC BY" in text
    assert "Resources: 2 file(s)" in text
    assert "list_dataset_resources" in text


async def test_get_dataset_info_handles_missing_dataset():
    with patch.object(api_client, "get_dataset_details", new=AsyncMock(return_value={})):
        text = await call_tool("get_dataset_info", {"dataset_id": "nope"})
    assert text.startswith("Error:")


async def test_list_dataset_resources_lists_files_with_sizes():
    with patch.object(
        api_client, "get_dataset_details", new=AsyncMock(return_value=DATASET_DETAIL)
    ):
        text = await call_tool("list_dataset_resources", {"dataset_id": "abc-1"})
    assert "Total resources: 2" in text
    assert "Resource ID: res-1" in text
    assert "Format: csv" in text
    assert "Size: 2.0 KB" in text
    assert "URL: https://example.com/pop.csv" in text


async def test_get_resource_info_returns_checksum_and_url():
    with patch.object(
        api_client, "get_resource_details", new=AsyncMock(return_value=RESOURCE_DETAIL)
    ):
        text = await call_tool("get_resource_info", {"dataset_id": "abc-1", "resource_id": "res-1"})
    assert "pop.csv" in text
    assert "Checksum (sha1): deadbeef" in text
    assert "URL: https://example.com/pop.csv" in text


async def test_get_resource_info_reports_unknown_resource():
    with patch.object(
        api_client,
        "get_resource_details",
        new=AsyncMock(side_effect=UDataError("Resource 'x' not found")),
    ):
        text = await call_tool("get_resource_info", {"dataset_id": "abc-1", "resource_id": "x"})
    assert "not found" in text


async def test_suggest_datasets_lists_titles():
    with patch.object(api_client, "suggest_datasets", new=AsyncMock(return_value=SUGGESTIONS)):
        text = await call_tool("suggest_datasets", {"partial_query": "popul"})
    assert "- Population" in text
    assert "- Population active" in text


async def test_search_organizations_formats_results():
    with patch.object(api_client, "search_organizations", new=AsyncMock(return_value=ORG_PAGE)):
        text = await call_tool("search_organizations", {"query": "statistique"})
    assert "Found 1 organization(s)" in text
    assert "Institut National de la Statistique" in text
    assert "Organization ID: org-1" in text


async def test_tools_return_error_text_on_api_failure():
    with patch.object(
        api_client,
        "search_datasets",
        new=AsyncMock(side_effect=UDataError("connection refused")),
    ):
        text = await call_tool("search_datasets", {"query": "x"})
    assert text.startswith("Error:")
    assert "connection refused" in text


@pytest.mark.parametrize(
    "requested,expected",
    [(20, 20), (100, 100), (500, 100)],
)
async def test_api_client_caps_page_size_at_100(requested, expected):
    http = AsyncMock()
    response = MagicMock()
    response.json.return_value = {}
    http.get = AsyncMock(return_value=response)
    with (
        patch.object(api_client, "_http", None),
        patch("datagouv_mcp_tn.helpers.api_client._client", return_value=http),
    ):
        await api_client.search_datasets(query="q", page=2, page_size=requested)
    _, kwargs = http.get.await_args
    assert kwargs["params"]["page_size"] == expected
