from functools import lru_cache
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict

from datagouv_mcp_tn.portals import Portal, get_default_portal_key, get_portal


class PortalSettings(BaseSettings):
    """Per-portal settings (can be overridden via env vars)."""
    api_url: str
    api_key: str | None = None
    request_timeout: float = 30.0
    request_max_retries: int = 2
    retry_backoff_seconds: float = 0.5
    download_timeout: float = 120.0
    max_download_size_mb: int = 50
    ssl_verify: bool = True

    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore",
    )


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Default portal key
    default_portal: str = get_default_portal_key()

    # Global defaults (used as fallback for portals without explicit config)
    request_timeout: float = 30.0
    request_max_retries: int = 2
    retry_backoff_seconds: float = 0.5
    download_timeout: float = 120.0
    max_download_size_mb: int = 50
    default_language: str = "fr"
    log_level: str = "INFO"
    enable_generative_ui: bool = False

    # --- Security settings ---
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

    # Per-portal overrides (loaded from env vars like PORTAL_DATA_GOV_TN_API_KEY)
    _portal_overrides: dict[str, PortalSettings] = {}

    def get_portal_settings(self, portal: Portal) -> PortalSettings:
        """Get settings for a specific portal, merging global defaults with overrides."""
        # Check for per-portal env vars (e.g., PORTAL_DATA_GOV_TN_API_KEY)
        import os
        prefix = f"PORTAL_{portal.key.upper().replace('-', '_')}_"
        overrides: dict[str, Any] = {}
        for key in ("api_url", "api_key", "request_timeout", "request_max_retries",
                    "retry_backoff_seconds", "download_timeout", "max_download_size_mb",
                    "ssl_verify"):
            env_key = f"{prefix}{key.upper()}"
            if env_key in os.environ:
                raw_val = os.environ[env_key]
                # Type conversion
                if key in ("request_timeout", "retry_backoff_seconds", "download_timeout"):
                    converted: Any = float(raw_val)
                elif key in ("request_max_retries", "max_download_size_mb"):
                    converted = int(raw_val)
                elif key == "ssl_verify":
                    converted = raw_val.lower() != "false"
                else:
                    converted = raw_val
                overrides[key] = converted

        # Use portal's default API URL if not overridden
        if "api_url" not in overrides:
            overrides["api_url"] = portal.api_url

        # Cast overrides to proper types for PortalSettings
        return PortalSettings(
            api_url=overrides.get("api_url", portal.api_url),
            api_key=overrides.get("api_key"),
            request_timeout=float(overrides.get("request_timeout", self.request_timeout)),
            request_max_retries=int(overrides.get("request_max_retries", self.request_max_retries)),
            retry_backoff_seconds=float(overrides.get(
                "retry_backoff_seconds", self.retry_backoff_seconds
            )),
            download_timeout=float(overrides.get("download_timeout", self.download_timeout)),
            max_download_size_mb=int(
                overrides.get("max_download_size_mb", self.max_download_size_mb)
            ),
            ssl_verify=bool(overrides.get("ssl_verify", portal.ssl_verify)),
        )

    def get_default_portal(self) -> Portal:
        """Get the default portal."""
        return get_portal(self.default_portal)


@lru_cache
def get_settings() -> Settings:
    return Settings()
