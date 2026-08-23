"""Async client for the CKAN Action API (API v3) with multi-portal support.

Supports all Tunisian CKAN portals with per-portal configuration.
"""

import asyncio
import logging
from typing import Any

import httpx

from datagouv_mcp_tn.helpers.config import PortalSettings, get_settings
from datagouv_mcp_tn.helpers.logging import MAIN_LOGGER_NAME
from datagouv_mcp_tn.portals import get_portal

logger = logging.getLogger(MAIN_LOGGER_NAME)

# Status codes worth retrying: rate limiting + transient server errors.
RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


class CKANError(RuntimeError):
    """Base CKAN API error."""
    def __init__(self, message: str, portal_key: str | None = None):
        super().__init__(message)
        self.portal_key = portal_key


class CKANTimeoutError(CKANError):
    pass


class CKANUnavailableError(CKANError):
    pass


# Per-portal HTTP client pool
_http_clients: dict[str, httpx.AsyncClient] = {}


def _get_client(portal_key: str) -> httpx.AsyncClient:
    """Get or create HTTP client for a portal."""
    if portal_key not in _http_clients:
        settings = get_settings()
        portal = get_portal(portal_key)
        portal_settings = settings.get_portal_settings(portal)

        headers = {
            "Accept": "application/json",
            "User-Agent": "datagouv-mcp-tn/0.1.0",
        }
        if portal_settings.api_key:
            headers["Authorization"] = portal_settings.api_key

        _http_clients[portal_key] = httpx.AsyncClient(
            base_url=portal_settings.api_url.rstrip("/"),
            headers=headers,
            timeout=portal_settings.request_timeout,
            transport=httpx.AsyncHTTPTransport(retries=1, verify=portal_settings.ssl_verify),
            follow_redirects=True,
        )
    return _http_clients[portal_key]


async def aclose() -> None:
    """Close all HTTP clients."""
    for client in _http_clients.values():
        await client.aclose()
    _http_clients.clear()


def _retry_wait(
    response: httpx.Response | None,
    attempt: int,
    portal_settings: PortalSettings,
) -> float:
    """Seconds to wait before retry ``attempt + 1``."""
    if response is not None:
        retry_after = response.headers.get("Retry-After")
        if retry_after is not None:
            try:
                return max(0.0, float(retry_after))
            except ValueError:
                pass
    return portal_settings.retry_backoff_seconds * (2**attempt)


def _is_retryable(error: httpx.HTTPError) -> bool:
    if isinstance(error, (httpx.TimeoutException, httpx.TransportError)):
        return True
    if isinstance(error, httpx.HTTPStatusError):
        return error.response.status_code in RETRYABLE_STATUS_CODES
    return False


def _to_ckan_error(url: str, error: httpx.HTTPError, portal_key: str) -> CKANError:
    if isinstance(error, httpx.TimeoutException):
        settings = get_settings()
        portal = get_portal(portal_key)
        portal_settings = settings.get_portal_settings(portal)
        return CKANTimeoutError(
            f"CKAN API timed out after {portal_settings.request_timeout}s for {url}. "
            "The portal may be slow or unreachable.",
            portal_key=portal_key,
        )
    if isinstance(error, httpx.TransportError):
        return CKANUnavailableError(
            f"CKAN API connection failed for {url}: {error}", portal_key=portal_key
        )
    if isinstance(error, httpx.HTTPStatusError):
        response = error.response
        hint = ""
        if response.status_code == 429:
            hint = " Rate limited — try again in a moment."
        elif response.status_code >= 500:
            hint = " The portal may be temporarily unavailable."
        return CKANError(
            f"CKAN API returned {response.status_code} for {url}: {response.text[:200]}.{hint}",
            portal_key=portal_key,
        )
    return CKANError(f"CKAN API request failed for {url}: {error}", portal_key=portal_key)


async def _call_action(
    portal_key: str,
    action: str,
    params: dict[str, Any] | None = None,
) -> Any:
    """Call a CKAN action API endpoint on a specific portal."""
    settings = get_settings()
    portal = get_portal(portal_key)
    portal_settings = settings.get_portal_settings(portal)

    url = f"/action/{action}"
    logger.debug("CKAN API portal=%s action=%s params=%s", portal_key, action, params)
    max_attempts = max(0, portal_settings.request_max_retries) + 1

    client = _get_client(portal_key)
    last_error: CKANError | None = None

    for attempt in range(max_attempts):
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            ckan_error = _to_ckan_error(url, exc, portal_key)
            if attempt < max_attempts - 1 and _is_retryable(exc):
                wait = _retry_wait(
                    exc.response if isinstance(exc, httpx.HTTPStatusError) else None,
                    attempt,
                    portal_settings,
                )
                logger.warning(
                    "CKAN API portal=%s attempt %d/%d failed (%s); retrying in %.1fs",
                    portal_key, attempt + 1, max_attempts, ckan_error, wait,
                )
                await asyncio.sleep(wait)
                continue
            raise ckan_error from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise CKANError(
                f"CKAN API returned invalid JSON for {url}", portal_key=portal_key
            ) from exc

        if not data.get("success", False):
            error_msg = data.get("error", {}).get("message", "Unknown error")
            raise CKANError(f"CKAN API error for {action}: {error_msg}", portal_key=portal_key)

        return data.get("result")

    raise last_error or CKANError(f"CKAN API request failed for {action}", portal_key=portal_key)


# --- High-level API functions (accept optional portal_key) ---

async def search_datasets(
    query: str,
    page: int = 1,
    page_size: int = 20,
    portal_key: str | None = None,
) -> dict[str, Any]:
    """Search datasets by keywords. Returns the raw paginated payload."""
    portal = get_portal(portal_key)
    result = await _call_action(
        portal.key,
        "package_search",
        params={
            "q": query,
            "start": (page - 1) * page_size,
            "rows": min(page_size, 100),
        },
    )
    return {
        "total": result.get("count", 0),
        "page": page,
        "page_size": page_size,
        "data": result.get("results", []),
        "portal": portal.key,
    }


async def suggest_datasets(
    partial_query: str,
    size: int = 10,
    portal_key: str | None = None,
) -> list[dict[str, Any]]:
    """Autocomplete dataset titles from a partial query."""
    portal = get_portal(portal_key)
    result = await _call_action(
        portal.key,
        "package_search",
        params={
            "q": f"title:{partial_query}*",
            "rows": min(size, 50),
            "fl": "id,title",
        },
    )
    return [{"id": pkg["id"], "title": pkg["title"]} for pkg in result.get("results", [])]


async def get_dataset_details(
    dataset_id: str,
    portal_key: str | None = None,
) -> dict[str, Any]:
    """Fetch the complete dataset payload from the CKAN API."""
    portal = get_portal(portal_key)
    return await _call_action(portal.key, "package_show", params={"id": dataset_id})


async def get_resource_details(
    dataset_id: str,
    resource_id: str,
    portal_key: str | None = None,
) -> dict[str, Any]:
    """Fetch a single resource by ID."""
    portal = get_portal(portal_key)
    return await _call_action(portal.key, "resource_show", params={"id": resource_id})


async def search_organizations(
    query: str,
    page: int = 1,
    page_size: int = 20,
    portal_key: str | None = None,
) -> dict[str, Any]:
    """Search publishing organizations by keywords."""
    portal = get_portal(portal_key)

    # First try organization_list with local filtering
    result = await _call_action(
        portal.key,
        "organization_list",
        params={
            "all_fields": True,
            "limit": 1000,
        },
    )
    orgs = [
        org for org in result
        if query.lower() in org.get("name", "").lower()
        or query.lower() in org.get("title", "").lower()
        or query.lower() in org.get("description", "").lower()
    ]

    # If no results, fall back to searching datasets and extracting orgs
    if not orgs:
        import json as json_lib
        pkg_result = await _call_action(
            portal.key,
            "package_search",
            params={
                "q": query,
                "rows": 100,
                "facet.field": json_lib.dumps(["organization"]),
                "facet.limit": 50,
            },
        )
        seen_orgs = set()
        for pkg in pkg_result.get("results", []):
            org = pkg.get("organization", {})
            org_id = org.get("id")
            if org_id and org_id not in seen_orgs:
                seen_orgs.add(org_id)
                orgs.append(org)

    start = (page - 1) * page_size
    end = start + page_size
    return {
        "total": len(orgs),
        "page": page,
        "page_size": page_size,
        "data": orgs[start:end],
        "portal": portal.key,
    }


async def get_organization_details(
    organization_id: str,
    portal_key: str | None = None,
) -> dict[str, Any]:
    """Fetch the complete organization payload."""
    portal = get_portal(portal_key)
    return await _call_action(portal.key, "organization_show", params={"id": organization_id})


async def search_dataservices(
    query: str,
    page: int = 1,
    page_size: int = 20,
    portal_key: str | None = None,
) -> dict[str, Any]:
    """Search dataservices (published APIs) by keywords."""
    portal = get_portal(portal_key)
    result = await _call_action(
        portal.key,
        "package_search",
        params={
            "q": f"{query} type:dataservice",
            "start": (page - 1) * page_size,
            "rows": min(page_size, 100),
        },
    )
    return {
        "total": result.get("count", 0),
        "page": page,
        "page_size": page_size,
        "data": result.get("results", []),
        "portal": portal.key,
    }


async def get_dataservice_details(
    dataservice_id: str,
    portal_key: str | None = None,
) -> dict[str, Any]:
    """Fetch the complete dataservice payload."""
    portal = get_portal(portal_key)
    return await _call_action(portal.key, "package_show", params={"id": dataservice_id})


async def get_object_metrics(
    object_type: str,
    object_id: str,
    portal_key: str | None = None,
) -> dict[str, Any]:
    """Fetch metrics for a dataset/organization/dataservice/reuse."""
    portal = get_portal(portal_key)
    if object_type == "dataset":
        pkg = await _call_action(portal.key, "package_show", params={"id": object_id})
        return {
            "views": pkg.get("tracking_summary", {}).get("total", 0),
            "downloads": sum(
                r.get("tracking_summary", {}).get("total", 0) for r in pkg.get("resources", [])
            ),
            "portal": portal.key,
        }
    if object_type == "organization":
        org = await _call_action(
            portal.key, "organization_show", params={"id": object_id, "include_datasets": True}
        )
        return {
            "dataset_count": len(org.get("packages", [])),
            "portal": portal.key,
        }
    return {"portal": portal.key}


async def list_dataset_resources(
    dataset_id: str,
    portal_key: str | None = None,
) -> list[dict[str, Any]]:
    """List all resources for a dataset."""
    portal = get_portal(portal_key)
    pkg = await _call_action(portal.key, "package_show", params={"id": dataset_id})
    return pkg.get("resources", [])


async def get_group_details(
    group_id: str,
    portal_key: str | None = None,
) -> dict[str, Any]:
    """Fetch group details."""
    portal = get_portal(portal_key)
    return await _call_action(portal.key, "group_show", params={"id": group_id})
