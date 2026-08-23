"""MCP Resources for the CKAN open data MCP server.

Resources expose portal metadata and API documentation through URI templates
so clients can read dynamic data without invoking tools.
"""

from __future__ import annotations

import json
from typing import Any

from datagouv_mcp_tn.helpers.config import get_settings
from datagouv_mcp_tn.portals import get_portal, list_portals

# ---------------------------------------------------------------------------
# Static resources
# ---------------------------------------------------------------------------


async def get_config() -> str:
    """Current server configuration (JSON)."""
    settings = get_settings()
    config: dict[str, Any] = {
        "default_portal": settings.default_portal,
        "request_timeout": settings.request_timeout,
        "request_max_retries": settings.request_max_retries,
        "retry_backoff_seconds": settings.retry_backoff_seconds,
        "download_timeout": settings.download_timeout,
        "max_download_size_mb": settings.max_download_size_mb,
        "default_language": settings.default_language,
        "log_level": settings.log_level,
        "strict_input_validation": settings.strict_input_validation,
        "rate_limit_enabled": settings.rate_limit_enabled,
        "rate_limit_max_requests": settings.rate_limit_max_requests,
        "rate_limit_window_minutes": settings.rate_limit_window_minutes,
        "cors_enabled": settings.cors_enabled,
        "host_origin_protection": settings.host_origin_protection,
        "log_sanitization_enabled": settings.log_sanitization_enabled,
    }
    return json.dumps(config, indent=2)


async def get_schema() -> str:
    """CKAN API schema reference (abridged)."""
    return """# CKAN Action API Schema Reference (Abridged)

## Package (Dataset) Object
{
  "id": "string",
  "name": "string",
  "title": "string",
  "notes": "string|null",
  "tags": [{"name": "string", "vocabulary_id": "string", "display_name": "string"}],
  "license_id": "string",
  "license_title": "string",
  "license_url": "string",
  "metadata_created": "ISO8601 datetime",
  "metadata_modified": "ISO8601 datetime",
  "organization": {"id": "string", "name": "string", "title": "string"},
  "resources": [
    {
      "id": "string",
      "package_id": "string",
      "name": "string",
      "format": "string",
      "mimetype": "string",
      "size": "int",
      "hash": "string",
      "url": "string",
      "description": "string|null",
      "resource_type": "string|null",
      "datastore_active": "bool"
    }
  ],
  "groups": [{"id": "string", "name": "string", "title": "string"}],
  "tracking_summary": {"recent": "int", "total": "int"}
}

## Organization Object
{
  "id": "string",
  "name": "string",
  "title": "string",
  "description": "string|null",
  "image_url": "string|null",
  "packages": [{"id": "string", "name": "string", "title": "string"}],
  "users": [{"name": "string", "capacity": "string"}],
  "tracking_summary": {"recent": "int", "total": "int"}
}

## Resource Object
{
  "id": "string",
  "package_id": "string",
  "name": "string",
  "format": "string",
  "mimetype": "string",
  "size": "int",
  "hash": "string",
  "url": "string",
  "description": "string|null",
  "resource_type": "string|null",
  "datastore_active": "bool",
  "tracking_summary": {"recent": "int", "total": "int"}
}

## Package Search Response
{
  "help": "string",
  "success": true,
  "result": {
    "count": "int",
    "results": [...],
    "facets": {},
    "search_facets": {}
  }
}

## Organization Search Response
{
  "help": "string",
  "success": true,
  "result": [...]
}
"""


# ---------------------------------------------------------------------------
# Dynamic resource helpers (used by resource templates in server.py)
# ---------------------------------------------------------------------------


async def get_api_docs(portal_key: str) -> str:
    """CKAN API documentation for a specific portal."""
    portal = get_portal(portal_key)
    base_url = portal.api_url.rstrip("/")
    return f"""# CKAN Action API Documentation (API v3)

Base URL: `{base_url}`

## Main Endpoints

### Datasets (Packages)
- `GET /action/package_search` - Search datasets (params: q, start, rows, sort)
- `GET /action/package_show` - Get dataset details (params: id)
- `GET /action/package_list` - List all dataset IDs
- `GET /action/current_package_list_with_resources` - List datasets with resources

### Resources
- `GET /action/resource_show` - Get resource details (params: id)
- `GET /action/resource_search` - Search resources (params: query, limit, offset)

### Organizations
- `GET /action/organization_list` - List organizations (params: all_fields, limit, offset)
- `GET /action/organization_show` - Get organization details (params: id, include_datasets)
- `GET /action/organization_list_for_user` - List orgs for user

### Groups
- `GET /action/group_list` - List groups
- `GET /action/group_show` - Get group details (params: id, include_datasets)

### Tags
- `GET /action/tag_list` - List tags (params: vocabulary_id, all_fields)
- `GET /action/tag_show` - Get tag details

### Common Parameters
- `start` (int): Pagination offset (default: 0)
- `rows` (int): Results per page, max 100 (default: 20)
- `q` (string): Search query (Solr syntax)
- `sort` (string): Sort field (e.g. "score desc, metadata_modified desc")
- `fl` (string): Comma-separated list of fields to return

## Authentication
Include `Authorization` header with API key if required by the portal.

## Rate Limiting
Default: 100 requests/minute (sliding window).

## Response Format
All endpoints return JSON with `success` boolean and `result` object.
Errors follow standard HTTP status codes with `error` object.
"""


async def get_portal_info(portal_key: str) -> str:
    """Information about a specific portal."""
    portal = get_portal(portal_key)
    settings = get_settings()
    portal_settings = settings.get_portal_settings(portal)

    lines = [
        f"# Portal: {portal.name}",
        "",
        f"- **Key**: {portal.key}",
        f"- **API URL**: {portal.api_url}",
        f"- **Catalog URL**: {portal.catalog_url}",
        f"- **Requires auth**: {portal.requires_auth}",
    ]
    if portal.description:
        lines.append(f"- **Description**: {portal.description}")
    if portal_settings.api_key:
        lines.append("- **API key configured**: yes")
    else:
        lines.append("- **API key configured**: no (public access)")

    lines.extend([
        "",
        "## Connection settings",
        f"- Request timeout: {portal_settings.request_timeout}s",
        f"- Max retries: {portal_settings.request_max_retries}s",
        f"- Retry backoff: {portal_settings.retry_backoff_seconds}s",
        f"- Download timeout: {portal_settings.download_timeout}s",
        f"- Max download size: {portal_settings.max_download_size_mb} MB",
        "",
        "## Usage",
        f"Pass `portal=\"{portal.key}\"` to any tool to target this portal.",
    ])
    return "\n".join(lines)


async def get_portals_registry() -> str:
    """All known portals registry."""
    portals = list_portals()
    lines = ["# CKAN Portals Registry", "", "## Portals"]
    for p in portals:
        lines.append(f"### {p['key']} - {p['name']}")
        lines.append(f"- API: {p['api_url']}")
        lines.append(f"- UI: {p['catalog_url']}")
        if p.get("description"):
            lines.append(f"- {p['description']}")
        lines.append("")

    lines.extend([
        "## Adding New Portals",
        "To add a new portal, either:",
        "1. Add a `Portal` entry to `portals.py` (code change), or",
        "2. Set environment variables:",
        "   - `PORTAL_<KEY>_API_URL` (required)",
        "   - `PORTAL_<KEY>_API_KEY` (optional)",
        "   - `PORTAL_<KEY>_REQUEST_TIMEOUT` (optional)",
        "",
        "## Portal Features",
        "All portals use the CKAN platform with Action API v3.",
        "Endpoints are consistent across portals.",
    ])
    return "\n".join(lines)
