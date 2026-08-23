"""Download and parse tabular resources (CSV, XLS, XLSX, ODS, JSON, GeoJSON).

The parser is deliberately lazy: pandas/openpyxl/xlrd/odfpy are imported on
first use so stdio server startup stays fast. Everything is in-memory —
nothing touches the filesystem.
"""

from __future__ import annotations

import io
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Literal, cast
from urllib.parse import urlparse

import httpx

from datagouv_mcp_tn.helpers.config import get_settings

logger = logging.getLogger(__name__)

PREVIEW_ROWS = 5
MAX_PREVIEW_CELL_CHARS = 60

SUPPORTED_FORMATS = ("csv", "xls", "xlsx", "ods", "json", "geojson")

# Canonical names for the format/mime strings actually found on data.gouv.tn,
# including messy ones ('XLS', '.jpg', 'word', 'test'...). Anything not listed
# here (PDF, images, archives, API refs...) is reported as non-tabular.
_FORMAT_ALIASES = {
    "csv": "csv",
    "xls": "xls",
    "xlsx": "xlsx",
    "ods": "ods",
    "json": "json",
    "geojson": "geojson",
}

_EXCEL_ENGINES = {
    "xlsx": "openpyxl",
    "xls": "xlrd",
    "ods": "odf",
}

_MIME_HINTS = {
    "text/csv": "csv",
    "application/csv": "csv",
    "application/vnd.ms-excel": "xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/vnd.oasis.opendocument.spreadsheet": "ods",
    "application/json": "json",
    "application/geo+json": "geojson",
    "application/vnd.geo+json": "geojson",
}

_GEOJSON_KEYS = ("data", "results", "items", "records", "features", "values")


def normalize_format(raw: Any) -> str:
    """Lowercase, trim and strip a leading dot from a format string."""
    return str(raw or "").strip().lower().lstrip(".")


def is_tabular_filename(filename: str) -> bool:
    """True if the filename has an extension the tabular parser handles."""
    lowered = filename.lower()
    extension = lowered.rsplit(".", 1)[-1] if "." in lowered else ""
    return extension in _FORMAT_ALIASES


def decode_text_best_effort(content: bytes) -> str:
    """Decode text trying UTF-8 first, then cp1252/latin-1 for legacy files.

    data.gouv.tn still hosts Windows-1252/Latin-1 documents; decoding those
    as UTF-8 would fill previews with U+FFFD replacement characters.
    """
    best: tuple[str, float] | None = None
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        decoded = content.decode(encoding, errors="replace")
        ratio = decoded.count("\ufffd") / max(len(decoded), 1)
        if ratio == 0:
            return decoded
        if best is None or ratio < best[1]:
            best = (decoded, ratio)
    assert best is not None
    return best[0]


class UnsupportedFormatError(ValueError):
    """Raised when a resource format cannot be parsed as tabular data."""


class DownloadTooLargeError(ValueError):
    """Raised when a resource exceeds the configured download size cap."""


@dataclass
class ParseResult:
    format: str
    n_rows: int
    n_columns: int
    columns: list[str]
    dtypes: dict[str, str]
    preview: list[dict[str, Any]]
    dataframe: Any = field(repr=False, default=None)  # pd.DataFrame


def detect_format(resource: dict[str, Any]) -> str | None:
    """Best-effort format detection from a uData resource payload.

    Handles the messy real-world values observed on data.gouv.tn: case
    differences ('XLSX', 'GeoJSON'), leading dots ('.jpg'), and mime types.
    """
    for key in ("format", "mime"):
        raw = normalize_format(resource.get(key))
        if raw in _FORMAT_ALIASES:
            return _FORMAT_ALIASES[raw]
        if raw in _MIME_HINTS:
            return _MIME_HINTS[raw]
        # 'text/csv' style mime values ending with an extension
        extension = raw.split("/")[-1]
        if extension in _FORMAT_ALIASES:
            return _FORMAT_ALIASES[extension]
    url = str(resource.get("url") or "").split("?")[0].lower()
    filename = url.rsplit("/", 1)[-1]
    extension = filename.rsplit(".", 1)[-1] if "." in filename else ""
    return _FORMAT_ALIASES.get(extension)


def explain_unsupported(resource: dict[str, Any]) -> str:
    """A helpful error for resources whose format is not tabular."""
    raw = normalize_format(resource.get("format"))
    if raw == "api":
        return (
            "This resource is an API endpoint reference, not a downloadable "
            "file. Use search_dataservices to explore published APIs."
        )
    shown = f"'{raw}'" if raw else "unknown"
    return (
        f"Format {shown} is not tabular-parseable. Supported formats: "
        f"{', '.join(SUPPORTED_FORMATS)}. PDF/images/archives must be opened "
        "via their download URL instead."
    )


async def fetch_resource_bytes(url: str, *, max_mb: int | None = None) -> bytes:
    """Stream-download a resource URL enforcing scheme and size caps."""
    settings = get_settings()
    limit_mb = max_mb if max_mb is not None else settings.max_download_size_mb
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Unsupported URL scheme '{parsed.scheme}': only http(s) is allowed.")

    limit_bytes = limit_mb * 1024 * 1024
    chunks: list[bytes] = []
    received = 0
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=settings.download_timeout,
        headers={"User-Agent": "datagouv-mcp-tn"},
    ) as client:
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes():
                received += len(chunk)
                if received > limit_bytes:
                    raise DownloadTooLargeError(
                        f"Resource exceeds the {limit_mb} MB download cap "
                        f"(use smaller resources or raise MAX_DOWNLOAD_SIZE_MB)."
                    )
                chunks.append(chunk)
    logger.info("Downloaded %.1f KB from %s", received / 1024, url)
    return b"".join(chunks)


def _records_from_json(payload: Any) -> tuple[list[dict[str, Any]], bool]:
    """Normalize arbitrary JSON into records; returns (records, is_geojson)."""
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)], False
    if not isinstance(payload, dict):
        return [{"value": payload}], False

    if payload.get("type") == "FeatureCollection" and isinstance(payload.get("features"), list):
        records = []
        for feature in payload["features"]:
            row: dict[str, Any] = {}
            properties = feature.get("properties") or {} if isinstance(feature, dict) else {}
            row.update(properties if isinstance(properties, dict) else {})
            geometry = feature.get("geometry") or {} if isinstance(feature, dict) else {}
            if isinstance(geometry, dict):
                coordinates = geometry.get("coordinates")
                depth = coordinates
                dims = 0
                while isinstance(depth, list):
                    dims += 1
                    depth = depth[0] if depth else None
                row["geometry_type"] = geometry.get("type")
                row["geometry_dims"] = dims
            records.append(row)
        return records, True

    for key in _GEOJSON_KEYS:
        inner = payload.get(key)
        if isinstance(inner, list) and (not inner or isinstance(inner[0], dict)):
            return [item for item in inner if isinstance(item, dict)], False

    for value in payload.values():
        if isinstance(value, list) and (not value or isinstance(value[0], dict)):
            return [item for item in value if isinstance(item, dict)], False

    return [payload], False


def parse_tabular(content: bytes, fmt: str) -> ParseResult:
    """Parse raw bytes into a :class:`ParseResult` (lazy pandas import)."""
    fmt = fmt.strip().lower()
    if fmt not in SUPPORTED_FORMATS:
        raise UnsupportedFormatError(
            f"Format '{fmt}' is not supported. Supported: {', '.join(SUPPORTED_FORMATS)}."
        )

    import pandas as pd

    if fmt == "csv":
        buffer = io.BytesIO(content)
        try:
            frame = pd.read_csv(buffer, sep=None, engine="python")
        except UnicodeDecodeError:
            # Legacy cp1252/latin-1 files are common on data.gouv.tn.
            buffer.seek(0)
            frame = pd.read_csv(buffer, sep=None, engine="python", encoding="cp1252")
        except Exception:  # noqa: BLE001 - fall back to plain comma parsing
            buffer.seek(0)
            frame = pd.read_csv(buffer)
    elif fmt in _EXCEL_ENGINES:
        # cast: the dict maps to valid engine literals, but fmt is a plain str
        engine = cast("Literal['xlrd', 'openpyxl', 'odf']", _EXCEL_ENGINES[fmt])
        frame = pd.read_excel(io.BytesIO(content), engine=engine)
    else:  # json / geojson
        text = decode_text_best_effort(content)
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON: {exc}") from exc
        records, _ = _records_from_json(payload)
        frame = pd.DataFrame(records)

    columns = [str(col) for col in frame.columns]
    return ParseResult(
        format=fmt,
        n_rows=int(len(frame)),
        n_columns=len(columns),
        columns=columns,
        dtypes={str(col): str(dtype) for col, dtype in frame.dtypes.items()},
        preview=frame.head(PREVIEW_ROWS).to_dict(orient="records"),
        dataframe=frame,
    )


def download_summary_lines(result: ParseResult, num_bytes: int) -> list[str]:
    """Standard summary block shared by the two data tools."""
    lines = [
        f"Format: {result.format.upper()}",
        f"Downloaded size: {human_size(num_bytes)}",
        f"Rows: {result.n_rows} · Columns: {result.n_columns}",
    ]
    if result.columns:
        lines.append("Columns:")
        for col in result.columns:
            lines.append(f"- {col} ({result.dtypes.get(col, 'unknown')})")
    return lines


def truncate_cell(value: Any, width: int = MAX_PREVIEW_CELL_CHARS) -> str:
    text = "" if value is None else str(value).replace("\n", "\\n")
    if len(text) > width:
        return text[: width - 3] + "..."
    return text


def render_table(frame: Any, max_rows: int) -> str:
    """Render a DataFrame slice as aligned text with truncated cells."""
    import pandas as pd

    sliced = frame.head(max_rows).copy()
    sliced = sliced.astype(object).where(pd.notna(sliced), "")
    for col in sliced.columns:
        sliced[col] = sliced[col].map(truncate_cell)
    return sliced.to_string(index=False)


def human_size(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} B"
    size = num_bytes / 1024
    for unit in ("KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"
