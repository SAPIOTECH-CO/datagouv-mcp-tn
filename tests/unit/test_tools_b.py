"""Unit tests for Tools B: orgs, dataservices, openapi spec."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from mcp.types import TextContent

from datagouv_mcp_tn.helpers import api_client
from datagouv_mcp_tn.helpers.api_client import CKANError

ORG_PAGE = {
    "total": 1,
    "data": [
        {"id": "org-1", "name": "Institut National de la Statistique", "acronym": "INS"}
    ],
}

ORG_DETAIL = {
    "id": "org-1",
    "name": "Institut National de la Statistique",
    "acronym": "INS",
    "description": "Tunisia's national statistics agency.",
    "url": "https://ins.tn",
    "metrics": {"members": 12, "datasets": 45},
}

DATASERVICE_PAGE = {
    "total": 1,
    "page": 1,
    "page_size": 20,
    "data": [
        {
            "id": "api-1",
            "title": "API recensement",
            "base_api_url": "https://api.gouv.tn/census",
        }
    ],
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

OPENAPI_SPEC = {
    "openapi": "3.1.0",
    "info": {
        "title": "Census API",
        "version": "2.0.0",
        "description": "Population queries.",
    },
    "servers": [{"url": "https://api.gouv.tn/census/v1"}],
    "paths": {
        "/communes": {"get": {"summary": "List communes"}},
        "/communes/{id}": {
            "get": {"summary": "Get one commune"},
            "post": {"summary": "Create commune"},
        },
    },
}


@pytest.fixture
async def call_tool(mcp_client):
    async def _call(name: str, arguments: dict) -> str:
        result = await mcp_client.call_tool(name, arguments)
        part = result.content[0]
        assert isinstance(part, TextContent)
        return part.text
    return _call


async def test_search_organizations_formats_results(call_tool):
    with patch.object(
        api_client, "search_organizations", new=AsyncMock(return_value=ORG_PAGE)
    ):
        text = await call_tool("search_organizations", {"query": "statistique"})
    assert "Trouvé 1 organisation(s) pour « statistique »" in text
    assert "Institut National de la Statistique" in text
    assert "Organization ID: org-1" in text


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


async def test_search_dataservices_formats_results(call_tool):
    with patch.object(
        api_client, "search_dataservices", new=AsyncMock(return_value=DATASERVICE_PAGE)
    ):
        text = await call_tool("search_dataservices", {"query": "census"})
    assert "Trouvé 1 service(s) de données pour « census »" in text
    assert "Dataservice ID: api-1" in text


async def test_search_dataservices_empty_reports_hint(call_tool):
    empty = {**DATASERVICE_PAGE, "total": 0, "data": []}
    with patch.object(
        api_client, "search_dataservices", new=AsyncMock(return_value=empty)
    ):
        text = await call_tool("search_dataservices", {"query": "nope"})
    assert "Aucun résultat" in text


async def test_get_dataservice_info_shows_metadata_and_endpoints(call_tool):
    with patch.object(
        api_client, "get_dataservice_details", new=AsyncMock(return_value=DATASERVICE_DETAIL)
    ):
        text = await call_tool("get_dataservice_info", {"dataservice_id": "api-1"})
    assert "Dataservice: API recensement" in text
    assert "Base API URL: https://api.gouv.tn/census" in text
    assert "Organization: INS" in text


async def test_get_dataservice_info_handles_missing(call_tool):
    with patch.object(
        api_client, "get_dataservice_details", new=AsyncMock(return_value={})
    ):
        text = await call_tool("get_dataservice_info", {"dataservice_id": "gone"})
    assert "Error: Dataservice with ID 'gone' not found" in text


async def test_openapi_spec_summarized_from_url(call_tool):
    detail = {**DATASERVICE_DETAIL, "openapi_spec_url": "https://x.tn/openapi.json"}
    with (
        patch.object(
            api_client, "get_dataservice_details", new=AsyncMock(return_value=detail)
        ),
        patch(
            "datagouv_mcp_tn.tools.get_dataservice_openapi_spec.fetch_resource_bytes",
            new=AsyncMock(return_value=json.dumps(OPENAPI_SPEC).encode()),
        ),
    ):
        text = await call_tool("get_dataservice_openapi_spec", {"dataservice_id": "api-1"})
    assert "OpenAPI spec: Census API" in text
    assert "Spec version: 3.1.0" in text
    assert "Operations: 3 (GET: 2, POST: 1)" in text
    assert "GET /communes — List communes" in text


async def test_openapi_spec_inline_dict_supported(call_tool):
    detail = {**DATASERVICE_DETAIL, "openapi_spec": OPENAPI_SPEC}
    with patch.object(
        api_client, "get_dataservice_details", new=AsyncMock(return_value=detail)
    ):
        text = await call_tool("get_dataservice_openapi_spec", {"dataservice_id": "api-1"})
    assert "OpenAPI spec: Census API" in text


async def test_openapi_spec_absent_is_reported(call_tool):
    detail = {
        **DATASERVICE_DETAIL,
        "endpoints": [{"url": "https://api.gouv.tn/census/v1"}],
    }
    with patch.object(
        api_client, "get_dataservice_details", new=AsyncMock(return_value=detail)
    ):
        text = await call_tool("get_dataservice_openapi_spec", {"dataservice_id": "api-1"})
    assert "no OpenAPI specification found" in text
