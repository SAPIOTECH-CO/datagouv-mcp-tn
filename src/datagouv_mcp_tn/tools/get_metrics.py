from typing import Any, Literal

from fastmcp import FastMCP

from datagouv_mcp_tn.helpers import api_client
from datagouv_mcp_tn.helpers.logging import log_tool
from datagouv_mcp_tn.helpers.mcp_tool_defaults import READ_ONLY_EXTERNAL_API_TOOL
from datagouv_mcp_tn.models.metrics import Metrics

_METRICS_FIELDS = (
    "views",
    "followers",
    "reuses",
    "datasets",
    "members",
)


def _render_metrics(payload: dict[str, Any]) -> str:
    metrics = Metrics.from_api(payload)
    lines: list[str] = []
    for name in _METRICS_FIELDS:
        value = getattr(metrics, name, None) or payload.get(name)
        if value is not None:
            lines.append(f"{name.capitalize()}: {value}")
    extras = {
        key: value
        for key, value in sorted((metrics.model_extra or {}).items())
        if key not in _METRICS_FIELDS and isinstance(value, (int, float))
    }
    for key, value in extras.items():
        lines.append(f"{key.replace('_', ' ').capitalize()}: {value}")
    if len(lines) <= 1:
        lines.append("No numeric metrics recorded for this object yet.")
    return "\n".join(lines)


def register_get_metrics_tool(mcp: FastMCP) -> None:
    @mcp.tool(
        title="Get metrics",
        annotations=READ_ONLY_EXTERNAL_API_TOOL,
    )
    @log_tool
    async def get_metrics(
        object_type: Literal["dataset", "organization", "dataservice", "reuse"],
        object_id: str,
    ) -> str:
        """
        Get usage metrics (views, followers, reuses...) for a portal object.

        Args:
            object_type: Kind of object to inspect.
            object_id: Object ID (from the corresponding search/info tools).

        Returns:
            One line per available metric. Falls back to the embedded
            'metrics' attribute when the dedicated endpoint is unavailable.
        """
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
        return "\n".join([header, _render_metrics(payload)])
