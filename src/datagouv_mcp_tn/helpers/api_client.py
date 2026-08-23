"""Async client for the uData REST API of data.gouv.tn (API v1)."""

import logging
from typing import Any

import httpx

from datagouv_mcp_tn.helpers.config import get_settings
from datagouv_mcp_tn.helpers.logging import MAIN_LOGGER_NAME

logger = logging.getLogger(MAIN_LOGGER_NAME)


class UDataError(RuntimeError):
    pass


_http: httpx.AsyncClient | None = None


def _client() -> httpx.AsyncClient:
    global _http
    if _http is None:
        settings = get_settings()
        headers = {
            "Accept": "application/json",
            "User-Agent": "datagouv-mcp-tn/0.1.0",
        }
        if settings.data_gouv_tn_api_key:
            headers["X-API-KEY"] = settings.data_gouv_tn_api_key
        _http = httpx.AsyncClient(
            base_url=settings.data_gouv_tn_api_url.rstrip("/"),
            headers=headers,
            timeout=settings.request_timeout,
        )
    return _http


async def aclose() -> None:
    global _http
    if _http is not None:
        await _http.aclose()
        _http = None


async def _get_json(path: str, params: dict[str, Any] | None = None) -> Any:
    url = path
    logger.debug("uData API GET %s params=%s", url, params)
    try:
        response = await _client().get(url, params=params)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        failed_response = exc.response
        raise UDataError(
            f"uData API returned {failed_response.status_code} for {url}: "
            f"{failed_response.text[:200]}"
        ) from exc
    except httpx.HTTPError as exc:
        raise UDataError(f"uData API request failed for {url}: {exc}") from exc
    try:
        return response.json()
    except ValueError as exc:
        raise UDataError(f"uData API returned invalid JSON for {url}") from exc


async def search_datasets(
    query: str,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """Search datasets by keywords. Returns the raw paginated payload."""
    return await _get_json(
        "/datasets/",
        params={"q": query, "page": page, "page_size": min(page_size, 100)},
    )


async def suggest_datasets(
    partial_query: str,
    size: int = 10,
) -> list[dict[str, Any]]:
    """Autocomplete dataset titles from a partial query."""
    data = await _get_json(
        "/datasets/suggest/",
        params={"q": partial_query, "size": min(size, 50)},
    )
    return data if isinstance(data, list) else []


async def get_dataset_details(dataset_id: str) -> dict[str, Any]:
    """Fetch the complete dataset payload from the API v1 endpoint."""
    return await _get_json(f"/datasets/{dataset_id}/")


async def get_resource_details(dataset_id: str, resource_id: str) -> dict[str, Any]:
    """Locate a single resource inside a dataset payload.

    The uData v1 API has no dedicated resource endpoint, so the dataset is
    fetched and the resource extracted.
    """
    dataset = await get_dataset_details(dataset_id)
    for resource in dataset.get("resources", []):
        if resource.get("id") == resource_id:
            return resource
    raise UDataError(
        f"Resource '{resource_id}' not found in dataset '{dataset_id}'."
        " Use list_dataset_resources to see available resources."
    )


async def search_organizations(
    query: str,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """Search publishing organizations by keywords."""
    return await _get_json(
        "/organizations/",
        params={"q": query, "page": page, "page_size": min(page_size, 100)},
    )


async def get_organization_details(organization_id: str) -> dict[str, Any]:
    """Fetch the complete organization payload."""
    return await _get_json(f"/organizations/{organization_id}/")
