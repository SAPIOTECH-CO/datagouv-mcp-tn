"""Tests for dynamic portal registry."""

import os
from unittest.mock import patch

import pytest

from datagouv_mcp_tn.portals import (
    get_portal,
    get_portal_by_api_url,
    list_portals,
    refresh_portals,
)


def test_get_portal_returns_default():
    portal = get_portal()
    assert portal.key == "agridata"


def test_get_portal_returns_specific():
    portal = get_portal("data-gov-tn")
    assert portal.key == "data-gov-tn"
    assert portal.name == "Presidency of the Government - data.gov.tn"


def test_get_portal_raises_for_unknown_key():
    with pytest.raises(ValueError, match="Unknown portal"):
        get_portal("unknown-portal")


def test_get_portal_by_api_url_finds_portal():
    portal = get_portal_by_api_url("https://catalog.agridata.tn/api/3")
    assert portal is not None
    assert portal.key == "agridata"


def test_get_portal_by_api_url_returns_none_for_unknown():
    portal = get_portal_by_api_url("https://unknown.example.com/api/3")
    assert portal is None


def test_list_portals_returns_list_of_dicts():
    portals = list_portals()
    assert isinstance(portals, list)
    assert len(portals) >= 5
    keys = [p["key"] for p in portals]
    assert "agridata" in keys
    assert "data-gov-tn" in keys


def test_refresh_portals_rebuilds_registry():
    with patch.dict(os.environ, {"PORTAL_TEST_PORTAL_API_URL": "https://test.example.com/api/3"}):
        refresh_portals()
        portals = list_portals()
        keys = [p["key"] for p in portals]
        assert "test-portal" in keys

    # Cleanup: refresh back to defaults
    refresh_portals()
    portals = list_portals()
    keys = [p["key"] for p in portals]
    assert "test-portal" not in keys


def test_env_portal_with_optional_overrides():
    env = {
        "PORTAL_MY_PORTAL_API_URL": "https://custom.example.com/api/3",
        "PORTAL_MY_PORTAL_NAME": "Custom Portal",
        "PORTAL_MY_PORTAL_CATALOG_URL": "https://custom.example.com",
        "PORTAL_MY_PORTAL_REQUIRES_AUTH": "true",
    }
    with patch.dict(os.environ, env):
        refresh_portals()
        portal = get_portal("my-portal")
        assert portal.name == "Custom Portal"
        assert portal.catalog_url == "https://custom.example.com"
        assert portal.requires_auth is True

    refresh_portals()
