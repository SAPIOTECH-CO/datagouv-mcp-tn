import io
from typing import Any, cast

import pytest

from datagouv_mcp_tn.helpers.file_parser import (
    PREVIEW_ROWS,
    ParseResult,
    UnsupportedFormatError,
    detect_format,
    download_summary_lines,
    explain_unsupported,
    fetch_resource_bytes,
    human_size,
    parse_tabular,
    render_table,
)

CSV_BYTES = b"name,score\nalpha,3\nbeta,7\ngamma,1\ndelta,5\n"


def make_xlsx() -> bytes:
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.append(["city", "pop"])
    sheet.append(["Tunis", 1056247])
    sheet.append(["Sfax", 330440])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"name": "Tunis", "code": "11"},
            "geometry": {"type": "Polygon", "coordinates": [[[1, 2], [3, 4], [5, 6], [1, 2]]]},
        },
        {
            "type": "Feature",
            "properties": {"name": "Sfax", "code": "14"},
            "geometry": {"type": "Point", "coordinates": [10.0, 34.7]},
        },
    ],
}


# --- detection ---


@pytest.mark.parametrize(
    "resource,expected",
    [
        ({"format": "CSV"}, "csv"),
        ({"format": " XLSX "}, "xlsx"),
        ({"format": "XLS"}, "xls"),
        ({"format": "ODS"}, "ods"),
        ({"format": "GeoJSON"}, "geojson"),
        ({"format": ".jpg"}, None),
        ({"format": "word"}, None),
        ({"format": "test"}, None),
        ({"mime": "application/vnd.ms-excel"}, "xls"),
        ({"mime": "application/vnd.oasis.opendocument.spreadsheet"}, "ods"),
        ({"mime": "application/geo+json"}, "geojson"),
        ({"url": "https://x.tn/f/data.xlsx"}, "xlsx"),
        ({"url": "https://x.tn/f/data.XLS?download=1"}, "xls"),
        ({"format": "pdf", "url": "https://x.tn/f/file.pdf"}, None),
        ({"format": "pdf"}, None),
        ({}, None),
    ],
)
def test_detect_format_from_metadata(resource, expected):
    assert detect_format(resource) == expected


def test_explain_unsupported_api_and_files():
    assert "API endpoint reference" in explain_unsupported({"format": "API"})
    message = explain_unsupported({"format": "PDF"})
    assert "'pdf'" in message and "csv" in message
    assert "unknown" in explain_unsupported({})


def test_parse_xls_routes_through_xlrd_engine(monkeypatch):
    import pandas as pd

    captured: dict = {}

    def fake_read_excel(buffer, engine):
        captured["engine"] = engine
        return pd.DataFrame([{"a": 1}])

    monkeypatch.setattr(pd, "read_excel", fake_read_excel)
    result = parse_tabular(b"not-real-xls-bytes", "xls")
    assert captured["engine"] == "xlrd"
    assert result.n_rows == 1


def test_parse_real_ods_file():
    import pandas as pd

    frame = pd.DataFrame([{"region": "Nord", "pop": 1}, {"region": "Sud", "pop": 2}])
    buffer = io.BytesIO()
    # cast: odf is a valid runtime engine, but pandas stubs omit it here
    frame.to_excel(buffer, engine=cast(Any, "odf"), index=False)
    parsed = parse_tabular(buffer.getvalue(), "ods")
    assert parsed.columns == ["region", "pop"]
    assert parsed.n_rows == 2


# --- parsing ---


def test_parse_csv_sniffed_and_typed():
    result = parse_tabular(CSV_BYTES, "csv")
    assert result.format == "csv"
    assert result.columns == ["name", "score"]
    assert result.n_rows == 4
    assert len(result.preview) == min(PREVIEW_ROWS, 4)


def test_parse_xlsx():
    result = parse_tabular(make_xlsx(), "xlsx")
    assert result.columns == ["city", "pop"]
    assert result.n_rows == 2
    assert result.preview[0]["city"] == "Tunis"


def test_parse_json_list_of_records():
    payload = b'[{"a": 1}, {"a": 2}]'
    result = parse_tabular(payload, "json")
    assert result.n_rows == 2
    assert result.columns == ["a"]


def test_parse_json_wrapped_in_data_key():
    result = parse_tabular(b'{"data": [{"k": "v"}], "total": 1}', "json")
    assert result.n_rows == 1
    assert result.columns == ["k"]


def test_parse_geojson_flattens_properties_and_geometry():
    import json

    result = parse_tabular(json.dumps(GEOJSON).encode(), "geojson")
    assert result.n_rows == 2
    assert set(result.columns) >= {"name", "code", "geometry_type"}
    assert result.preview[0]["geometry_type"] == "Polygon"
    assert result.preview[0]["name"] == "Tunis"


def test_parse_rejects_unsupported_and_invalid():
    with pytest.raises(UnsupportedFormatError):
        parse_tabular(CSV_BYTES, "parquet")
    with pytest.raises(ValueError, match="Invalid JSON"):
        parse_tabular(b"{nope", "json")


# --- rendering & helpers ---


def test_render_table_truncates_cells():
    frame = parse_tabular(CSV_BYTES, "csv").dataframe
    text = render_table(frame, 2)
    assert "alpha" in text and "beta" in text and "gamma" not in text


def test_human_size():
    assert human_size(512) == "512 B"
    assert human_size(2048) == "2.0 KB"


def test_download_summary_lines_lists_columns_with_types():
    lines = download_summary_lines(parse_tabular(CSV_BYTES, "csv"), 2048)
    assert any("Rows: 4" in line for line in lines)
    assert "- name (" in "".join(lines)


async def test_fetch_resource_bytes_rejects_non_http_schemes():
    from datagouv_mcp_tn.helpers.file_parser import DownloadTooLargeError  # noqa: F401

    with pytest.raises(ValueError, match="scheme"):
        await fetch_resource_bytes("file:///etc/passwd")


# --- ParseResult shape sanity ---


def test_parse_result_defaults():
    result = ParseResult(format="csv", n_rows=0, n_columns=0, columns=[], dtypes={}, preview=[])
    assert result.dataframe is None
