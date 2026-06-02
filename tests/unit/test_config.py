"""Unit tests for refchecker.config module."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from refchecker.config import (
    AdapterKeys,
    RefCheckerConfig,
    load_config,
)


class TestAdapterKeys:
    """Tests for AdapterKeys settings model."""

    def test_defaults(self) -> None:
        """AdapterKeys has sensible defaults."""
        keys = AdapterKeys()
        assert keys.crossref_mailto == "refchecker@example.com"
        assert keys.s2_api_key is None
        assert keys.openalex_api_key is None
        assert keys.aminer_api_key is None
        assert keys.http_proxy is None
        assert keys.https_proxy is None
        assert keys.request_timeout == 30.0
        assert keys.max_concurrent == 3
        assert keys.max_retries == 5

    def test_env_prefix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """AdapterKeys reads from REFCHECKER_ env prefix."""
        monkeypatch.setenv("REFCHECKER_S2_API_KEY", "test-s2-key")
        monkeypatch.setenv("REFCHECKER_HTTP_PROXY", "http://proxy:8080")
        keys = AdapterKeys()
        assert keys.s2_api_key == "test-s2-key"
        assert keys.http_proxy == "http://proxy:8080"


class TestRefCheckerConfig:
    """Tests for RefCheckerConfig settings model."""

    def test_defaults(self) -> None:
        """Config has expected default values."""
        config = RefCheckerConfig()
        assert "crossref" in config.enabled_adapters
        assert "s2" in config.enabled_adapters
        assert "aminer" in config.enabled_adapters
        assert config.default_export_format == "csv"
        assert config.verbose is False

    def test_default_enabled_adapters(self) -> None:
        """Default adapters include all 7 core adapters."""
        config = RefCheckerConfig()
        expected = {"crossref", "s2", "openalex", "aminer", "baidu", "arxiv", "scholar"}
        assert set(config.enabled_adapters) == expected

    def test_is_adapter_enabled_true(self) -> None:
        """Default adapters are enabled."""
        config = RefCheckerConfig()
        assert config.is_adapter_enabled("crossref") is True
        assert config.is_adapter_enabled("s2") is True

    def test_is_adapter_enabled_false(self) -> None:
        """Non-default adapters are not enabled."""
        config = RefCheckerConfig(enabled_adapters=["crossref"])
        assert config.is_adapter_enabled("s2") is False

    @patch("refchecker.core.key_store.resolve_key", return_value=None)
    def test_get_adapter_config_crossref(self, mock_resolve: object) -> None:
        """Crossref config includes mailto."""
        config = RefCheckerConfig()
        result = config.get_adapter_config("crossref")
        assert "mailto" in result

    @patch("refchecker.core.key_store.resolve_key", return_value=None)
    def test_get_adapter_config_s2(self, mock_resolve: object) -> None:
        """S2 config resolves API key."""
        config = RefCheckerConfig()
        result = config.get_adapter_config("s2")
        assert "api_key" in result

    @patch("refchecker.core.key_store.resolve_key", return_value=None)
    def test_get_adapter_config_baidu_empty(self, mock_resolve: object) -> None:
        """Baidu config has no special keys."""
        config = RefCheckerConfig()
        result = config.get_adapter_config("baidu")
        assert result == {}

    @patch("refchecker.core.key_store.resolve_key", return_value=None)
    def test_get_adapter_config_unknown_empty(self, mock_resolve: object) -> None:
        """Unknown adapter returns empty dict."""
        config = RefCheckerConfig()
        result = config.get_adapter_config("nonexistent")
        assert result == {}

    def test_get_proxy_url_https_preferred(self) -> None:
        """HTTPS proxy is preferred over HTTP."""
        config = RefCheckerConfig(
            adapters=AdapterKeys(http_proxy="http://p:80", https_proxy="https://p:443"),
        )
        assert config.get_proxy_url() == "https://p:443"

    def test_get_proxy_url_http_fallback(self) -> None:
        """HTTP proxy returned when HTTPS not set."""
        config = RefCheckerConfig(
            adapters=AdapterKeys(http_proxy="http://p:80"),
        )
        assert config.get_proxy_url() == "http://p:80"

    def test_get_proxy_url_none(self) -> None:
        """No proxy returns None."""
        config = RefCheckerConfig()
        assert config.get_proxy_url() is None


class TestLoadConfig:
    """Tests for load_config function."""

    def test_default_config(self) -> None:
        """load_config with no args returns default config."""
        config = load_config()
        assert isinstance(config, RefCheckerConfig)
        assert "crossref" in config.enabled_adapters

    def test_load_nonexistent_path(self, tmp_path: Path) -> None:
        """load_config with nonexistent path returns default config."""
        config = load_config(tmp_path / "nonexistent.toml")
        assert isinstance(config, RefCheckerConfig)

    def test_load_from_toml(self, tmp_path: Path) -> None:
        """load_config reads from TOML file."""
        toml_file = tmp_path / "config.toml"
        toml_file.write_text(
            '[refchecker]\nenabled_adapters = ["crossref", "s2"]\ndefault_export_format = "xlsx"\n',
        )
        config = load_config(toml_file)
        assert config.enabled_adapters == ["crossref", "s2"]
        assert config.default_export_format == "xlsx"
