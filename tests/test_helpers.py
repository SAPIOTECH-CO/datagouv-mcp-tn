from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from datagouv_mcp_tn.helpers import api_client
from datagouv_mcp_tn.helpers.api_client import UDataError, _get_json, _retry_wait
from datagouv_mcp_tn.helpers.pagination import PaginationInfo
from datagouv_mcp_tn.helpers.query_cleaner import clean_search_query


def status_error(status_code: int, retry_after: str | None = None) -> httpx.HTTPStatusError:
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.text = "boom"
    if retry_after is not None:
        response.headers = {"Retry-After": retry_after}
    else:
        response.headers = {}
    return httpx.HTTPStatusError(
        f"HTTP {status_code}", request=MagicMock(), response=response
    )


def mock_http(side_effects: list) -> AsyncMock:
    http = AsyncMock()
    http.get = AsyncMock(side_effect=side_effects)
    return http


# --- query cleaner (TASK-011) ---


@pytest.mark.parametrize(
    "raw,cleaned",
    [
        ("données population", "population"),
        ("Fichier budget 2024", "budget 2024"),
        ("csv tableau recettes", "recettes"),
        ("بيانات سكان تونس", "سكان تونس"),
        ("population tunisie", "population tunisie"),
        ("", ""),
    ],
)
def test_clean_search_query_removes_stop_words(raw, cleaned):
    assert clean_search_query(raw) == cleaned


def test_clean_search_query_returns_empty_when_all_generic():
    assert clean_search_query("données fichier csv") == ""


# --- pagination (TASK-012) ---


def test_pagination_from_udata_reads_fields():
    info = PaginationInfo.from_udata({"total": 231, "page": 2, "page_size": 20})
    assert (info.page, info.page_size, info.total) == (2, 20, 231)


def test_pagination_from_udapplies_defaults_for_missing_fields():
    info = PaginationInfo.from_udata({}, default_page=3, default_page_size=50)
    assert (info.page, info.page_size, info.total) == (3, 50, 0)


def test_pagination_total_pages_rounds_up():
    assert PaginationInfo(1, 20, 231).total_pages == 12
    assert PaginationInfo(1, 20, 40).total_pages == 2
    assert PaginationInfo(1, 20, 0).total_pages == 0


def test_pagination_describe_formats_summary():
    assert PaginationInfo(2, 20, 231).describe() == "Page 2/12 · 231 results"
    assert PaginationInfo(1, 20, 1).describe() == "Page 1/1 · 1 result"


# --- retries & errors (TASK-010) ---


async def test_get_json_retries_on_server_error_then_succeeds():
    ok_response = MagicMock()
    ok_response.json.return_value = {"ok": True}
    http = mock_http([status_error(502), ok_response])
    with (
        patch.object(api_client, "_http", None),
        patch("datagouv_mcp_tn.helpers.api_client._client", return_value=http),
        patch("datagouv_mcp_tn.helpers.api_client.asyncio.sleep", new=AsyncMock()),
    ):
        result = await _get_json("/datasets/")
    assert result == {"ok": True}
    assert http.get.await_count == 2


async def test_get_json_does_not_retry_on_client_error():
    http = mock_http([status_error(404)])
    with (
        patch.object(api_client, "_http", None),
        patch("datagouv_mcp_tn.helpers.api_client._client", return_value=http),
    ):
        with pytest.raises(UDataError, match="404"):
            await _get_json("/datasets/missing/")
    assert http.get.await_count == 1


@pytest.mark.parametrize("status_code", [429, 500, 502, 503, 504])
async def test_get_json_retries_retryable_statuses(status_code):
    http = mock_http([status_error(status_code), status_error(status_code), status_error(status_code)])
    with (
        patch.object(api_client, "_http", None),
        patch("datagouv_mcp_tn.helpers.api_client._client", return_value=http),
        patch("datagouv_mcp_tn.helpers.api_client.asyncio.sleep", new=AsyncMock()),
    ):
        with pytest.raises(UDataError, match=str(status_code)):
            await _get_json("/datasets/")
    # initial attempt + REQUEST_MAX_RETRIES=2
    assert http.get.await_count == 3


async def test_get_json_retries_on_timeout_and_raises_typed_error():
    http = mock_http([httpx.ReadTimeout("timed out")] * 3)
    with (
        patch.object(api_client, "_http", None),
        patch("datagouv_mcp_tn.helpers.api_client._client", return_value=http),
        patch("datagouv_mcp_tn.helpers.api_client.asyncio.sleep", new=AsyncMock()),
    ):
        with pytest.raises(api_client.UDataTimeoutError, match="timed out"):
            await _get_json("/datasets/")


async def test_get_json_raises_unavailable_on_connection_failure():
    http = mock_http([httpx.ConnectError("refused")] * 3)
    with (
        patch.object(api_client, "_http", None),
        patch("datagouv_mcp_tn.helpers.api_client._client", return_value=http),
        patch("datagouv_mcp_tn.helpers.api_client.asyncio.sleep", new=AsyncMock()),
    ):
        with pytest.raises(api_client.UDataUnavailableError, match="refused"):
            await _get_json("/datasets/")
    assert http.get.await_count == 3


@pytest.mark.parametrize(
    "retry_after,attempt,expected",
    [
        ("7", 0, 7.0),  # Retry-After wins when present
        (None, 0, 0.5),  # backoff base
        (None, 1, 1.0),  # exponential
        (None, 2, 2.0),  # exponential squared
    ],
)
def test_retry_wait_computation(retry_after, attempt, expected):
    response = MagicMock()
    response.headers = {"Retry-After": retry_after} if retry_after else {}
    assert _retry_wait(response, attempt) == pytest.approx(expected)


def test_retry_wait_ignores_invalid_retry_after():
    response = MagicMock()
    response.headers = {"Retry-After": "soon"}
    assert _retry_wait(response, 0) == pytest.approx(0.5)
