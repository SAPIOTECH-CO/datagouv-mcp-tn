import json
from unittest.mock import AsyncMock, patch

import pytest
from fastmcp import Client

from datagouv_mcp_tn.helpers import api_client
from datagouv_mcp_tn.helpers.api_client import UDataError
from datagouv_mcp_tn.server import mcp

CSV_BYTES = b"city,score\nTunis,9\nSfax,7\nNabeul,5\n"

XLSX_RESOURCE = {
    "id": "res-x",
    "title": "cities.xlsx",
    "format": "xlsx",
    "url": "https://example.com/cities.xlsx",
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
    "endpoints": [{"url": "https://api.gouv.tn/census/v1", "format": "openapi"}],
}

OPENAPI_SPEC = {
    "openapi": "3.1.0",
    "info": {"title": "Census API", "version": "2.0.0", "description": "Population queries."},
    "servers": [{"url": "https://api.gouv.tn/census/v1"}],
    "paths": {
        "/communes": {"get": {"summary": "List communes"}},
        "/communes/{id}": {
            "get": {"summary": "Get one commune"},
            "post": {"summary": "Create commune"},
        },
    },
}


async def call_tool(name: str, arguments: dict) -> str:
    async with Client(mcp) as client:
        result = await client.call_tool(name, arguments)
    part = result.content[0]
    assert part.type == "text"
    return part.text


# --- TASK-020: search_dataservices ---


async def test_search_dataservices_formats_results():
    with patch.object(
        api_client, "search_dataservices", new=AsyncMock(return_value=DATASERVICE_PAGE)
    ):
        text = await call_tool("search_dataservices", {"query": "census"})
    assert "Trouvé 1 service(s) de données pour « census »" in text
    assert "Dataservice ID: api-1" in text


async def test_search_dataservices_empty_reports_hint():
    empty = {**DATASERVICE_PAGE, "total": 0, "data": []}
    with patch.object(api_client, "search_dataservices", new=AsyncMock(return_value=empty)):
        text = await call_tool("search_dataservices", {"query": "nope"})
    assert "Aucun résultat" in text


# --- TASK-024: get_dataservice_info ---


async def test_get_dataservice_info_shows_metadata_and_endpoints():
    with patch.object(
        api_client, "get_dataservice_details", new=AsyncMock(return_value=DATASERVICE_DETAIL)
    ):
        text = await call_tool("get_dataservice_info", {"dataservice_id": "api-1"})
    assert "Dataservice: API recensement" in text
    assert "Base API URL: https://api.gouv.tn/census" in text
    assert "Organization: INS" in text


async def test_get_dataservice_info_handles_missing():
    with patch.object(api_client, "get_dataservice_details", new=AsyncMock(return_value={})):
        text = await call_tool("get_dataservice_info", {"dataservice_id": "gone"})
    assert text.startswith("Error: Dataservice with ID 'gone' not found.")


# --- TASK-025: get_dataservice_openapi_spec ---


async def test_openapi_spec_summarized_from_url():
    detail = {**DATASERVICE_DETAIL, "openapi_spec_url": "https://x.tn/openapi.json"}
    with (
        patch.object(api_client, "get_dataservice_details", new=AsyncMock(return_value=detail)),
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


async def test_openapi_spec_inline_dict_supported():
    detail = {**DATASERVICE_DETAIL, "openapi_spec": OPENAPI_SPEC}
    with patch.object(api_client, "get_dataservice_details", new=AsyncMock(return_value=detail)):
        text = await call_tool("get_dataservice_openapi_spec", {"dataservice_id": "api-1"})
    assert "OpenAPI spec: Census API" in text


async def test_openapi_spec_absent_is_reported():
    detail = {**DATASERVICE_DETAIL, "endpoints": [{"url": "https://api.gouv.tn/census/v1"}]}
    with patch.object(api_client, "get_dataservice_details", new=AsyncMock(return_value=detail)):
        text = await call_tool("get_dataservice_openapi_spec", {"dataservice_id": "api-1"})
    assert "no OpenAPI specification found" in text


# --- TASK-027: download_and_parse_resource ---


async def test_download_and_parse_csv_shows_preview():
    with (
        patch.object(
            api_client,
            "get_resource_details",
            new=AsyncMock(return_value=XLSX_RESOURCE | {"format": "csv"}),
        ),
        patch(
            "datagouv_mcp_tn.tools.download_and_parse_resource.fetch_resource_bytes",
            new=AsyncMock(return_value=CSV_BYTES),
        ),
    ):
        text = await call_tool(
            "download_and_parse_resource", {"dataset_id": "abc-1", "resource_id": "res-x"}
        )
    assert "Format: CSV" in text
    assert "Rows: 3 · Columns: 2" in text
    assert "Tunis" in text
    assert "query_resource_data" in text


async def test_download_and_parse_inspects_non_tabular():
    from _factories import make_pdf

    resource = {"id": "res-p", "title": "Rapport", "format": "pdf", "url": "https://x.tn/a.pdf"}
    with (
        patch.object(api_client, "get_resource_details", new=AsyncMock(return_value=resource)),
        patch(
            "datagouv_mcp_tn.tools.download_and_parse_resource.fetch_resource_bytes",
            new=AsyncMock(return_value=make_pdf(pages=2)),
        ),
    ):
        text = await call_tool(
            "download_and_parse_resource", {"dataset_id": "abc-1", "resource_id": "res-p"}
        )
    assert "Kind: document" in text
    assert "Pages: 2" in text
    assert "not tabular" in text


async def test_download_and_parse_docx_hint_despite_zip_magic():
    from _factories import make_docx

    resource = {"id": "res-d", "title": "Note", "format": "docx", "url": "https://x.tn/a.docx"}
    with (
        patch.object(api_client, "get_resource_details", new=AsyncMock(return_value=resource)),
        patch(
            "datagouv_mcp_tn.tools.download_and_parse_resource.fetch_resource_bytes",
            new=AsyncMock(return_value=make_docx()),
        ),
    ):
        text = await call_tool(
            "download_and_parse_resource", {"dataset_id": "abc-1", "resource_id": "res-d"}
        )
    assert "Kind: document" in text
    assert "Paragraphs:" in text


async def test_download_and_parse_tabular_fallback_to_inspector():
    """A resource announced as CSV whose body is actually a PDF gets inspected."""
    from _factories import make_pdf

    resource = {"id": "res-l", "title": "Faux CSV", "format": "csv", "url": "https://x.tn/a.csv"}
    with (
        patch.object(api_client, "get_resource_details", new=AsyncMock(return_value=resource)),
        patch(
            "datagouv_mcp_tn.tools.download_and_parse_resource.fetch_resource_bytes",
            new=AsyncMock(return_value=make_pdf(pages=1)),
        ),
    ):
        text = await call_tool(
            "download_and_parse_resource", {"dataset_id": "abc-1", "resource_id": "res-l"}
        )
    assert "Kind: document" in text
    assert "is not one" in text


async def test_download_and_parse_tabular_without_url():
    resource = {"id": "res-u", "title": "Sans URL", "format": "csv", "url": None}
    with patch.object(api_client, "get_resource_details", new=AsyncMock(return_value=resource)):
        text = await call_tool(
            "download_and_parse_resource", {"dataset_id": "abc-1", "resource_id": "res-u"}
        )
    assert text.startswith("Error:")
    assert "no downloadable URL" in text


async def test_download_and_parse_inspector_crash_returns_error():
    """Malformed non-tabular payloads surface as an Error string, never a raise."""
    resource = {
        "id": "res-c",
        "title": "PDF cassé",
        "format": "pdf",
        "url": "https://x.tn/a.pdf",
    }
    with (
        patch.object(api_client, "get_resource_details", new=AsyncMock(return_value=resource)),
        patch(
            "datagouv_mcp_tn.tools.download_and_parse_resource.fetch_resource_bytes",
            new=AsyncMock(return_value=b"%PDF-1.7 garbage \x00\xff"),
        ),
    ):
        text = await call_tool(
            "download_and_parse_resource", {"dataset_id": "abc-1", "resource_id": "res-c"}
        )
    assert text.startswith("Error:")
    assert "could not inspect" in text


async def test_download_and_parse_api_ref_without_url():
    resource = {"id": "res-a", "title": "API météo", "format": "api"}
    with patch.object(api_client, "get_resource_details", new=AsyncMock(return_value=resource)):
        text = await call_tool(
            "download_and_parse_resource", {"dataset_id": "abc-1", "resource_id": "res-a"}
        )
    assert text.startswith("Error:")
    assert "search_dataservices" in text


# --- TASK-026: query_resource_data ---


@pytest.fixture
def mocked_csv_source():
    with (
        patch.object(
            api_client,
            "get_resource_details",
            new=AsyncMock(return_value=XLSX_RESOURCE | {"format": "csv"}),
        ),
        patch(
            "datagouv_mcp_tn.tools.query_resource_data.fetch_resource_bytes",
            new=AsyncMock(return_value=CSV_BYTES),
        ),
    ):
        yield


async def test_query_returns_all_rows(mocked_csv_source):
    text = await call_tool("query_resource_data", {"dataset_id": "abc-1", "resource_id": "res-x"})
    assert "Matched 3 row(s) · showing 3 row(s)" in text
    assert "Nabeul" in text


async def test_query_filter_contains(mocked_csv_source):
    text = await call_tool(
        "query_resource_data",
        {
            "dataset_id": "abc-1",
            "resource_id": "res-x",
            "filter_column": "city",
            "filter_op": "contains",
            "filter_value": "uni",
        },
    )
    assert "Matched 1 row(s)" in text
    assert "Tunis" in text and "Sfax" not in text


async def test_query_sort_desc_limit(mocked_csv_source):
    text = await call_tool(
        "query_resource_data",
        {
            "dataset_id": "abc-1",
            "resource_id": "res-x",
            "sort_by": "score",
            "sort_order": "desc",
            "limit": 1,
        },
    )
    assert "showing 1 row(s)" in text
    lines = [line for line in text.splitlines() if line.startswith(("Tunis", "Sfax", "Nabeul"))]
    assert lines[0].startswith("Tunis")


async def test_query_numeric_filter_and_offset(mocked_csv_source):
    text = await call_tool(
        "query_resource_data",
        {
            "dataset_id": "abc-1",
            "resource_id": "res-x",
            "filter_column": "score",
            "filter_op": "gt",
            "filter_value": "6",
            "offset": 1,
            "limit": 10,
        },
    )
    assert "Matched 2 row(s) · showing 1 row(s)" in text


async def test_query_unknown_column_error(mocked_csv_source):
    text = await call_tool(
        "query_resource_data",
        {
            "dataset_id": "abc-1",
            "resource_id": "res-x",
            "columns": "nope",
        },
    )
    assert "unknown column(s): nope" in text


# --- TASK-028: get_metrics ---


async def test_get_metrics_from_dedicated_endpoint():
    with patch.object(
        api_client,
        "get_object_metrics",
        new=AsyncMock(return_value={"views": 120, "followers": 7}),
    ):
        text = await call_tool("get_metrics", {"object_type": "dataset", "object_id": "abc-1"})
    assert "Views: 120" in text
    assert "Followers: 7" in text


async def test_get_metrics_falls_back_to_detail_payload():
    with (
        patch.object(
            api_client,
            "get_object_metrics",
            new=AsyncMock(side_effect=UDataError("404")),
        ),
        patch.object(
            api_client,
            "get_dataset_details",
            new=AsyncMock(return_value={"metrics": {"views": 33}}),
        ),
    ):
        text = await call_tool("get_metrics", {"object_type": "dataset", "object_id": "abc-1"})
    assert "Views: 33" in text
