import json
from typing import Any

from fastmcp import FastMCP
from fastmcp.tools import ToolResult

from datagouv_mcp_tn.helpers import api_client
from datagouv_mcp_tn.helpers.file_parser import fetch_resource_bytes
from datagouv_mcp_tn.helpers.logging import log_tool
from datagouv_mcp_tn.helpers.mcp_tool_defaults import READ_ONLY_EXTERNAL_API_TOOL
from datagouv_mcp_tn.helpers.prefab_views import openapi_endpoints_table
from datagouv_mcp_tn.helpers.validators import validate_openapi_args

_MAX_SPEC_MB = 5  # specs are small; cap well under the download limit
_MAX_OPERATIONS_LISTED = 25


def _find_spec_url(raw: dict[str, Any]) -> str | None:
    for key in ("openapi_spec_url", "spec_url", "swagger_url", "openapi_spec"):
        value = raw.get(key)
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            return value
    endpoints = raw.get("endpoints") or []
    if isinstance(endpoints, list):
        for endpoint in endpoints:
            if not isinstance(endpoint, dict):
                continue
            fmt = str(endpoint.get("format") or "").lower()
            url = str(endpoint.get("url") or "")
            if "openapi" in fmt or "swagger" in fmt or url.endswith((".json", ".yaml", ".yml")):
                return url
    return None


def _summarize_spec(spec: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    title = spec.get("info", {}).get("title") or "Untitled API"
    version = spec.get("info", {}).get("version")
    spec_version = spec.get("openapi") or spec.get("swagger")
    lines.append(f"OpenAPI spec: {title}")
    if version:
        lines.append(f"API version: {version}")
    if spec_version:
        lines.append(f"Spec version: {spec_version}")
    description = spec.get("info", {}).get("description")
    if description:
        text = " ".join(description.split())
        if len(text) > 300:
            text = text[:297] + "..."
        lines.append(f"Description: {text}")

    servers = spec.get("servers") or []
    if servers and isinstance(servers[0], dict) and servers[0].get("url"):
        lines.append(f"Server: {servers[0]['url']}")
    elif spec.get("host"):
        scheme = (spec.get("schemes") or ["https"])[0]
        base_path = spec.get("basePath", "")
        lines.append(f"Server: {scheme}://{spec['host']}{base_path}")

    paths = spec.get("paths") or {}
    operations: list[tuple[str, str, str]] = []
    method_counts: dict[str, int] = {}
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method in ("get", "post", "put", "patch", "delete"):
            op = path_item.get(method)
            if isinstance(op, dict):
                method_counts[method.upper()] = method_counts.get(method.upper(), 0) + 1
                summary = op.get("summary") or op.get("operationId") or ""
                operations.append((method.upper(), str(path), str(summary)))

    breakdown = ", ".join(f"{k}: {v}" for k, v in sorted(method_counts.items()))
    lines.append(f"Paths: {len(paths)} · Operations: {sum(method_counts.values())} ({breakdown})")

    if operations:
        lines.append("")
        lines.append("Operations:")
        for method, path, summary in operations[:_MAX_OPERATIONS_LISTED]:
            label = f"{method} {path}"
            if summary:
                label += f" — {summary}"
            lines.append(f"- {label}")
        remaining = len(operations) - _MAX_OPERATIONS_LISTED
        if remaining > 0:
            lines.append(f"... and {remaining} more operation(s)")
    return lines


def register_get_dataservice_openapi_spec_tool(mcp: FastMCP) -> None:
    @mcp.tool(
        title="Get dataservice OpenAPI spec",
        annotations=READ_ONLY_EXTERNAL_API_TOOL,
        app=True,
    )
    @log_tool
    async def get_dataservice_openapi_spec(dataservice_id: str) -> str | ToolResult:
        """
        Fetch and summarize the OpenAPI/Swagger specification of a dataservice.

        Args:
            dataservice_id: Dataservice ID (from search_dataservices results).

        Returns:
            Spec title/version, server URL, path & operation counts, and a
            list of operations. Raw YAML is not parsed; JSON specs only.
        """
        # Validate and sanitize input
        dataservice_id = validate_openapi_args(dataservice_id)

        try:
            raw = await api_client.get_dataservice_details(dataservice_id)
        except Exception as e:  # noqa: BLE001
            return f"Error: {e}"

        inline_spec = raw.get("openapi_spec")
        spec: dict[str, Any] | None = inline_spec if isinstance(inline_spec, dict) else None

        if spec is None:
            spec_url = _find_spec_url(raw)
            if not spec_url:
                return (
                    "Error: no OpenAPI specification found for this dataservice. "
                    "Use get_dataservice_info to see its endpoints."
                )
            try:
                content = await fetch_resource_bytes(spec_url, max_mb=_MAX_SPEC_MB)
                parsed = json.loads(content.decode("utf-8", errors="replace"))
                if not isinstance(parsed, dict):
                    raise ValueError("spec is not a JSON object")
                spec = parsed
            except ValueError as e:
                return (
                    f"Error: could not parse the OpenAPI spec at {spec_url} ({e}). "
                    "YAML-only specs are not supported; open the URL directly."
                )
            except Exception as e:  # noqa: BLE001
                return f"Error: failed to download the OpenAPI spec from {spec_url}: {e}"

        text = "\n".join(_summarize_spec(spec))
        return ToolResult(content=text, structured_content=openapi_endpoints_table(spec))
