"""Encrypted API key storage for RefChecker adapters.

Uses the OS-native credential store via the ``keyring`` library:
  - macOS: Keychain
  - Linux: Secret Service (GNOME Keyring / KDE Wallet) or fallback encrypted file
  - Windows: Windows Credential Manager

Each adapter's API key is stored as a separate keyring entry under
the service name "refchecker". Keys are never written to disk in
plaintext.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from refchecker.core.logging import get_logger

logger = get_logger(__name__)

# Keyring service name — groups all RefChecker keys together
_SERVICE_NAME = "refchecker"

# Supported adapter key names
_ADAPTER_KEY_NAMES = frozenset({
    "s2_api_key",
    "openalex_api_key",
    "aminer_api_key",
})


@dataclass(frozen=True)
class StoredKey:
    """A single stored API key entry.

    Attributes:
        adapter_name: Adapter identifier (e.g. "s2", "aminer").
        key_name: Config field name (e.g. "s2_api_key").
        has_key: Whether a key is currently stored.
    """

    adapter_name: str
    key_name: str
    has_key: bool


def _get_keyring():
    """Lazily import keyring to avoid import errors when not installed.

    Returns:
        The keyring module.

    Raises:
        ImportError: If keyring is not installed.
    """
    import keyring  # noqa: PLC0415
    return keyring


def store_key(key_name: str, api_key: str) -> None:
    """Store an API key in the encrypted key store.

    Args:
        key_name: Key identifier (e.g. "s2_api_key").
        api_key: The API key value to store.

    Raises:
        ValueError: If key_name is not a recognized adapter key.
        ImportError: If keyring is not available.
    """
    if key_name not in _ADAPTER_KEY_NAMES:
        raise ValueError(
            f"Unknown key name '{key_name}'. "
            f"Supported: {sorted(_ADAPTER_KEY_NAMES)}"
        )

    kr = _get_keyring()
    kr.set_password(_SERVICE_NAME, key_name, api_key)
    logger.info("key_stored", key_name=key_name)


def load_key(key_name: str) -> Optional[str]:
    """Load an API key from the encrypted key store.

    Args:
        key_name: Key identifier (e.g. "s2_api_key").

    Returns:
        The API key string, or None if not found.

    Raises:
        ValueError: If key_name is not a recognized adapter key.
        ImportError: If keyring is not available.
    """
    if key_name not in _ADAPTER_KEY_NAMES:
        raise ValueError(
            f"Unknown key name '{key_name}'. "
            f"Supported: {sorted(_ADAPTER_KEY_NAMES)}"
        )

    kr = _get_keyring()
    value = kr.get_password(_SERVICE_NAME, key_name)
    if value is not None:
        logger.debug("key_loaded", key_name=key_name)
    return value


def delete_key(key_name: str) -> bool:
    """Delete an API key from the encrypted key store.

    Args:
        key_name: Key identifier (e.g. "s2_api_key").

    Returns:
        True if the key was deleted, False if it didn't exist.

    Raises:
        ValueError: If key_name is not a recognized adapter key.
        ImportError: If keyring is not available.
    """
    if key_name not in _ADAPTER_KEY_NAMES:
        raise ValueError(
            f"Unknown key name '{key_name}'. "
            f"Supported: {sorted(_ADAPTER_KEY_NAMES)}"
        )

    kr = _get_keyring()
    if kr.get_password(_SERVICE_NAME, key_name) is None:
        return False

    kr.delete_password(_SERVICE_NAME, key_name)
    logger.info("key_deleted", key_name=key_name)
    return True


def list_keys() -> list[StoredKey]:
    """List all known adapter keys and their storage status.

    Returns:
        List of StoredKey entries for each known adapter key.
    """
    try:
        kr = _get_keyring()
    except ImportError:
        # If keyring unavailable, report all as no-key
        return [
            StoredKey(
                adapter_name=_key_to_adapter(kn),
                key_name=kn,
                has_key=False,
            )
            for kn in sorted(_ADAPTER_KEY_NAMES)
        ]

    results: list[StoredKey] = []
    for key_name in sorted(_ADAPTER_KEY_NAMES):
        value = kr.get_password(_SERVICE_NAME, key_name)
        results.append(StoredKey(
            adapter_name=_key_to_adapter(key_name),
            key_name=key_name,
            has_key=value is not None,
        ))

    return results


def _key_to_adapter(key_name: str) -> str:
    """Convert a key_name to its adapter short name.

    Args:
        key_name: Config field name (e.g. "s2_api_key").

    Returns:
        Adapter name (e.g. "s2").
    """
    # Strip trailing "_api_key" or "_key"
    for suffix in ("_api_key", "_key"):
        if key_name.endswith(suffix):
            return key_name[: -len(suffix)]
    return key_name


def resolve_key(key_name: str, env_value: Optional[str] = None) -> Optional[str]:
    """Resolve an API key from env var (priority) or encrypted store (fallback).

    Environment variables take precedence so that CI/CD pipelines and
    .env files continue to work without keyring.

    Args:
        key_name: Key identifier (e.g. "s2_api_key").
        env_value: Value from environment variable (already loaded).

    Returns:
        The resolved API key, or None if not found.
    """
    if env_value:
        logger.debug("key_from_env", key_name=key_name)
        return env_value

    try:
        stored = load_key(key_name)
        if stored:
            logger.debug("key_from_store", key_name=key_name)
        return stored
    except ImportError:
        logger.warning("keyring_unavailable", key_name=key_name)
        return None
