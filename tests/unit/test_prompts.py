"""Tests for dynamic prompt templates."""

import pytest


@pytest.mark.asyncio
async def test_explore_portal_prompt(mcp_client):
    result = await mcp_client.get_prompt("explore_portal", {"portal_key": "agridata"})
    text = result.messages[0].content.text
    assert "portal" in text.lower()
    assert "agridata" in text


@pytest.mark.asyncio
async def test_search_and_analyze_prompt(mcp_client):
    result = await mcp_client.get_prompt(
        "search_and_analyze", {"topic": "population", "portal_key": "agridata"}
    )
    text = result.messages[0].content.text
    assert "population" in text.lower()
    assert "search_datasets" in text


@pytest.mark.asyncio
async def test_discover_portals_prompt(mcp_client):
    result = await mcp_client.get_prompt("discover_portals", {})
    text = result.messages[0].content.text
    assert "portal" in text.lower()
    assert "agridata" in text


@pytest.mark.asyncio
async def test_analyze_resource_prompt(mcp_client):
    result = await mcp_client.get_prompt("analyze_resource", {"resource_hint": "csv"})
    text = result.messages[0].content.text
    assert "resource" in text.lower()


@pytest.mark.asyncio
async def test_workflow_assistant_prompt(mcp_client):
    result = await mcp_client.get_prompt("workflow_assistant", {})
    text = result.messages[0].content.text
    assert "assistant" in text.lower()
    assert "tool" in text.lower()
