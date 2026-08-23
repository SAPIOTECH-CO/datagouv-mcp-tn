"""Unit tests for Tools A: search, suggest, dataset info, resources."""

from unittest.mock import AsyncMock, patch

import pytest
from mcp.types import TextContent

from datagouv_mcp_tn.helpers import api_client
from datagouv_mcp_tn.helpers.api_client import CKANError

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


@pytest.fixture
async def call_tool(mcp_client):
    async def _call(name: str, arguments: dict) -> str:
        result = await mcp_client.call_tool(name, arguments)
        part = result.content[0]
        assert isinstance(part, TextContent)
        return part.text
    return _call


async def test_search_datasets_formats_results_with_ids(call_tool):
    with patch.object(
        api_client, "search_datasets", new=AsyncMock(return_value=SEARCH_PAGE)
    ):
        text = await call_tool("search_datasets", {"query": "population"})
    assert "Trouvé 2 jeu(x) de données pour « population »" in text
    assert "Population" in text
    assert "Dataset ID: abc-1" in text


async def test_search_datasets_formats_results_in_english_and_arabic(call_tool):
    with patch.object(
        api_client, "search_datasets", new=AsyncMock(return_value=SEARCH_PAGE)
    ):
        english = await call_tool(
            "search_datasets", {"query": "population", "language": "en"}
        )
        arabic = await call_tool(
            "search_datasets", {"query": "population", "language": "ar"}
        )
    assert "Found 2 dataset(s) for 'population'" in english
    assert "تم العثور على 2 مجموعة(ات) بيانات" in arabic


async def test_search_datasets_reports_empty_results(call_tool):
    empty = {**SEARCH_PAGE, "total": 0, "data": []}
    with patch.object(
        api_client, "search_datasets", new=AsyncMock(return_value=empty)
    ):
        text = await call_tool("search_datasets", {"query": "zzz"})
    assert "Aucun résultat" in text


async def test_get_dataset_info_shows_metadata_and_next_step(call_tool):
    with patch.object(
        api_client, "get_dataset_details", new=AsyncMock(return_value=DATASET_DETAIL)
    ):
        text = await call_tool("get_dataset_info", {"dataset_id": "abc-1"})
    assert "Population data for Tunisia." in text
    assert "Organization: INS" in text
    assert "License: CC BY" in text
    assert "Resources: 2 file(s)" in text
    assert "list_dataset_resources" in text


async def test_get_dataset_info_handles_missing_dataset(call_tool):
    with patch.object(
        api_client, "get_dataset_details", new=AsyncMock(return_value={})
    ):
        text = await call_tool("get_dataset_info", {"dataset_id": "nope"})
    assert text.startswith("Error:")


async def test_list_dataset_resources_lists_files_with_sizes(call_tool):
    with patch.object(
        api_client, "get_dataset_details", new=AsyncMock(return_value=DATASET_DETAIL)
    ):
        text = await call_tool("list_dataset_resources", {"dataset_id": "abc-1"})
    assert "Total resources: 2" in text
    assert "Resource ID: res-1" in text
    assert "Format: csv" in text
    assert "Size: 2.0 KB" in text
    assert "URL: https://example.com/pop.csv" in text


async def test_get_resource_info_returns_checksum_and_url(call_tool):
    with patch.object(
        api_client, "get_resource_details", new=AsyncMock(return_value=RESOURCE_DETAIL)
    ):
        text = await call_tool(
            "get_resource_info", {"dataset_id": "abc-1", "resource_id": "res-1"}
        )
    assert "pop.csv" in text
    assert "Checksum (sha1): deadbeef" in text
    assert "URL: https://example.com/pop.csv" in text


async def test_get_resource_info_reports_unknown_resource(call_tool):
    with patch.object(
        api_client,
        "get_resource_details",
        new=AsyncMock(side_effect=CKANError("Resource 'x' not found")),
    ):
        text = await call_tool(
            "get_resource_info", {"dataset_id": "abc-1", "resource_id": "x"}
        )
    assert "not found" in text


async def test_suggest_datasets_lists_titles(call_tool):
    with patch.object(
        api_client, "suggest_datasets", new=AsyncMock(return_value=SUGGESTIONS)
    ):
        text = await call_tool("suggest_datasets", {"partial_query": "popul"})
    assert "- Population" in text
    assert "- Population active" in text


async def test_tools_return_error_text_on_api_failure(call_tool):
    with patch.object(
        api_client,
        "search_datasets",
        new=AsyncMock(side_effect=CKANError("connection refused")),
    ):
        text = await call_tool("search_datasets", {"query": "x"})
    assert text.startswith("Error:")
    assert "connection refused" in text


@pytest.mark.parametrize(
    "requested,expected", [(20, 20), (100, 100), (500, 100)]
)
async def test_api_client_caps_page_size_at_100(requested, expected):
    http = AsyncMock()
    response = pytest.importorskip("unittest.mock").MagicMock()
    response.json.return_value = {
        "success": True, "result": {"count": 0, "results": []}
    }
    http.get = AsyncMock(return_value=response)
    with (
        patch.object(api_client, "_http_clients", {}),
        patch(
            "datagouv_mcp_tn.helpers.api_client._get_client", return_value=http
        ),
    ):
        await api_client.search_datasets(
            query="q", page=2, page_size=requested, portal_key="agridata"
        )
    _, kwargs = http.get.await_args
    assert kwargs["params"]["rows"] == expected
