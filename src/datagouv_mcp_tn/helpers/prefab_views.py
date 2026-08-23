"""Prefab UI views for tools that benefit from rich rendering.

Companion to the text outputs: every builder here produces a Prefab
component returned as ``structured_content`` next to the unchanged text
``content``, so capable hosts render an interactive view while text-only
clients keep receiving exactly the same string as before.

``prefab_ui`` is imported lazily to keep server startup fast.
"""

from __future__ import annotations

from typing import Any, cast

from datagouv_mcp_tn.models.dataset import Resource


def search_results_table(results: list[dict[str, Any]]) -> Any:
    """Interactive table of dataset search results."""
    from prefab_ui.components import DataTable, DataTableColumn

    rows: list[dict[str, Any]] = []
    for dataset in results[:100]:
        description = " ".join((dataset.get("description") or "").split())
        rows.append(
            {
                "title": dataset.get("title") or "Untitled",
                "id": dataset.get("id") or "",
                "description": description[:120],
            }
        )
    return DataTable(
        columns=[
            DataTableColumn(key="title", header="Title", sortable=True),
            DataTableColumn(key="id", header="Dataset ID", sortable=True),
            DataTableColumn(key="description", header="Description"),
        ],
        rows=cast(Any, rows),
        search=True,
    )


def resources_table(resources: list[Resource]) -> Any:
    """Interactive table of a dataset's downloadable files."""
    from prefab_ui.components import Badge, DataTable, DataTableColumn

    tabular = {"csv", "xls", "xlsx", "ods", "json", "geojson"}
    rows: list[dict[str, Any]] = []
    for resource in resources:
        fmt = resource.format or ""
        rows.append(
            {
                "title": resource.display_title,
                "id": resource.id,
                "format": fmt,
                "size": resource.human_size or "",
                "type": Badge(fmt.upper(), variant="success")
                if fmt.lower() in tabular
                else fmt.upper(),
            }
        )
    return DataTable(
        columns=[
            DataTableColumn(key="title", header="Title", sortable=True),
            DataTableColumn(key="format", header="Format", sortable=True),
            DataTableColumn(key="size", header="Size"),
            DataTableColumn(key="id", header="Resource ID"),
            DataTableColumn(key="type", header="Type"),
        ],
        rows=cast(Any, rows),
        search=True,
    )


def rows_table(columns: list[str], rows: list[dict[str, Any]]) -> Any:
    """Generic interactive table for data rows (query results, previews)."""
    from prefab_ui.components import DataTable, DataTableColumn

    return DataTable(
        columns=[DataTableColumn(key=col, header=col) for col in columns],
        rows=cast(Any, rows),
        search=True,
    )


def organizations_table(results: list[dict[str, Any]]) -> Any:
    """Interactive table of organization search results."""
    from prefab_ui.components import DataTable, DataTableColumn

    rows = [
        {
            "name": org.get("name") or "Unnamed",
            "id": org.get("id") or "",
            "acronym": org.get("acronym") or "",
        }
        for org in results[:100]
    ]
    return DataTable(
        columns=[
            DataTableColumn(key="name", header="Organization", sortable=True),
            DataTableColumn(key="acronym", header="Acronym"),
            DataTableColumn(key="id", header="Organization ID"),
        ],
        rows=cast(Any, rows),
        search=True,
    )


def dataservices_table(results: list[dict[str, Any]]) -> Any:
    """Interactive table of dataservice (API) search results."""
    from prefab_ui.components import DataTable, DataTableColumn

    rows = [
        {
            "title": service.get("title") or service.get("name") or "Unnamed",
            "id": service.get("id") or "",
            "base_url": service.get("base_api_url") or "",
        }
        for service in results[:100]
    ]
    return DataTable(
        columns=[
            DataTableColumn(key="title", header="API", sortable=True),
            DataTableColumn(key="base_url", header="Base URL"),
            DataTableColumn(key="id", header="Dataservice ID"),
        ],
        rows=cast(Any, rows),
        search=True,
    )


_OPENAPI_METHODS = ("get", "post", "put", "patch", "delete", "options", "head")


def openapi_endpoints_table(spec: dict[str, Any]) -> Any:
    """Interactive table of the operations declared in an OpenAPI spec."""
    from prefab_ui.components import Badge, DataTable, DataTableColumn

    paths = spec.get("paths") or {}
    method_colors = {"get": "success", "post": "info", "delete": "destructive"}
    rows: list[dict[str, Any]] = []
    for path in sorted(paths)[:100]:
        operations = paths[path] if isinstance(paths[path], dict) else {}
        for method in _OPENAPI_METHODS:
            operation = operations.get(method)
            if not isinstance(operation, dict):
                continue
            label = str(operation.get("summary") or operation.get("description") or "")
            rows.append(
                {
                    "method": Badge(method.upper(), variant=method_colors.get(method, "secondary")),
                    "path": path,
                    "summary": " ".join(label.split())[:80],
                }
            )
    return DataTable(
        columns=[
            DataTableColumn(key="method", header="Method"),
            DataTableColumn(key="path", header="Path"),
            DataTableColumn(key="summary", header="Summary"),
        ],
        rows=cast(Any, rows),
        search=True,
    )


def metrics_view(object_type: str, object_id: str, values: dict[str, Any]) -> Any:
    """Metric cards plus a bar chart for the numeric metrics of one object."""
    from prefab_ui.app import PrefabApp
    from prefab_ui.components import Column, Metric, Row, Separator, Text
    from prefab_ui.components.charts import BarChart, ChartSeries

    numeric = {
        name.replace("_", " ").capitalize(): value
        for name, value in values.items()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    }

    # prefab_ui stubs expose the JSON aliases (camelCase) to type checkers
    # while runtime accepts snake_case via populate_by_name.
    chart_kwargs: dict[str, Any] = cast(
        Any,
        {
            "data": [{"metric": label, "value": value} for label, value in numeric.items()],
            "series": [ChartSeries(**cast(Any, {"data_key": "value", "label": "Value"}))],
            "x_axis": "metric",
            "show_tooltip": True,
        },
    )

    with PrefabApp() as app:
        with Column(gap=4, css_class="p-6"):
            Text(
                f"Metrics · {object_type} · {object_id}",
                css_class="text-sm text-muted-foreground",
            )
            if numeric:
                with Row(gap=4):
                    for label, value in list(numeric.items())[:4]:
                        Metric(label=label, value=f"{value:,}")
                Separator()
                BarChart(**chart_kwargs)
            else:
                Text("No numeric metrics recorded yet.")
    return app
