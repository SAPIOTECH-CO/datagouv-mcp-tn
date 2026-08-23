"""End-to-end scenario tests (TASK-038)."""

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
    "description": "Population data for Tunisia.",
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

ORG_DETAIL = {
    "id": "org-1",
    "name": "Institut National de la Statistique",
    "acronym": "INS",
    "description": "Tunisia's national statistics agency.",
    "url": "https://ins.tn",
    "metrics": {"members": 12, "datasets": 45},
}

DATASERVICE_DETAIL = {
    "id": "api-1",
    "name": "API recensement",
    "description": "Census API.",
    "base_api_url": "https://api.gouv.tn/census",
    "organization": {"name": "INS"},
    "endpoints": [
        {"url": "https://api.gouv.tn/census/v1", "format": "openapi"}
    ],
}

CSV_BYTES = b"city,score\nTunis,9\nSfax,7\nNabeul,5\n"


async def _call(mcp_client, name: str, arguments: dict) -> str:
    result = await mcp_client.call_tool(name, arguments)
    part = result.content[0]
    assert isinstance(part, TextContent)
    return part.text


@pytest.mark.asyncio
async def test_e2e_discover_and_drill_down(mcp_client):
    with patch.object(
        api_client, "search_datasets", new=AsyncMock(return_value=SEARCH_PAGE)
    ):
        text = await _call(mcp_client, "search_datasets", {"query": "population"})
    assert "Population" in text
    assert "Dataset ID: abc-1" in text

    with patch.object(
        api_client, "get_dataset_details", new=AsyncMock(return_value=DATASET_DETAIL)
    ):
        text = await _call(
            mcp_client, "get_dataset_info", {"dataset_id": "abc-1"}
        )
    assert "Population data for Tunisia." in text
    assert "Resources: 2 file(s)" in text
    assert "list_dataset_resources" in text

    with patch.object(
        api_client, "get_dataset_details", new=AsyncMock(return_value=DATASET_DETAIL)
    ):
        text = await _call(
            mcp_client, "list_dataset_resources", {"dataset_id": "abc-1"}
        )
    assert "Total resources: 2" in text
    assert "Resource ID: res-1" in text
    assert "Format: csv" in text

    with patch.object(
        api_client, "get_resource_details", new=AsyncMock(return_value=RESOURCE_DETAIL)
    ):
        text = await _call(
            mcp_client, "get_resource_info", {"dataset_id": "abc-1", "resource_id": "res-1"}
        )
    assert "pop.csv" in text
    assert "Checksum (sha1): deadbeef" in text


@pytest.mark.asyncio
async def test_e2e_organization_discovery(mcp_client):
    with patch.object(
        api_client,
        "search_organizations",
        new=AsyncMock(return_value={"total": 1, "data": [ORG_DETAIL]}),
    ):
        text = await _call(
            mcp_client, "search_organizations", {"query": "statistique"}
        )
    assert "Institut National de la Statistique" in text
    assert "Organization ID: org-1" in text

    with patch.object(
        api_client, "get_organization_details", new=AsyncMock(return_value=ORG_DETAIL)
    ):
        text = await _call(
            mcp_client, "get_organization_info", {"organization_id": "org-1"}
        )
    assert "Members: 12" in text
    assert "Datasets published: 45" in text


@pytest.mark.asyncio
async def test_e2e_dataservice_discovery(mcp_client):
    detail = {**DATASERVICE_DETAIL, "openapi_spec_url": "https://x.tn/openapi.json"}
    with patch.object(
        api_client,
        "search_dataservices",
        new=AsyncMock(return_value={"total": 1, "data": [DATASERVICE_DETAIL]}),
    ):
        text = await _call(
            mcp_client, "search_dataservices", {"query": "census"}
        )
    assert "API recensement" in text

    with (
        patch.object(
            api_client, "get_dataservice_details", new=AsyncMock(return_value=detail)
        ),
        patch(
            "datagouv_mcp_tn.tools.get_dataservice_openapi_spec.fetch_resource_bytes",
            new=AsyncMock(
                return_value=(
                    b'{"openapi":"3.1.0","info":{'
                    b'"title":"Census API","version":"1.0.0"},'
                    b'"paths":{"/communes":{"get":{"summary":"List communes"}}}}'
                )
            ),
        ),
    ):
        text = await _call(
            mcp_client, "get_dataservice_openapi_spec", {"dataservice_id": "api-1"}
        )
    assert "OpenAPI spec: Census API" in text


@pytest.mark.asyncio
async def test_e2e_data_analysis_workflow(mcp_client):
    resource = {
        "id": "res-1",
        "title": "pop.csv",
        "format": "csv",
        "url": "https://example.com/pop.csv",
    }
    with (
        patch.object(
            api_client, "get_resource_details", new=AsyncMock(return_value=resource)
        ),
        patch(
            "datagouv_mcp_tn.tools.download_and_parse_resource.fetch_resource_bytes",
            new=AsyncMock(return_value=CSV_BYTES),
        ),
    ):
        text = await _call(
            mcp_client, "download_and_parse_resource",
            {"dataset_id": "abc-1", "resource_id": "res-1"}
        )
    assert "Format: CSV" in text
    assert "Rows: 3" in text
    assert "query_resource_data" in text

    with (
        patch.object(
            api_client, "get_resource_details", new=AsyncMock(return_value=resource)
        ),
        patch(
            "datagouv_mcp_tn.tools.query_resource_data.fetch_resource_bytes",
            new=AsyncMock(return_value=CSV_BYTES),
        ),
    ):
        text = await _call(
            mcp_client, "query_resource_data", {
                "dataset_id": "abc-1",
                "resource_id": "res-1",
                "filter_column": "city",
                "filter_op": "contains",
                "filter_value": "uni",
            }
        )
    assert "Matched 1 row(s)" in text
    assert "Tunis" in text


@pytest.mark.asyncio
async def test_e2e_error_handling_chain(mcp_client):
    with patch.object(
        api_client,
        "search_datasets",
        new=AsyncMock(side_effect=CKANError("connection refused")),
    ):
        text = await _call(
            mcp_client, "search_datasets", {"query": "x"}
        )
    assert text.startswith("Error:")
    assert "connection refused" in text

    with patch.object(
        api_client, "get_dataset_details", new=AsyncMock(return_value={})
    ):
        text = await _call(
            mcp_client, "get_dataset_info", {"dataset_id": "missing"}
        )
    assert text.startswith("Error:")

    resource = {"id": "res-1", "title": "x", "format": "csv", "url": None}
    with patch.object(
        api_client, "get_resource_details", new=AsyncMock(return_value=resource)
    ):
        text = await _call(
            mcp_client, "download_and_parse_resource",
            {"dataset_id": "abc-1", "resource_id": "res-1"}
        )
    assert text.startswith("Error:")
    assert "no downloadable URL" in text
