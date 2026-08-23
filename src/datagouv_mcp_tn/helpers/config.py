from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    data_gouv_tn_api_url: str = "https://data.gouv.tn/api/1"
    data_gouv_tn_api_key: str | None = None
    request_timeout: float = 30.0
    request_max_retries: int = 2
    retry_backoff_seconds: float = 0.5
    download_timeout: float = 120.0
    max_download_size_mb: int = 50
    default_language: str = "fr"
    log_level: str = "INFO"
    # Opt-in: registers the Generative UI provider (generate_prefab_ui),
    # which executes LLM-written Prefab code in a Pyodide sandbox and needs
    # Deno on the host for server-side validation. Off by default.
    enable_generative_ui: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
