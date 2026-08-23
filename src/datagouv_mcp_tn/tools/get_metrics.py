from typing import Any, Literal

from fastmcp import FastMCP
from fastmcp.tools import ToolResult

from datagouv_mcp_tn.helpers import api_client
from datagouv_mcp_tn.helpers.logging import log_tool
from datagouv_mcp_tn.helpers.mcp_tool_defaults import READ_ONLY_EXTERNAL_API_TOOL
from datagouv_mcp_tn.helpers.prefab_views import metrics_view
from datagouv_mcp_tn.helpers.validators import validate_metrics_args
from datagouv_mcp_tn.models.metrics import Metrics

_METRICS_FIELDS = (
    "views",
    "followers",
    "reuses",
    "datasets",
    "members",
)


def _collect_metrics(payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Return (text rendering, numeric values map) for a metrics payload."""
    metrics = Metrics.from_api(payload)
    lines: list[str] = []
    values: dict[str, Any] = {}
    for name in _METRICS_FIELDS:
        value = getattr(metrics, name, None) or payload.get(name)
        if value is not None:
            lines.append(f"{name.capitalize()}: {value}")
            values[name] = value
    extras = {
        key: value
        for key, value in sorted((metrics.model_extra or {}).items())
        if key not in _METRICS_FIELDS and isinstance(value, (int, float))
    }
    for key, value in extras.items():
        lines.append(f"{key.replace('_', ' ').capitalize()}: {value}")
        values[key] = value
    if len(lines) <= 1:
        lines.append("No numeric metrics recorded for this object yet.")
    return "\n".join(lines), values


def register_get_metrics_tool(mcp: FastMCP) -> None:
    @mcp.tool(
        title="Get metrics",
        annotations=READ_ONLY_EXTERNAL_API_TOOL,
        app=True,
    )
    @log_tool
    async def get_metrics(
        object_type: Literal["dataset", "organization", "dataservice", "reuse"],
        object_id: str,
    ) -> str | ToolResult:
        """
        Get usage metrics (views, followers, reuses...) for a portal object.

        Args:
            object_type: Kind of object to inspect.
            object_id: Object ID (from the corresponding search/info tools).

        Returns:
            One line per available metric. Falls back to the embedded
            'metrics' attribute when the dedicated endpoint is unavailable.
        """
        # Validate and sanitize inputs
        object_type, object_id = validate_metrics_args(object_type, object_id)

        try:
            payload = await api_client.get_object_metrics(object_type, object_id)
        except Exception:  # noqa: BLE001 - fall back to detail payload metrics
            detail_fetchers = {
                "dataset": api_client.get_dataset_details,
                "organization": api_client.get_organization_details,
                "dataservice": api_client.get_dataservice_details,
            }
            fetcher = detail_fetchers.get(object_type)
            if fetcher is None:
                return f"Error: no fallback metrics source for '{object_type}'."
            try:
                detail = await fetcher(object_id)
            except Exception as e:  # noqa: BLE001
                return f"Error: {e}"
            payload = detail.get("metrics") or {}
            if isinstance(payload, dict) and not payload:
                return "No metrics available for this object."
        else:
            if not isinstance(payload, dict):
                return "Error: unexpected metrics payload from the portal."

        header = f"Metrics for {object_type} '{object_id}':"
        text, values = _collect_metrics(payload)
        return ToolResult(
            content="\n".join([header, text]),
            structured_content=metrics_view(object_type, object_id, values),
        )
