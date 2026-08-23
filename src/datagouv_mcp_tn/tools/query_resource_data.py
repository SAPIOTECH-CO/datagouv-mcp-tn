from typing import Any, Literal, cast

from fastmcp import FastMCP
from fastmcp.tools import ToolResult

from datagouv_mcp_tn.helpers import api_client
from datagouv_mcp_tn.helpers.file_parser import (
    UnsupportedFormatError,
    detect_format,
    explain_unsupported,
    fetch_resource_bytes,
    parse_tabular,
    render_table,
)
from datagouv_mcp_tn.helpers.logging import log_tool
from datagouv_mcp_tn.helpers.mcp_tool_defaults import READ_ONLY_EXTERNAL_API_TOOL
from datagouv_mcp_tn.helpers.prefab_views import rows_table
from datagouv_mcp_tn.helpers.validators import validate_query_resource_args
from datagouv_mcp_tn.models.common import SortOrder


def _coerce_value(value: str):
    for caster in (int, float):
        try:
            return caster(value)
        except (TypeError, ValueError):
            continue
    return value


def register_query_resource_data_tool(mcp: FastMCP) -> None:
    @mcp.tool(
        title="Query resource data",
        annotations=READ_ONLY_EXTERNAL_API_TOOL,
        app=True,
    )
    @log_tool
    async def query_resource_data(
        dataset_id: str,
        resource_id: str,
        columns: str | None = None,
        filter_column: str | None = None,
        filter_op: Literal["eq", "ne", "gt", "ge", "lt", "le", "contains", "startswith"] = "eq",
        filter_value: str | None = None,
        sort_by: str | None = None,
        sort_order: SortOrder = SortOrder.ASCENDING,
        limit: int = 20,
        offset: int = 0,
    ) -> str | ToolResult:
        """
        Query rows of a tabular resource (CSV, XLSX, JSON, GeoJSON) in memory.

        Args:
            dataset_id: Dataset ID or slug.
            resource_id: Resource ID (from list_dataset_resources results).
            columns: Optional comma-separated subset of columns to keep.
            filter_column: Column to filter on (used with filter_op/filter_value).
            filter_op: Comparison operator for the filter.
            filter_value: Value to compare against (numbers are auto-detected).
            sort_by: Optional column name to sort by.
            sort_order: asc or desc (applies to sort_by).
            limit: Maximum rows returned (1-100).
            offset: Rows to skip before slicing.

        Returns:
            Match counts plus the matching rows as a text table. Start with
            download_and_parse_resource to inspect columns first.
        """
        # Validate and sanitize all inputs
        (
            dataset_id,
            resource_id,
            validated_columns,
            filter_column,
            filter_op_raw,
            filter_value,
            sort_by,
            sort_order,
            limit,
            offset,
        ) = validate_query_resource_args(
            dataset_id,
            resource_id,
            columns,
            filter_column,
            filter_op,
            filter_value,
            sort_by,
            sort_order,
            limit,
            offset,
        )
        columns = validated_columns  # type: ignore[assignment]
        filter_op = cast(
            Literal["eq", "ne", "gt", "ge", "lt", "le", "contains", "startswith"],
            filter_op_raw,
        )

        try:
            raw = await api_client.get_resource_details(dataset_id, resource_id)
            fmt = detect_format(raw)
            if fmt is None:
                raise UnsupportedFormatError(explain_unsupported(raw))
            url = raw.get("url")
            if not url:
                raise ValueError("This resource has no downloadable URL.")
            content = await fetch_resource_bytes(url)
            result = parse_tabular(content, fmt)
        except Exception as e:  # noqa: BLE001
            return f"Error: {e}"

        frame = result.dataframe

        # Validate columns against actual dataframe schema
        from datagouv_mcp_tn.helpers.validators import validate_against_dataframe

        try:
            _, filter_column, sort_by = await validate_against_dataframe(
                result.columns, columns, filter_column, sort_by
            )
        except ValueError as e:
            return f"Error: {e}"

        if filter_column and filter_value is not None:
            if filter_column not in frame.columns:
                available = ", ".join(result.columns)
                return f"Error: unknown column '{filter_column}'. Available columns: {available}."
            import pandas as pd

            series = frame[filter_column]
            numeric = _coerce_value(filter_value)
            # typed as Any: pandas stubs model Series comparisons as a huge
            # union that pyright cannot resolve for mixed str/numeric series
            comparable: Any = (
                pd.to_numeric(series, errors="coerce")
                if isinstance(numeric, (int, float))
                else series.astype(str)
            )
            op = filter_op
            if op == "eq":
                mask = comparable.eq(numeric)
            elif op == "ne":
                mask = comparable.ne(numeric)
            elif op == "gt":
                mask = comparable > numeric
            elif op == "ge":
                mask = comparable >= numeric
            elif op == "lt":
                mask = comparable < numeric
            elif op == "le":
                mask = comparable <= numeric
            elif op == "contains":
                mask = series.astype(str).str.contains(str(filter_value), case=False, na=False)
            else:  # startswith
                mask = (
                    series.astype(str)
                    .str.lower()
                    .str.startswith(str(filter_value).lower(), na=False)
                )
            frame = frame[mask.fillna(False)]
        elif filter_column or filter_value is not None:
            return "Error: filtering requires both filter_column and filter_value."

        if columns:
            requested = [col.strip() for col in columns.split(",") if col.strip()]
            unknown = [col for col in requested if col not in frame.columns]
            if unknown:
                available = ", ".join(frame.columns)
                return f"Error: unknown column(s): {', '.join(unknown)}. Available: {available}."
            frame = frame[requested]

        if sort_by:
            if sort_by not in frame.columns:
                available = ", ".join(frame.columns)
                return f"Error: unknown sort column '{sort_by}'. Available: {available}."
            ascending = sort_order is SortOrder.ASCENDING
            frame = frame.sort_values(by=sort_by, ascending=ascending, na_position="last")

        matched = len(frame)
        offset = max(0, offset)
        limit_clamped = max(1, min(limit, 100))
        page = frame.iloc[offset : offset + limit_clamped]

        lines = [
            f"Matched {matched} row(s) · showing {len(page)} row(s) "
            f"(offset {offset}, limit {limit_clamped})",
            "",
        ]
        if page.empty:
            lines.append("No rows match these parameters.")
            return "\n".join(lines)

        lines.append(render_table(page, limit_clamped))
        lines.append("")
        lines.append(f"Source: {result.n_rows} total row(s) · {result.format.upper()}")
        text = "\n".join(lines)

        preview_rows = page.head(limit_clamped).to_dict(orient="records")
        view = rows_table(result.columns, preview_rows)
        return ToolResult(content=text, structured_content=view)
