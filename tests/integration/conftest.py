"""Shared fixtures for integration and E2E tests."""

import httpx
import pytest
from fastmcp import Client


@pytest.fixture
async def http_client():
    """Provide an HTTP client for testing the MCP server."""
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=30.0) as client:
        yield client


@pytest.fixture
async def mcp_http_client():
    """Provide a FastMCP client connected to the HTTP server."""
    async with Client("http://127.0.0.1:8000/mcp") as client:
        yield client
