from fastmcp import FastMCP

from datagouv_mcp_tn.helpers import api_client
from datagouv_mcp_tn.helpers.document_inspector import inspect_non_tabular, sniff_kind
from datagouv_mcp_tn.helpers.file_parser import (
    PREVIEW_ROWS,
    detect_format,
    download_summary_lines,
    explain_unsupported,
    fetch_resource_bytes,
    normalize_format,
    parse_tabular,
    render_table,
)
from datagouv_mcp_tn.helpers.logging import log_tool
from datagouv_mcp_tn.helpers.mcp_tool_defaults import READ_ONLY_EXTERNAL_API_TOOL

_MAGIC_KINDS_NEVER_TABULAR = frozenset({"pdf", "png", "jpeg", "gif", "ole2"})


def _resource_title(raw: dict, resource_id: str) -> str:
    return str(raw.get("title") or raw.get("name") or raw.get("id") or resource_id)


def _render_inspection(
    raw: dict,
    resource_id: str,
    kind: str | None,
    lines: list[str],
    downloaded_size: int | None = None,
) -> str:
    """Shared rendering for both non-tabular output paths."""
    header = [f"Resource: {_resource_title(raw, resource_id)}"]
    if kind is not None:
        size_part = (
            f" · Downloaded size: {downloaded_size} bytes" if downloaded_size is not None else ""
        )
        header.append(f"Kind: {kind}{size_part}")
    output = [*header, ""]
    output.extend(lines)
    output.extend(["", "Note: this resource is not tabular; use its URL to access the raw file."])
    return "\n".join(output)


def register_download_and_parse_resource_tool(mcp: FastMCP) -> None:
    @mcp.tool(
        title="Download and parse resource",
        annotations=READ_ONLY_EXTERNAL_API_TOOL,
    )
    @log_tool
    async def download_and_parse_resource(
        dataset_id: str,
        resource_id: str,
        preview_rows: int = PREVIEW_ROWS,
    ) -> str:
        """
        Download any resource from data.gouv.tn and analyze it in memory.

        Tabular files (CSV, XLS, XLSX, ODS, JSON, GeoJSON) are parsed into
        rows/columns with a preview. Everything else — PDF, Word, PowerPoint,
        HTML/XML, images, ZIP/KMZ archives, plain text — is inspected: page
        counts, text previews, dimensions, archive listings...

        The file is processed in memory only. Use query_resource_data instead
        when you want filtered/sorted rows of a tabular resource.

        Args:
            dataset_id: Dataset ID or slug.
            resource_id: Resource ID (from list_dataset_resources results).
            preview_rows: Number of preview rows for tabular files (1-20).

        Returns:
            A structured summary of the file content.
        """
        try:
            raw = await api_client.get_resource_details(dataset_id, resource_id)
        except Exception as e:  # noqa: BLE001
            return f"Error: {e}"

        fmt = detect_format(raw)
        if fmt is not None:
            return await _summarize_tabular(raw, resource_id, fmt, preview_rows)

        # Non-tabular (or undetectable): download once and describe it.
        url = raw.get("url")
        if not url:
            return f"Error: {explain_unsupported(raw)}"
        try:
            content = await fetch_resource_bytes(url)
            kind, lines = inspect_non_tabular(content, normalize_format(raw.get("format")))
        except Exception as e:  # noqa: BLE001
            return f"Error: could not inspect resource: {e}"
        return _render_inspection(raw, resource_id, kind, lines, len(content))


async def _summarize_tabular(raw: dict, resource_id: str, fmt: str, preview_rows: int) -> str:
    url = raw.get("url")
    if not url:
        return f"Error: this resource is detected as {fmt.upper()} but has no downloadable URL."

    try:
        content = await fetch_resource_bytes(url)
    except Exception as e:  # noqa: BLE001
        return f"Error: could not download {fmt.upper()} content: {e}"

    # A file announced as CSV whose magic bytes reveal a PDF/image/legacy
    # Office payload would otherwise be shredded into garbage rows by the
    # delimiter-sniffing parser — send it straight to inspection.
    if fmt == "csv" and sniff_kind(content) in _MAGIC_KINDS_NEVER_TABULAR:
        return _inspect_fallback(raw, resource_id, content, fmt)

    try:
        result = parse_tabular(content, fmt)
    except Exception as parse_error:  # noqa: BLE001
        return _inspect_fallback(raw, resource_id, content, fmt, parse_error)

    lines = [f"Resource: {_resource_title(raw, resource_id)}"]
    lines.extend(download_summary_lines(result, len(content)))
    lines.append("")
    if result.n_rows == 0:
        lines.append("The file contains no data rows.")
        return "\n".join(lines)

    shown = max(1, min(preview_rows, 20))
    lines.append(f"Preview ({shown} first row(s)):")
    lines.append(render_table(result.dataframe, shown))
    lines.append("")
    lines.append("Next step: use query_resource_data to filter, sort or select columns.")
    return "\n".join(lines)


def _inspect_fallback(
    raw: dict,
    resource_id: str,
    content: bytes,
    fmt: str,
    parse_error: Exception | None = None,
) -> str:
    """Describe content the tabular parser rejected (or should not touch)."""
    try:
        kind, lines = inspect_non_tabular(content, fmt)
    except Exception:  # noqa: BLE001
        reason = f" ({parse_error})" if parse_error else ""
        return f"Error: could not parse {fmt.upper()} content{reason}"
    notice = (
        f"The file could not be parsed as {fmt.upper()} ({parse_error}); inspected instead."
        if parse_error
        else f"The file announced as {fmt.upper()} is not one; inspected instead."
    )
    lines = [notice, "", *lines]
    return _render_inspection(raw, resource_id, kind, lines, len(content))
