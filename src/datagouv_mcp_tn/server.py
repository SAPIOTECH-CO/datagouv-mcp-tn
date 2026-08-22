from fastmcp import FastMCP

from datagouv_mcp_tn.client import get_client

mcp = FastMCP("DataGouv TN")


@mcp.tool
async def search_datasets(
    query: str,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """Search datasets on the Tunisian open data portal (data.gouv.tn).

    Args:
        query: Free-text search terms (French or Arabic work best).
        page: 1-based result page number.
        page_size: Number of results per page (max 100).
    """
    data = await get_client().get(
        "/datasets/",
        params={"q": query, "page": page, "page_size": min(page_size, 100)},
    )
    return _summarize_page(data)


@mcp.tool
async def get_dataset(dataset_id: str) -> dict:
    """Fetch full metadata for a single dataset by its ID or slug."""
    return await get_client().get(f"/datasets/{dataset_id}/")


@mcp.tool
async def suggest_datasets(partial_query: str, size: int = 10) -> list[str]:
    """Autocomplete dataset titles from a partial query.

    Returns a flat list of matching dataset titles.
    """
    data = await get_client().get(
        "/datasets/suggest/",
        params={"q": partial_query, "size": min(size, 50)},
    )
    if isinstance(data, list):
        return [item.get("title", "") for item in data if isinstance(item, dict)]
    return []


@mcp.tool
async def search_organizations(
    query: str,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """Search publishing organizations on the Tunisian open data portal.

    Args:
        query: Free-text search terms.
        page: 1-based result page number.
        page_size: Number of results per page (max 100).
    """
    data = await get_client().get(
        "/organizations/",
        params={"q": query, "page": page, "page_size": min(page_size, 100)},
    )
    return _summarize_page(data)


@mcp.tool
async def get_organization(organization_id: str) -> dict:
    """Fetch full metadata for an organization by its ID or slug."""
    return await get_client().get(f"/organizations/{organization_id}/")


def _summarize_page(data: dict) -> dict:
    results = []
    for item in data.get("data", []):
        results.append(
            {
                "id": item.get("id"),
                "slug": item.get("slug"),
                "title": item.get("title"),
                "description": (item.get("description") or "")[:300],
                "url": item.get("page") or item.get("url"),
            }
        )
    return {
        "total": data.get("total", len(results)),
        "page": data.get("page"),
        "page_size": data.get("page_size"),
        "results": results,
    }
