"""Shared fixtures for integration and E2E tests."""

import asyncio
import sys
from pathlib import Path

import httpx
import pytest
from fastmcp import Client

# Ensure root-level test helpers are importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


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
