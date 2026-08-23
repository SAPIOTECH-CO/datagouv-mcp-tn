"""Context providers for FastMCP dependency injection.

Use ``Depends`` to inject server-level defaults (portal, language) into
tools and prompts without requiring the caller to pass them explicitly.
"""

from __future__ import annotations

from fastmcp.dependencies import Depends

from datagouv_mcp_tn.helpers.config import get_settings
from datagouv_mcp_tn.helpers.i18n import Language, resolve_language
from datagouv_mcp_tn.portals import get_default_portal_key


def get_default_portal() -> str:
    """Return the configured default portal key.

    Use as a FastMCP dependency::

        @mcp.tool
        async def my_tool(..., portal: str = Depends(get_default_portal)):
            ...
    """
    return get_default_portal_key()


def get_default_language() -> Language:
    """Return the configured default language.

    Use as a FastMCP dependency::

        @mcp.tool
        async def my_tool(..., language: Language = Depends(get_default_language)):
            ...
    """
    settings = get_settings()
    return resolve_language(settings.default_language)


def get_portal_or_default(portal: str | None = None) -> str:
    """Resolve portal parameter: use provided key or fall back to default.

    This is a convenience wrapper that makes the fallback explicit in the
    dependency graph::

        @mcp.tool
        async def my_tool(..., portal: str = Depends(get_portal_or_default)):
            ...
    """
    if portal is not None:
        return portal
    return get_default_portal()


__all__ = [
    "Depends",
    "get_default_portal",
    "get_default_language",
    "get_portal_or_default",
]
