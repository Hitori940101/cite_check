"""Configuration and API key management for RefChecker.

Uses Pydantic Settings for type-safe configuration with
environment variable and .env file support.

API keys are resolved in priority order:
1. Environment variables (REFCHECKER_<FIELD_NAME>) — for CI/CD
2. Encrypted key store (OS keyring via keyring lib) — for interactive use
3. None — free tier is used

The tool works out-of-box with free tiers. Keys unlock higher
rate limits or additional features.
"""

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from refchecker.core.logging import get_logger

logger = get_logger(__name__)


class AdapterKeys(BaseSettings):
    """Per-adapter API key configuration.

    All keys are optional. The tool works with free tiers.
    Keys unlock higher rate limits or additional features.

    Environment variables: REFCHECKER_<FIELD_NAME>
    """

    model_config = SettingsConfigDict(
        env_prefix="REFCHECKER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Adapter API keys (from env vars; encrypted store is checked at resolution)
    crossref_mailto: str = "refchecker@example.com"
    s2_api_key: Optional[str] = None
    openalex_api_key: Optional[str] = None
    aminer_api_key: Optional[str] = None

    # Proxy settings
    http_proxy: Optional[str] = None
    https_proxy: Optional[str] = None

    # General settings
    request_timeout: float = 30.0
    max_concurrent: int = 3
    max_retries: int = 5


class RefCheckerConfig(BaseSettings):
    """Top-level application configuration.

    Combines adapter keys with general application settings.
    """

    model_config = SettingsConfigDict(
        env_prefix="REFCHECKER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Adapter configuration
    adapters: AdapterKeys = Field(default_factory=AdapterKeys)

    # Which adapters to enable (comma-separated or list)
    enabled_adapters: list[str] = Field(
        default=["crossref", "s2", "openalex", "aminer"],
        description="List of adapter names to use for verification.",
    )

    # Output settings
    default_export_format: str = "csv"
    verbose: bool = False

    def get_adapter_config(self, adapter_name: str) -> dict:
        """Get configuration dict for a specific adapter.

        Resolves API keys with priority: env var → encrypted store → None.

        Args:
            adapter_name: Adapter identifier (e.g. "crossref", "s2").

        Returns:
            Dict with adapter-specific configuration.
        """
        from refchecker.core.key_store import resolve_key

        key_map = {
            "crossref": {"mailto": self.adapters.crossref_mailto},
            "s2": {"api_key": resolve_key("s2_api_key", self.adapters.s2_api_key)},
            "openalex": {"api_key": resolve_key("openalex_api_key", self.adapters.openalex_api_key)},
            "aminer": {"api_key": resolve_key("aminer_api_key", self.adapters.aminer_api_key)},
            "baidu": {},
            "cnki": {},
        }
        return key_map.get(adapter_name, {})

    def is_adapter_enabled(self, adapter_name: str) -> bool:
        """Check if an adapter is in the enabled list.

        Args:
            adapter_name: Adapter name to check.

        Returns:
            True if enabled.
        """
        return adapter_name in self.enabled_adapters

    def get_proxy_url(self) -> Optional[str]:
        """Get the proxy URL for HTTP requests.

        Returns:
            Proxy URL or None.
        """
        return self.adapters.https_proxy or self.adapters.http_proxy


def load_config(config_path: Optional[Path] = None) -> RefCheckerConfig:
    """Load configuration from environment, .env file, or explicit path.

    Args:
        config_path: Optional explicit path to a config file.

    Returns:
        Loaded RefCheckerConfig.
    """
    if config_path is not None and config_path.exists():
        import tomllib

        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        return RefCheckerConfig(**data.get("refchecker", {}))

    return RefCheckerConfig()
