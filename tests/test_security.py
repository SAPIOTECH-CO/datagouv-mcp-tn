"""Tests for rate limiting, CORS, host/origin protection, and log sanitization."""

import json
import logging
from unittest.mock import AsyncMock, patch

import pytest

from datagouv_mcp_tn.helpers.config import Settings
from datagouv_mcp_tn.helpers.cors import build_cors_middleware, get_host_origin_protection_config
from datagouv_mcp_tn.helpers.logging_config import _SecretsAndPIIFilter, _sanitize_text, configure_logging
from datagouv_mcp_tn.helpers.rate_limit import build_rate_limit_middleware


class TestRateLimiting:
    def test_build_rate_limit_middleware_enabled(self):
        test_settings = Settings(
            rate_limit_enabled=True,
            rate_limit_max_requests=100,
            rate_limit_window_minutes=1,
        )
        with patch("datagouv_mcp_tn.helpers.rate_limit.get_settings", return_value=test_settings):
            mw = build_rate_limit_middleware()
            assert mw is not None
            assert mw.max_requests == 100
            assert mw.window_seconds == 60

    def test_build_rate_limit_middleware_disabled(self):
        test_settings = Settings(rate_limit_enabled=False)
        with patch("datagouv_mcp_tn.helpers.rate_limit.get_settings", return_value=test_settings):
            mw = build_rate_limit_middleware()
            assert mw is None

    def test_build_rate_limit_middleware_zero_requests(self):
        test_settings = Settings(
            rate_limit_enabled=True,
            rate_limit_max_requests=0,
        )
        with patch("datagouv_mcp_tn.helpers.rate_limit.get_settings", return_value=test_settings):
            mw = build_rate_limit_middleware()
            assert mw is None


class TestCORS:
    def test_build_cors_middleware_enabled(self):
        test_settings = Settings(
            cors_enabled=True,
            cors_allowed_origins=["*"],
            cors_allowed_methods=["GET", "POST"],
            cors_allowed_headers=["Content-Type"],
            cors_expose_headers=["mcp-session-id"],
            cors_allow_credentials=False,
            cors_max_age=600,
        )
        with patch("datagouv_mcp_tn.helpers.cors.get_settings", return_value=test_settings):
            middlewares = build_cors_middleware()
            assert middlewares is not None
            assert len(middlewares) == 1

    def test_build_cors_middleware_disabled(self):
        test_settings = Settings(cors_enabled=False)
        with patch("datagouv_mcp_tn.helpers.cors.get_settings", return_value=test_settings):
            middlewares = build_cors_middleware()
            assert middlewares is None


class TestHostOriginProtection:
    def test_get_config_defaults(self):
        test_settings = Settings(
            host_origin_protection=True,
            allowed_hosts=None,
            allowed_origins=None,
        )
        with patch("datagouv_mcp_tn.helpers.cors.get_settings", return_value=test_settings):
            config = get_host_origin_protection_config()
            assert config["host_origin_protection"] is True
            assert config["allowed_hosts"] is None
            assert config["allowed_origins"] is None

    def test_get_config_with_lists(self):
        # Create a Settings instance with custom values for testing
        test_settings = Settings(
            host_origin_protection=True,
            allowed_hosts=["mcp.example.com"],
            allowed_origins=["https://app.example.com"],
        )
        with patch("datagouv_mcp_tn.helpers.cors.get_settings", return_value=test_settings):
            config = get_host_origin_protection_config()
            assert config["allowed_hosts"] == ["mcp.example.com"]
            assert config["allowed_origins"] == ["https://app.example.com"]


class TestLogSanitization:
    def test_sanitize_text_bearer_token(self):
        text = 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9'
        result = _sanitize_text(text)
        assert "Bearer ***" in result
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in result

    def test_sanitize_text_api_key(self):
        text = 'api_key="sk_live_abcdefghijklmnopqrstuvwxyz123456"'
        result = _sanitize_text(text)
        assert "***" in result
        assert "sk_live_abcdefghijklmnopqrstuvwxyz123456" not in result

    def test_sanitize_text_password(self):
        text = 'password="MySecretPassword123!"'
        result = _sanitize_text(text)
        assert "***" in result
        assert "MySecretPassword123!" not in result

    def test_sanitize_text_email(self):
        text = "Contact: user@example.com for info"
        result = _sanitize_text(text)
        assert "[email]" in result
        assert "user@example.com" not in result

    def test_sanitize_text_ipv4(self):
        text = "Client IP: 192.168.1.100 connected"
        result = _sanitize_text(text)
        assert "[ip]" in result
        assert "192.168.1.100" not in result

    def test_sanitize_text_user_id(self):
        text = "GET /users/12345/profile"
        result = _sanitize_text(text)
        assert "[user_id]" in result
        assert "12345" not in result

    def test_sanitize_text_multiple(self):
        text = 'User user@test.com from 10.0.0.1 used api_key="abc123def456ghi789"'
        result = _sanitize_text(text)
        assert "[email]" in result
        assert "[ip]" in result
        assert "***" in result

    def test_sanitize_text_preserves_normal_text(self):
        text = "Normal log message with numbers 123 and punctuation!"
        result = _sanitize_text(text)
        assert result == text

    def test_secrets_pii_filter_enabled(self):
        filter_obj = _SecretsAndPIIFilter(enabled=True)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=1,
            msg='User token="secret123"',
            args=(),
            exc_info=None,
        )
        filter_obj.filter(record)
        assert "secret123" not in record.msg
        assert "***" in record.msg

    def test_secrets_pii_filter_disabled(self):
        filter_obj = _SecretsAndPIIFilter(enabled=False)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=1,
            msg='User token="secret123"',
            args=(),
            exc_info=None,
        )
        filter_obj.filter(record)
        assert record.msg == 'User token="secret123"'

    def test_configure_logging_returns_uvicorn_config(self):
        config = configure_logging("INFO")
        assert isinstance(config, dict)
        assert "version" in config
        assert "formatters" in config


class TestSettingsSecurityDefaults:
    def test_security_defaults_are_secure(self):
        """Verify that default settings are production-safe."""
        settings = Settings()
        assert settings.strict_input_validation is True
        assert settings.rate_limit_enabled is True
        assert settings.rate_limit_max_requests == 100
        assert settings.rate_limit_window_minutes == 1
        assert settings.cors_enabled is True
        assert settings.host_origin_protection is True
        assert settings.log_sanitization_enabled is True

    def test_cors_defaults_allow_all_origins(self):
        """CORS defaults to permissive for local development."""
        settings = Settings()
        assert settings.cors_allowed_origins == ["*"]
        assert "Authorization" in settings.cors_allowed_headers
        assert "mcp-protocol-version" in settings.cors_allowed_headers
        assert "mcp-session-id" in settings.cors_allowed_headers
        assert "mcp-session-id" in settings.cors_expose_headers

    def test_host_origin_protection_defaults_auto(self):
        """Host/Origin protection defaults to on but with no explicit lists (auto mode)."""
        settings = Settings()
        assert settings.host_origin_protection is True
        assert settings.allowed_hosts is None
        assert settings.allowed_origins is None