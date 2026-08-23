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

    # --- Security settings ---
    # Strict input validation for tool arguments (FastMCP native)
    strict_input_validation: bool = True

    # Rate limiting (SlidingWindowRateLimitingMiddleware)
    rate_limit_enabled: bool = True
    rate_limit_max_requests: int = 100
    rate_limit_window_minutes: int = 1

    # CORS configuration
    cors_enabled: bool = True
    cors_allowed_origins: list[str] = ["*"]
    cors_allowed_methods: list[str] = ["GET", "POST", "DELETE", "OPTIONS"]
    cors_allowed_headers: list[str] = [
        "mcp-protocol-version",
        "mcp-session-id",
        "Authorization",
        "Content-Type",
    ]
    cors_expose_headers: list[str] = ["mcp-session-id"]
    cors_allow_credentials: bool = False
    cors_max_age: int = 600

    # Host/Origin protection (DNS rebinding guard)
    host_origin_protection: bool = True
    allowed_hosts: list[str] | None = None
    allowed_origins: list[str] | None = None

    # Log sanitization (secrets + PII masking)
    log_sanitization_enabled: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
