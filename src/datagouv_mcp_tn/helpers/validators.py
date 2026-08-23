"""Input validation and sanitization for all tool arguments.

Centralizes allow-lists, format checks, and sanitization logic so that
every tool applies the same rules. Designed to be composable:
validators raise ValueError with a clear message; tools catch and return
"Error: ..." strings per project convention.
"""

from __future__ import annotations

import re
from typing import Literal, cast

from datagouv_mcp_tn.helpers.i18n import Language
from datagouv_mcp_tn.models.common import SortOrder

# --- allow-lists --------------------------------------------------------------

_MAX_QUERY_LEN = 500
_MAX_ID_LEN = 100
_MAX_PAGE_SIZE = 100
_MIN_PAGE = 1

# uData slug pattern: lowercase alphanumeric + hyphens, no leading/trailing hyphen
_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
# Dataset/resource/dataservice IDs can also be numeric
_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,100}$")

# Columns / field names: alphanumeric + underscore, no SQL-ish keywords
_COLUMN_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]{0,63}$")
_SQL_KEYWORDS = frozenset(
    {
        "select",
        "insert",
        "update",
        "delete",
        "drop",
        "create",
        "alter",
        "union",
        "exec",
        "execute",
        "script",
        "declare",
        "xp_",
        "sp_",
    }
)


# --- core validators ----------------------------------------------------------


def validate_query(query: str) -> str:
    """Validate and sanitize a search query string."""
    if not query or not query.strip():
        raise ValueError("Query must not be empty")
    cleaned = query.strip()
    if len(cleaned) > _MAX_QUERY_LEN:
        raise ValueError(f"Query too long (max {_MAX_QUERY_LEN} characters)")
    # Strip control chars but keep unicode letters/digits/punct
    sanitized = re.sub(r"[\x00-\x1f\x7f]", "", cleaned)
    return sanitized


def validate_id(value: str, field: str = "ID") -> str:
    """Validate a dataset/resource/dataservice/organization identifier."""
    if not value:
        raise ValueError(f"{field} must not be empty")
    v = value.strip()
    if len(v) > _MAX_ID_LEN:
        raise ValueError(f"{field} too long (max {_MAX_ID_LEN} characters)")
    if not _ID_RE.fullmatch(v):
        raise ValueError(f"Invalid {field} format: only alphanumeric, hyphen, underscore allowed")
    return v


def validate_slug(value: str, field: str = "slug") -> str:
    """Validate a uData-style slug (lowercase alnum + hyphens)."""
    if not value:
        raise ValueError(f"{field} must not be empty")
    v = value.strip().lower()
    if not _SLUG_RE.fullmatch(v):
        raise ValueError(
            f"Invalid {field}: only lowercase letters, digits, hyphens; no leading/trailing hyphen"
        )
    return v


def validate_page(page: int) -> int:
    """Validate 1-based page number."""
    if page < _MIN_PAGE:
        raise ValueError(f"Page must be >= {_MIN_PAGE}")
    return page


def validate_page_size(page_size: int) -> int:
    """Validate page size within allowed bounds."""
    if page_size < 1 or page_size > _MAX_PAGE_SIZE:
        raise ValueError(f"Page size must be between 1 and {_MAX_PAGE_SIZE}")
    return page_size


def validate_limit(limit: int, max_limit: int = 100) -> int:
    """Validate a row-limit parameter (e.g., query_resource_data limit)."""
    if limit < 1 or limit > max_limit:
        raise ValueError(f"Limit must be between 1 and {max_limit}")
    return limit


def validate_offset(offset: int) -> int:
    """Validate a non-negative offset."""
    if offset < 0:
        raise ValueError("Offset must be >= 0")
    return offset


def validate_columns(columns: str | None, available: list[str] | None = None) -> list[str] | None:
    """Parse and validate a comma-separated column list."""
    if columns is None:
        return None
    if not columns.strip():
        raise ValueError("Columns list must not be empty")
    requested = [c.strip() for c in columns.split(",") if c.strip()]
    if not requested:
        raise ValueError("Columns list must not be empty")
    for col in requested:
        if not _COLUMN_RE.fullmatch(col):
            raise ValueError(f"Invalid column name: '{col}'")
        if col.lower() in _SQL_KEYWORDS:
            raise ValueError(f"Column name '{col}' is a reserved keyword")
        if available and col not in available:
            raise ValueError(f"Unknown column: '{col}'")
    return requested


def validate_filter_column(column: str | None, available: list[str] | None = None) -> str | None:
    """Validate a filter column name."""
    if not column:
        return None
    col = column.strip()
    if not _COLUMN_RE.fullmatch(col):
        raise ValueError(f"Invalid filter column: '{col}'")
    if available and col not in available:
        raise ValueError(f"Unknown filter column: '{col}'")
    return col


def validate_filter_value(value: str | None) -> str | None:
    """Basic sanitization of filter values (no control chars)."""
    if value is None:
        return None
    sanitized = re.sub(r"[\x00-\x1f\x7f]", "", value)
    if len(sanitized) > 200:
        raise ValueError("Filter value too long (max 200 characters)")
    return sanitized


def validate_sort_column(column: str | None, available: list[str] | None = None) -> str | None:
    """Validate a sort column name."""
    if not column:
        return None
    col = column.strip()
    if not _COLUMN_RE.fullmatch(col):
        raise ValueError(f"Invalid sort column: '{col}'")
    if available and col not in available:
        raise ValueError(f"Unknown sort column: '{col}'")
    return col


def validate_sort_order(order: SortOrder | None) -> SortOrder:
    """Normalize sort order, defaulting to ASCENDING."""
    return order or SortOrder.ASCENDING


def validate_language(lang: Language | None) -> Language:
    """Normalize language, defaulting to the configured default."""
    if lang is not None:
        return lang
    from datagouv_mcp_tn.helpers.config import get_settings

    default = get_settings().default_language
    if default == "fr":
        return Language.FRENCH
    if default == "ar":
        return Language.ARABIC
    return Language.ENGLISH


def validate_preview_rows(rows: int) -> int:
    """Validate preview row count (1-20)."""
    if rows < 1 or rows > 20:
        raise ValueError("Preview rows must be between 1 and 20")
    return rows


def validate_object_type(obj_type: str) -> str:
    """Validate object type for metrics endpoint."""
    allowed = {"dataset", "organization", "dataservice", "reuse"}
    if obj_type not in allowed:
        raise ValueError(f"Object type must be one of: {', '.join(sorted(allowed))}")
    return obj_type


def validate_file_format(fmt: str) -> str:
    """Validate a file format string against supported list."""
    from datagouv_mcp_tn.helpers.file_parser import SUPPORTED_FORMATS

    f = fmt.strip().lower()
    if f not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported format: '{fmt}'. Supported: {', '.join(SUPPORTED_FORMATS)}")
    return f


def sanitize_text(text: str, max_len: int = 10000) -> str:
    """Generic text sanitization: strip control chars, truncate."""
    if not text:
        return ""
    sanitized = re.sub(r"[\x00-\x1f\x7f]", "", text)
    return sanitized[:max_len]


# --- composite validators for tool signatures --------------------------------


def validate_search_args(
    query: str,
    page: int,
    page_size: int,
    language: Language | None,
) -> tuple[str, int, int, Language]:
    """Validate all search_* tool arguments at once."""
    return (
        validate_query(query),
        validate_page(page),
        validate_page_size(page_size),
        validate_language(language),
    )


def validate_pagination_args(page: int, page_size: int) -> tuple[int, int]:
    """Validate pagination arguments."""
    return validate_page(page), validate_page_size(page_size)


def validate_query_resource_args(
    dataset_id: str,
    resource_id: str,
    columns: str | None,
    filter_column: str | None,
    filter_op: str,
    filter_value: str | None,
    sort_by: str | None,
    sort_order: SortOrder,
    limit: int,
    offset: int,
) -> tuple[
    str, str, list[str] | None, str | None, str, str | None, str | None, SortOrder, int, int
]:
    """Validate all query_resource_data arguments."""
    return (
        validate_id(dataset_id, "Dataset ID"),
        validate_id(resource_id, "Resource ID"),
        validate_columns(columns),
        validate_filter_column(filter_column),
        filter_op,  # validated by Literal in signature
        validate_filter_value(filter_value),
        validate_sort_column(sort_by),
        validate_sort_order(sort_order),
        validate_limit(limit),
        validate_offset(offset),
    )


def validate_download_args(
    dataset_id: str,
    resource_id: str,
    preview_rows: int,
) -> tuple[str, str, int]:
    """Validate download_and_parse_resource arguments."""
    return (
        validate_id(dataset_id, "Dataset ID"),
        validate_id(resource_id, "Resource ID"),
        validate_preview_rows(preview_rows),
    )


def validate_metrics_args(
    object_type: str, object_id: str
) -> tuple[Literal["dataset", "organization", "dataservice", "reuse"], str]:
    """Validate get_metrics arguments."""
    return cast(
        Literal["dataset", "organization", "dataservice", "reuse"],
        validate_object_type(object_type),
    ), validate_id(object_id, "Object ID")


def validate_openapi_args(dataservice_id: str) -> str:
    """Validate get_dataservice_openapi_spec argument."""
    return validate_id(dataservice_id, "Dataservice ID")


def validate_resource_args(dataset_id: str) -> str:
    """Validate list_dataset_resources argument."""
    return validate_id(dataset_id, "Dataset ID")


# --- async helper for dataframe-aware validation ------------------------------


async def validate_against_dataframe(
    frame_columns: list[str],
    columns: str | list[str] | None,
    filter_column: str | None,
    sort_by: str | None,
) -> tuple[list[str] | None, str | None, str | None]:
    """Validate column names against an actual DataFrame (post-parse).

    Accepts `columns` as either a comma-separated string (from the first
    validation pass) or an already-parsed list (if the validator already ran).
    """
    # If columns is already a list, just validate against available columns
    if isinstance(columns, list):
        validated_columns = columns
        for col in validated_columns:
            if col not in frame_columns:
                raise ValueError(f"Unknown column: '{col}'")
    else:
        validated_columns = validate_columns(columns, frame_columns)

    return (
        validated_columns,
        validate_filter_column(filter_column, frame_columns),
        validate_sort_column(sort_by, frame_columns),
    )
