import httpx

from datagouv_mcp_tn.config import Settings, get_settings


class UDataError(RuntimeError):
    pass


class UDataClient:
    def __init__(self, settings: Settings) -> None:
        headers = {"Accept": "application/json"}
        if settings.data_gouv_tn_api_key:
            headers["X-API-KEY"] = settings.data_gouv_tn_api_key
        self._http = httpx.AsyncClient(
            base_url=settings.data_gouv_tn_api_url.rstrip("/"),
            headers=headers,
            timeout=settings.request_timeout,
        )

    async def get(self, path: str, params: dict | None = None) -> dict | list:
        response = await self._http.get(path, params=params)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise UDataError(
                f"uData API returned {response.status_code}: {response.text[:200]}"
            ) from exc
        try:
            return response.json()
        except ValueError as exc:
            raise UDataError("uData API returned invalid JSON") from exc

    async def aclose(self) -> None:
        await self._http.aclose()


_client: UDataClient | None = None


def get_client() -> UDataClient:
    global _client
    if _client is None:
        _client = UDataClient(get_settings())
    return _client
