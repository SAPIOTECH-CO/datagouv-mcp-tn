"""Portal registry for CKAN open data portals.

Portals are discovered from three sources, in order of precedence:

1. **Environment variables** — any ``PORTAL_<KEY>_API_URL`` variable creates
   a dynamic portal entry at startup.  This lets operators add new portals
   without touching code.
2. **Built-in defaults** — the ``PORTALS`` tuple ships with known Tunisian
   CKAN portals.
3. **CKAN discovery** — if the default portal exposes a ``site_url`` or
   ``package_list`` endpoint, additional portals can be inferred (future).

The registry is built once at import time and cached.  Call ``refresh_portals()``
to rebuild it after changing environment variables.
"""

from __future__ import annotations

import dataclasses
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True)
class Portal:
    """Configuration for a CKAN portal."""

    key: str  # Unique identifier (slug)
    name: str  # Display name
    catalog_url: str  # UI catalog URL (e.g. https://catalog.data.gov.tn/fr/dataset)
    api_url: str  # CKAN Action API v3 base URL
    requires_auth: bool = False
    description: str = ""
    ssl_verify: bool = True  # Set False for portals with SSL certificate issues


# ---------------------------------------------------------------------------
# Built-in defaults
# ---------------------------------------------------------------------------

_DEFAULT_PORTALS: tuple[Portal, ...] = (
    Portal(
        key="data-gov-tn",
        name="Presidency of the Government - data.gov.tn",
        catalog_url="https://catalog.data.gov.tn/fr/dataset",
        api_url="https://catalog.data.gov.tn/api/3",
        description="National open data portal of Tunisia",
        ssl_verify=False,  # SSL certificate issues on this portal
    ),
    Portal(
        key="industrie",
        name="Ministry of Industry, Mines and Energy",
        catalog_url="http://data.industrie.gov.tn/dataset",
        api_url="http://data.industrie.gov.tn/api/3",
        description="Ministry of Industry, Mines and Energy",
    ),
    Portal(
        key="culture",
        name="Ministry of Cultural Affairs",
        catalog_url="http://www.openculture.gov.tn/dataset",
        api_url="http://www.openculture.gov.tn/api/3",
        description="Ministry of Cultural Affairs",
    ),
    Portal(
        key="transport",
        name="Ministry of Transport",
        catalog_url="https://data.transport.tn/dataset",
        api_url="https://data.transport.tn/api/3",
        description="Ministry of Transport",
    ),
    Portal(
        key="agridata",
        name="Ministry of Agriculture, Water Resources and Fisheries",
        catalog_url="https://catalog.agridata.tn/fr/dataset",
        api_url="https://catalog.agridata.tn/api/3",
        description="Ministry of Agriculture, Water Resources and Fisheries",
    ),
)

_DEFAULT_PORTAL_KEY = "agridata"


# ---------------------------------------------------------------------------
# Dynamic registry
# ---------------------------------------------------------------------------


def _discover_env_portals() -> list[Portal]:
    """Scan environment for PORTAL_<KEY>_API_URL variables."""
    discovered: list[Portal] = []
    for env_key, api_url in os.environ.items():
        if not env_key.startswith("PORTAL_") or not env_key.endswith("_API_URL"):
            continue
        key = env_key[len("PORTAL_") : -len("_API_URL")].lower().replace("_", "-")
        if not key or not api_url:
            continue

        # Read optional overrides
        prefix = f"PORTAL_{key.upper().replace('-', '_')}_"
        name = os.environ.get(f"{prefix}NAME", key)
        catalog_url = os.environ.get(f"{prefix}CATALOG_URL", "")
        description = os.environ.get(f"{prefix}DESCRIPTION", "")
        requires_auth = os.environ.get(f"{prefix}REQUIRES_AUTH", "false").lower() == "true"

        # Derive catalog_url from api_url if not provided
        if not catalog_url:
            base = api_url.rstrip("/")
            if base.endswith("/api/3"):
                catalog_url = base[: -len("/api/3")]
            else:
                catalog_url = base

        ssl_verify = os.environ.get(f"{prefix}SSL_VERIFY", "true").lower() != "false"
        discovered.append(
            Portal(
                key=key,
                name=name,
                catalog_url=catalog_url,
                api_url=api_url,
                requires_auth=requires_auth,
                description=description,
                ssl_verify=ssl_verify,
            )
        )
        logger.debug("Discovered portal from env: %s -> %s", key, api_url)

    return discovered


# Module-level mutable state (rebuilt by refresh_portals)
_PORTALS: tuple[Portal, ...] = ()
_PORTALS_BY_KEY: dict[str, Portal] = {}
_PORTALS_BY_API_URL: dict[str, Portal] = {}


def refresh_portals() -> None:
    """Rebuild the portal registry from defaults + environment."""
    global _PORTALS, _PORTALS_BY_KEY, _PORTALS_BY_API_URL

    env_portals = _discover_env_portals()

    # Merge: defaults first, then env portals (env can override by key)
    merged: dict[str, Portal] = {p.key: p for p in _DEFAULT_PORTALS}
    for p in env_portals:
        merged[p.key] = p  # env overrides defaults

    _PORTALS = tuple(merged.values())
    _PORTALS_BY_KEY = {p.key: p for p in _PORTALS}
    _PORTALS_BY_API_URL = {p.api_url.rstrip("/"): p for p in _PORTALS}

    logger.info("Portal registry refreshed: %d portals", len(_PORTALS))


# Build registry on first import
refresh_portals()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_portal(key: str | None = None) -> Portal:
    """Get portal by key, or default."""
    if key is None:
        key = _DEFAULT_PORTAL_KEY
    portal = _PORTALS_BY_KEY.get(key)
    if portal is None:
        raise ValueError(
            f"Unknown portal: {key}. Available: {sorted(_PORTALS_BY_KEY.keys())}"
        )
    return portal


def get_portal_by_api_url(api_url: str) -> Portal | None:
    """Find portal by its API base URL."""
    return _PORTALS_BY_API_URL.get(api_url.rstrip("/"))


def list_portals() -> list[dict[str, Any]]:
    """List all portals as dicts for MCP resources."""
    return [
        {
            "key": p.key,
            "name": p.name,
            "catalog_url": p.catalog_url,
            "api_url": p.api_url,
            "requires_auth": p.requires_auth,
            "description": p.description,
            "ssl_verify": p.ssl_verify,
        }
        for p in _PORTALS
    ]


def get_default_portal_key() -> str:
    """Return the configured default portal key."""
    return _DEFAULT_PORTAL_KEY
