"""Integration tests for CKAN API client flow (TASK-009, TASK-037)."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from datagouv_mcp_tn.helpers import api_client
from datagouv_mcp_tn.helpers.api_client import (
    CKANTimeoutError,
    CKANUnavailableError,
    _call_action,
)


def _make_response(json_data, status_code=200):
    response = MagicMock()
    response.json.return_value = json_data
    response.status_code = status_code
    response.raise_for_status = MagicMock()
    response.headers = {}
    return response


@pytest.mark.asyncio
async def test_call_action_happy_path():
    http = AsyncMock()
    response = _make_response(
        {"success": True, "result": {"id": "ds-1", "title": "Test"}}
    )
    http.get = AsyncMock(return_value=response)
    with (
        patch.object(api_client, "_http_clients", {}),
        patch(
            "datagouv_mcp_tn.helpers.api_client._get_client", return_value=http
        ),
    ):
        result = await _call_action("agridata", "package_show", params={"id": "ds-1"})
    assert result["id"] == "ds-1"
    assert result["title"] == "Test"


@pytest.mark.asyncio
async def test_call_action_retries_on_server_error():
    ok_response = _make_response(
        {"success": True, "result": {"ok": True}}
    )
    error_response = MagicMock()
    error_response.status_code = 502
    error_response.text = "Bad Gateway"
    error_response.headers = {}
    error_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "502", request=MagicMock(), response=error_response
        )
    )

    http = AsyncMock()
    http.get = AsyncMock(
        side_effect=[
            httpx.HTTPStatusError(
                "502", request=MagicMock(), response=error_response
            ),
            ok_response,
        ]
    )
    with (
        patch.object(api_client, "_http_clients", {}),
        patch(
            "datagouv_mcp_tn.helpers.api_client._get_client", return_value=http
        ),
        patch(
            "datagouv_mcp_tn.helpers.api_client.asyncio.sleep",
            new=AsyncMock(),
        ),
    ):
        result = await _call_action(
            "agridata", "package_search", params={"q": "test"}
        )
    assert result == {"ok": True}
    assert http.get.await_count == 2


@pytest.mark.asyncio
async def test_call_action_raises_timeout():
    http = AsyncMock()
    http.get = AsyncMock(side_effect=httpx.ReadTimeout("timed out"))
    with (
        patch.object(api_client, "_http_clients", {}),
        patch(
            "datagouv_mcp_tn.helpers.api_client._get_client", return_value=http
        ),
        patch(
            "datagouv_mcp_tn.helpers.api_client.asyncio.sleep",
            new=AsyncMock(),
        ),
    ):
        with pytest.raises(CKANTimeoutError, match="timed out"):
            await _call_action(
                "agridata", "package_search", params={"q": "test"}
            )
    assert http.get.await_count == 3


@pytest.mark.asyncio
async def test_call_action_raises_unavailable():
    http = AsyncMock()
    http.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
    with (
        patch.object(api_client, "_http_clients", {}),
        patch(
            "datagouv_mcp_tn.helpers.api_client._get_client", return_value=http
        ),
        patch(
            "datagouv_mcp_tn.helpers.api_client.asyncio.sleep",
            new=AsyncMock(),
        ),
    ):
        with pytest.raises(CKANUnavailableError, match="refused"):
            await _call_action(
                "agridata", "package_search", params={"q": "test"}
            )
    assert http.get.await_count == 3


@pytest.mark.asyncio
async def test_ssl_verify_false_for_data_gov_tn():
    from datagouv_mcp_tn.portals import get_portal

    portal = get_portal("data-gov-tn")
    assert portal.ssl_verify is False


@pytest.mark.asyncio
async def test_ssl_verify_true_for_other_portals():
    from datagouv_mcp_tn.portals import get_portal

    for key in ["agridata", "culture", "industrie", "transport"]:
        portal = get_portal(key)
        assert portal.ssl_verify is True
