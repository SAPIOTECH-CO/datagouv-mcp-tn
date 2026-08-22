import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastmcp import Client

from datagouv_mcp_tn.server import mcp, search_datasets

DATASETS_PAGE = {
    "total": 2,
    "page": 1,
    "page_size": 20,
    "data": [
        {
            "id": "abc-1",
            "slug": "population-tunisie",
            "title": "Population",
            "description": "Population data",
            "page": "https://data.gouv.tn/datasets/population-tunisie",
        },
        {
            "id": "abc-2",
            "slug": "budget-2024",
            "title": "Budget 2024",
            "description": None,
            "url": "https://example.com/budget.json",
        },
    ],
}

ORGANIZATIONS_PAGE = {
    **DATASETS_PAGE,
    "data": [DATASETS_PAGE["data"][0]],
}

SUGGESTIONS = [
    {"id": "abc-1", "title": "Population"},
    {"id": "abc-3", "title": "Population active"},
]

DATASET_DETAIL = {"id": "abc-1", "title": "Population", "resources": [{"format": "csv"}]}


@pytest.fixture
def api():
    with patch("datagouv_mcp_tn.server.get_client") as get_client:
        get_client.return_value = MagicMock()
        get_client.return_value.get = AsyncMock(return_value={})
        yield get_client.return_value


async def test_search_datasets_returns_summarized_results(api):
    api.get.return_value = DATASETS_PAGE
    async with Client(mcp) as client:
        result = await client.call_tool("search_datasets", {"query": "population"})
    data = json.loads(result.content[0].text)
    assert data["total"] == 2
    assert len(data["results"]) == 2
    assert data["results"][0]["title"] == "Population"
    assert data["results"][0]["url"].startswith("https://data.gouv.tn/")
    assert data["results"][1]["url"].startswith("https://example.com/")


async def test_get_dataset_returns_full_metadata(api):
    api.get.return_value = DATASET_DETAIL
    async with Client(mcp) as client:
        result = await client.call_tool("get_dataset", {"dataset_id": "abc-1"})
    assert json.loads(result.content[0].text) == DATASET_DETAIL


async def test_suggest_datasets_returns_title_list(api):
    api.get.return_value = SUGGESTIONS
    async with Client(mcp) as client:
        result = await client.call_tool("suggest_datasets", {"partial_query": "popul"})
    assert result.data == ["Population", "Population active"]


async def test_suggest_datasets_handles_unexpected_payload(api):
    api.get.return_value = {"unexpected": True}
    async with Client(mcp) as client:
        result = await client.call_tool("suggest_datasets", {"partial_query": "x"})
    assert result.data == []


async def test_search_organizations_returns_summarized_results(api):
    api.get.return_value = ORGANIZATIONS_PAGE
    async with Client(mcp) as client:
        result = await client.call_tool("search_organizations", {"query": "ministry"})
    data = json.loads(result.content[0].text)
    assert data["total"] == 2
    assert len(data["results"]) == 1


@pytest.mark.parametrize(
    "requested,expected",
    [
        (20, 20),
        (100, 100),
        (500, 100),
    ],
)
async def test_search_datasets_caps_page_size_at_100(api, requested, expected):
    api.get.return_value = DATASETS_PAGE
    await search_datasets(query="q", page=2, page_size=requested)
    _, kwargs = api.get.await_args
    assert kwargs["params"]["page_size"] == expected
    assert kwargs["params"]["page"] == 2
