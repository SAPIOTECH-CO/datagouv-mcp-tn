"""Tests for FastMCP context providers."""

from unittest.mock import patch

from datagouv_mcp_tn.helpers.context import (
    Depends,
    get_default_language,
    get_default_portal,
    get_portal_or_default,
)
from datagouv_mcp_tn.helpers.i18n import Language


def test_get_default_portal_returns_key():
    with patch("datagouv_mcp_tn.helpers.context.get_default_portal_key", return_value="agridata"):
        result = get_default_portal()
    assert result == "agridata"


def test_get_default_language_returns_language():
    with patch("datagouv_mcp_tn.helpers.context.get_settings") as mock_settings:
        mock_settings.return_value.default_language = "fr"
        result = get_default_language()
    assert result == Language.FRENCH


def test_get_portal_or_default_uses_provider():
    result = get_portal_or_default("data-gov-tn")
    assert result == "data-gov-tn"


def test_get_portal_or_default_falls_back():
    with patch("datagouv_mcp_tn.helpers.context.get_default_portal", return_value="agridata"):
        result = get_portal_or_default(None)
    assert result == "agridata"


def test_depends_is_importable():
    assert Depends is not None
