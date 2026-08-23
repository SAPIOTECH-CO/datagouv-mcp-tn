"""Async client for the uData REST API of data.gouv.tn (API v1).

Hardened for production use:

- per-request timeout (``REQUEST_TIMEOUT``);
- connect-level retries handled by httpx itself;
- request-level retries with exponential backoff on transient failures
  (timeouts, connection errors, 429 and 5xx responses), honoring
  ``Retry-After`` when the server sends one;
- typed errors: :class:`UDataTimeoutError` and :class:`UDataUnavailableError`
  both subclass :class:`UDataError`.
"""

import asyncio
import logging
from typing import Any

import httpx

from datagouv_mcp_tn.helpers.config import get_settings
from datagouv_mcp_tn.helpers.logging import MAIN_LOGGER_NAME

logger = logging.getLogger(MAIN_LOGGER_NAME)

# Status codes worth retrying: rate limiting + transient server errors.
RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


class UDataError(RuntimeError):
    pass


class UDataTimeoutError(UDataError):
    pass


class UDataUnavailableError(UDataError):
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
            # Connect-level retries (only covers connection establishment).
            transport=httpx.AsyncHTTPTransport(retries=1),
            follow_redirects=True,
        )
    return _http


async def aclose() -> None:
    global _http
    if _http is not None:
        await _http.aclose()
        _http = None


def _retry_wait(response: httpx.Response | None, attempt: int) -> float:
    """Seconds to wait before retry ``attempt + 1``.

    Honors a numeric Retry-After header; otherwise uses exponential
    backoff based on RETRY_BACKOFF_SECONDS.
    """
    settings = get_settings()
    if response is not None:
        retry_after = response.headers.get("Retry-After")
        if retry_after is not None:
            try:
                return max(0.0, float(retry_after))
            except ValueError:
                pass
    return settings.retry_backoff_seconds * (2**attempt)


def _is_retryable(error: httpx.HTTPError) -> bool:
    if isinstance(error, (httpx.TimeoutException, httpx.TransportError)):
        return True
    if isinstance(error, httpx.HTTPStatusError):
        return error.response.status_code in RETRYABLE_STATUS_CODES
    return False


def _to_udata_error(url: str, error: httpx.HTTPError) -> UDataError:
    if isinstance(error, httpx.TimeoutException):
        timeout = get_settings().request_timeout
        return UDataTimeoutError(
            f"uData API timed out after {timeout}s for {url}. "
            "The portal may be slow or unreachable."
        )
    if isinstance(error, httpx.TransportError):
        return UDataUnavailableError(f"uData API connection failed for {url}: {error}")
    if isinstance(error, httpx.HTTPStatusError):
        response = error.response
        hint = ""
        if response.status_code == 429:
            hint = " Rate limited — try again in a moment."
        elif response.status_code >= 500:
            hint = " The portal may be temporarily unavailable."
        return UDataError(
            f"uData API returned {response.status_code} for {url}: {response.text[:200]}.{hint}"
        )
    return UDataError(f"uData API request failed for {url}: {error}")


async def _get_json(path: str, params: dict[str, Any] | None = None) -> Any:
    url = path
    logger.debug("uData API GET %s params=%s", url, params)
    settings = get_settings()
    max_attempts = max(0, settings.request_max_retries) + 1

    last_error: UDataError | None = None
    for attempt in range(max_attempts):
        try:
            response = await _client().get(url, params=params)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            udata_error = _to_udata_error(url, exc)
            if attempt < max_attempts - 1 and _is_retryable(exc):
                wait = _retry_wait(
                    exc.response if isinstance(exc, httpx.HTTPStatusError) else None,
                    attempt,
                )
                logger.warning(
                    "uData API attempt %d/%d failed (%s); retrying in %.1fs",
                    attempt + 1,
                    max_attempts,
                    udata_error,
                    wait,
                )
                await asyncio.sleep(wait)
                continue
            raise udata_error from exc

        try:
            return response.json()
        except ValueError as exc:
            raise UDataError(f"uData API returned invalid JSON for {url}") from exc

    raise last_error or UDataError(f"uData API request failed for {url}")


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
