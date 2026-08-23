from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from datagouv_mcp_tn.helpers import api_client
from datagouv_mcp_tn.helpers.api_client import (
    CKANError,
    CKANTimeoutError,
    CKANUnavailableError,
    _call_action,
    _retry_wait,
)
from datagouv_mcp_tn.helpers.i18n import (
    DEFAULT_LANGUAGE,
    Language,
    MessageKey,
    resolve_language,
    translate,
)
from datagouv_mcp_tn.helpers.query_cleaner import clean_search_query


def status_error(status_code: int, retry_after: str | None = None) -> httpx.HTTPStatusError:
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.text = "boom"
    if retry_after is not None:
        response.headers = {"Retry-After": retry_after}
    else:
        response.headers = {}
    return httpx.HTTPStatusError(f"HTTP {status_code}", request=MagicMock(), response=response)


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


# --- i18n (TASK-013) ---


@pytest.mark.parametrize(
    "raw,expected",
    [("fr", Language.FRENCH), ("AR", Language.ARABIC), (" en ", Language.ENGLISH)],
)
def test_resolve_language_normalizes(raw, expected):
    assert resolve_language(raw) == expected


def test_resolve_language_falls_back_to_default():
    assert resolve_language("de") == DEFAULT_LANGUAGE
    assert resolve_language(None) == DEFAULT_LANGUAGE


@pytest.mark.parametrize(
    "lang,expected",
    [
        (Language.FRENCH, "Trouvé 5 jeu(x) de données pour « pop »"),
        (Language.ARABIC, "تم العثور على 5 مجموعة(ات) بيانات لـ «pop»"),
        (Language.ENGLISH, "Found 5 dataset(s) for 'pop'"),
    ],
)
def test_translate_formats_per_language(lang, expected):
    assert (
        translate(
            MessageKey.RESULTS_FOUND,
            lang,
            count=5,
            what=translate(MessageKey.WHAT_DATASETS, lang),
            query="pop",
        )
        == expected
    )


def test_translate_missing_key_is_safe():
    assert translate("nope", Language.FRENCH) == "missing translation: nope"


# --- retries & errors (TASK-010) ---


async def test_call_action_retries_on_server_error_then_succeeds():
    ok_response = MagicMock()
    ok_response.json.return_value = {"success": True, "result": {"ok": True}}
    http = mock_http([status_error(502), ok_response])
    with (
        patch.object(api_client, "_http_clients", {}),
        patch("datagouv_mcp_tn.helpers.api_client._get_client", return_value=http),
        patch("datagouv_mcp_tn.helpers.api_client.asyncio.sleep", new=AsyncMock()),
    ):
        result = await _call_action("agridata", "package_search", params={"q": "test"})
    assert result == {"ok": True}
    assert http.get.await_count == 2


async def test_call_action_does_not_retry_on_client_error():
    http = mock_http([status_error(404)])
    with (
        patch.object(api_client, "_http_clients", {}),
        patch("datagouv_mcp_tn.helpers.api_client._get_client", return_value=http),
    ):
        with pytest.raises(CKANError, match="404"):
            await _call_action("agridata", "package_show", params={"id": "missing"})
    assert http.get.await_count == 1


@pytest.mark.parametrize("status_code", [429, 500, 502, 503, 504])
async def test_call_action_retries_retryable_statuses(status_code):
    http = mock_http(
        [status_error(status_code), status_error(status_code), status_error(status_code)]
    )
    with (
        patch.object(api_client, "_http_clients", {}),
        patch("datagouv_mcp_tn.helpers.api_client._get_client", return_value=http),
        patch("datagouv_mcp_tn.helpers.api_client.asyncio.sleep", new=AsyncMock()),
    ):
        with pytest.raises(CKANError, match=str(status_code)):
            await _call_action("agridata", "package_search", params={"q": "test"})
    # initial attempt + REQUEST_MAX_RETRIES=2
    assert http.get.await_count == 3


async def test_call_action_retries_on_timeout_and_raises_typed_error():
    http = mock_http([httpx.ReadTimeout("timed out")] * 3)
    with (
        patch.object(api_client, "_http_clients", {}),
        patch("datagouv_mcp_tn.helpers.api_client._get_client", return_value=http),
        patch("datagouv_mcp_tn.helpers.api_client.asyncio.sleep", new=AsyncMock()),
    ):
        with pytest.raises(CKANTimeoutError, match="timed out"):
            await _call_action("agridata", "package_search", params={"q": "test"})


async def test_call_action_raises_unavailable_on_connection_failure():
    http = mock_http([httpx.ConnectError("refused")] * 3)
    with (
        patch.object(api_client, "_http_clients", {}),
        patch("datagouv_mcp_tn.helpers.api_client._get_client", return_value=http),
        patch("datagouv_mcp_tn.helpers.api_client.asyncio.sleep", new=AsyncMock()),
    ):
        with pytest.raises(CKANUnavailableError, match="refused"):
            await _call_action("agridata", "package_search", params={"q": "test"})
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
    # Need to pass a PortalSettings-like object
    from datagouv_mcp_tn.helpers.config import PortalSettings

    portal_settings = PortalSettings(api_url="https://test/api/3", request_timeout=30.0)
    assert _retry_wait(response, attempt, portal_settings) == pytest.approx(expected)


def test_retry_wait_ignores_invalid_retry_after():
    response = MagicMock()
    response.headers = {"Retry-After": "soon"}
    from datagouv_mcp_tn.helpers.config import PortalSettings

    portal_settings = PortalSettings(api_url="https://test/api/3", request_timeout=30.0)
    assert _retry_wait(response, 0, portal_settings) == pytest.approx(0.5)


# --- direct api_client high-level functions (TASK-010+) ---


@pytest.mark.parametrize(
    "func_name,args,expected_key",
    [
        (
            "search_datasets",
            {"query": "q", "page": 1, "page_size": 20, "portal_key": "agridata"},
            "data",
        ),
        ("suggest_datasets", {"partial_query": "q", "size": 10, "portal_key": "agridata"}, None),
        ("get_dataset_details", {"dataset_id": "ds-1", "portal_key": "agridata"}, "id"),
        (
            "get_resource_details",
            {"dataset_id": "ds-1", "resource_id": "res-1", "portal_key": "agridata"},
            "id",
        ),
        ("get_organization_details", {"organization_id": "org-1", "portal_key": "agridata"}, "id"),
        (
            "search_dataservices",
            {"query": "q", "page": 1, "page_size": 20, "portal_key": "agridata"},
            "data",
        ),
        ("get_dataservice_details", {"dataservice_id": "ds-1", "portal_key": "agridata"}, "id"),
        ("list_dataset_resources", {"dataset_id": "ds-1", "portal_key": "agridata"}, None),
    ],
)
async def test_api_client_high_level_functions(func_name, args, expected_key):
    http = AsyncMock()
    response = MagicMock()
    response.json.return_value = {"success": True, "result": {"id": "test", "data": []}}
    http.get = AsyncMock(return_value=response)
    with (
        patch.object(api_client, "_http_clients", {}),
        patch("datagouv_mcp_tn.helpers.api_client._get_client", return_value=http),
    ):
        func = getattr(api_client, func_name)
        result = await func(**args)
    if expected_key:
        assert result is not None


async def test_search_organizations_filters_locally():
    http = AsyncMock()
    response = MagicMock()
    response.json.return_value = {
        "success": True,
        "result": [
            {"id": "org-1", "name": "INS", "title": "Statistics", "description": "Stats agency"},
            {"id": "org-2", "name": "Ministry", "title": "Ministry", "description": "Gov"},
        ],
    }
    http.get = AsyncMock(return_value=response)
    with (
        patch.object(api_client, "_http_clients", {}),
        patch("datagouv_mcp_tn.helpers.api_client._get_client", return_value=http),
    ):
        result = await api_client.search_organizations("stat", portal_key="agridata")
    assert result["total"] == 1
    assert result["data"][0]["id"] == "org-1"


async def test_get_object_metrics_dataset():
    http = AsyncMock()
    response = MagicMock()
    response.json.return_value = {
        "success": True,
        "result": {
            "id": "ds-1",
            "tracking_summary": {"total": 100},
            "resources": [{"tracking_summary": {"total": 50}}],
        },
    }
    http.get = AsyncMock(return_value=response)
    with (
        patch.object(api_client, "_http_clients", {}),
        patch("datagouv_mcp_tn.helpers.api_client._get_client", return_value=http),
    ):
        result = await api_client.get_object_metrics("dataset", "ds-1", portal_key="agridata")
    assert result["views"] == 100
    assert result["downloads"] == 50
    assert result["portal"] == "agridata"


async def test_get_object_metrics_organization():
    http = AsyncMock()
    response = MagicMock()
    response.json.return_value = {
        "success": True,
        "result": {"id": "org-1", "packages": [{"id": "p1"}, {"id": "p2"}]},
    }
    http.get = AsyncMock(return_value=response)
    with (
        patch.object(api_client, "_http_clients", {}),
        patch("datagouv_mcp_tn.helpers.api_client._get_client", return_value=http),
    ):
        result = await api_client.get_object_metrics("organization", "org-1", portal_key="agridata")
    assert result["dataset_count"] == 2
    assert result["portal"] == "agridata"


async def test_get_object_metrics_unknown_type():
    result = await api_client.get_object_metrics("unknown", "obj-1", portal_key="agridata")
    assert result["portal"] == "agridata"
