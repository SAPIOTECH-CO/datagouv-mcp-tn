"""Unit tests for Tools C: download, query, metrics."""

from unittest.mock import AsyncMock, patch

import pytest
from mcp.types import TextContent

from datagouv_mcp_tn.helpers import api_client
from datagouv_mcp_tn.helpers.api_client import CKANError

CSV_BYTES = b"city,score\nTunis,9\nSfax,7\nNabeul,5\n"

XLSX_RESOURCE = {
    "id": "res-x",
    "title": "cities.xlsx",
    "format": "xlsx",
    "url": "https://example.com/cities.xlsx",
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


@pytest.fixture
async def call_tool(mcp_client):
    async def _call(name: str, arguments: dict) -> str:
        result = await mcp_client.call_tool(name, arguments)
        part = result.content[0]
        assert isinstance(part, TextContent)
        return part.text
    return _call


async def test_download_and_parse_csv_shows_preview(call_tool):
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


async def test_download_and_parse_inspects_non_tabular(call_tool):
    from _factories import make_pdf

    resource = {
        "id": "res-p",
        "title": "Rapport",
        "format": "pdf",
        "url": "https://x.tn/a.pdf",
    }
    with (
        patch.object(
            api_client, "get_resource_details", new=AsyncMock(return_value=resource)
        ),
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


async def test_download_and_parse_docx_hint_despite_zip_magic(call_tool):
    from _factories import make_docx

    resource = {
        "id": "res-d",
        "title": "Note",
        "format": "docx",
        "url": "https://x.tn/a.docx",
    }
    with (
        patch.object(
            api_client, "get_resource_details", new=AsyncMock(return_value=resource)
        ),
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


async def test_download_and_parse_tabular_fallback_to_inspector(call_tool):
    from _factories import make_pdf

    resource = {
        "id": "res-l",
        "title": "Faux CSV",
        "format": "csv",
        "url": "https://x.tn/a.csv",
    }
    with (
        patch.object(
            api_client, "get_resource_details", new=AsyncMock(return_value=resource)
        ),
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


async def test_download_and_parse_tabular_without_url(call_tool):
    resource = {
        "id": "res-u",
        "title": "Sans URL",
        "format": "csv",
        "url": None,
    }
    with patch.object(
        api_client, "get_resource_details", new=AsyncMock(return_value=resource)
    ):
        text = await call_tool(
            "download_and_parse_resource", {"dataset_id": "abc-1", "resource_id": "res-u"}
        )
    assert text.startswith("Error:")
    assert "no downloadable URL" in text


async def test_download_and_parse_inspector_crash_returns_error(call_tool):
    resource = {
        "id": "res-c",
        "title": "PDF cassé",
        "format": "pdf",
        "url": "https://x.tn/a.pdf",
    }
    with (
        patch.object(
            api_client, "get_resource_details", new=AsyncMock(return_value=resource)
        ),
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


async def test_download_and_parse_api_ref_without_url(call_tool):
    resource = {"id": "res-a", "title": "API météo", "format": "api"}
    with patch.object(
        api_client, "get_resource_details", new=AsyncMock(return_value=resource)
    ):
        text = await call_tool(
            "download_and_parse_resource", {"dataset_id": "abc-1", "resource_id": "res-a"}
        )
    assert text.startswith("Error:")
    assert "search_dataservices" in text


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


async def test_query_returns_all_rows(mocked_csv_source, call_tool):
    text = await call_tool(
        "query_resource_data", {"dataset_id": "abc-1", "resource_id": "res-x"}
    )
    assert "Matched 3 row(s) · showing 3 row(s)" in text
    assert "Nabeul" in text


async def test_query_filter_contains(mocked_csv_source, call_tool):
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


async def test_query_sort_desc_limit(mocked_csv_source, call_tool):
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
    lines = [
        line
        for line in text.splitlines()
        if line.startswith(("Tunis", "Sfax", "Nabeul"))
    ]
    assert lines[0].startswith("Tunis")


async def test_query_numeric_filter_and_offset(mocked_csv_source, call_tool):
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


async def test_query_unknown_column_error(mocked_csv_source, call_tool):
    text = await call_tool(
        "query_resource_data",
        {
            "dataset_id": "abc-1",
            "resource_id": "res-x",
            "columns": "nope",
        },
    )
    assert "unknown column" in text.lower() and "nope" in text


async def test_get_metrics_from_dedicated_endpoint(call_tool):
    with patch.object(
        api_client,
        "get_object_metrics",
        new=AsyncMock(return_value={"views": 120, "followers": 7}),
    ):
        text = await call_tool(
            "get_metrics", {"object_type": "dataset", "object_id": "abc-1"}
        )
    assert "Views: 120" in text
    assert "Followers: 7" in text


async def test_get_metrics_falls_back_to_detail_payload(call_tool):
    with (
        patch.object(
            api_client,
            "get_object_metrics",
            new=AsyncMock(side_effect=CKANError("404")),
        ),
        patch.object(
            api_client,
            "get_dataset_details",
            new=AsyncMock(return_value={"metrics": {"views": 33}}),
        ),
    ):
        text = await call_tool(
            "get_metrics", {"object_type": "dataset", "object_id": "abc-1"}
        )
    assert "Views: 33" in text
