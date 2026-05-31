"""Unit tests for the encrypted API key store (key_store.py).

Uses a mock keyring backend to test without touching the real OS keychain.
"""

from unittest.mock import MagicMock, patch

import pytest

from refchecker.core.key_store import (
    StoredKey,
    _key_to_adapter,
    delete_key,
    list_keys,
    load_key,
    resolve_key,
    store_key,
)


# --- In-memory mock keyring ---


class _MockKeyring:
    """A simple in-memory keyring for testing."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def set_password(self, service: str, key: str, password: str) -> None:
        assert service == "refchecker"
        self._store[key] = password

    def get_password(self, service: str, key: str) -> str | None:
        assert service == "refchecker"
        return self._store.get(key)

    def delete_password(self, service: str, key: str) -> None:
        assert service == "refchecker"
        if key not in self._store:
            raise KeyError(key)
        del self._store[key]


@pytest.fixture
def mock_keyring():
    """Patch keyring with an in-memory mock."""
    mock = _MockKeyring()
    with patch("refchecker.core.key_store._get_keyring", return_value=mock):
        yield mock


# --- store_key tests ---


class TestStoreKey:
    """Tests for storing API keys."""

    def test_store_s2_key(self, mock_keyring: _MockKeyring) -> None:
        """Storing an S2 key succeeds."""
        store_key("s2_api_key", "test-s2-key-123")
        assert mock_keyring.get_password("refchecker", "s2_api_key") == "test-s2-key-123"

    def test_store_openalex_key(self, mock_keyring: _MockKeyring) -> None:
        """Storing an OpenAlex key succeeds."""
        store_key("openalex_api_key", "test-openalex-key")
        assert mock_keyring.get_password("refchecker", "openalex_api_key") == "test-openalex-key"

    def test_store_unknown_key_raises(self, mock_keyring: _MockKeyring) -> None:
        """Storing an unknown key name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown key name"):
            store_key("nonexistent_key", "value")

    def test_overwrite_existing_key(self, mock_keyring: _MockKeyring) -> None:
        """Overwriting an existing key succeeds."""
        store_key("s2_api_key", "old-key")
        store_key("s2_api_key", "new-key")
        assert load_key("s2_api_key") == "new-key"


# --- load_key tests ---


class TestLoadKey:
    """Tests for loading API keys."""

    def test_load_existing_key(self, mock_keyring: _MockKeyring) -> None:
        """Loading an existing key returns its value."""
        mock_keyring.set_password("refchecker", "s2_api_key", "my-key")
        result = load_key("s2_api_key")
        assert result == "my-key"

    def test_load_missing_key_returns_none(self, mock_keyring: _MockKeyring) -> None:
        """Loading a missing key returns None."""
        result = load_key("s2_api_key")
        assert result is None

    def test_load_unknown_key_raises(self, mock_keyring: _MockKeyring) -> None:
        """Loading an unknown key name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown key name"):
            load_key("garbage_key")


# --- delete_key tests ---


class TestDeleteKey:
    """Tests for deleting API keys."""

    def test_delete_existing_key(self, mock_keyring: _MockKeyring) -> None:
        """Deleting an existing key returns True."""
        store_key("s2_api_key", "to-delete")
        result = delete_key("s2_api_key")
        assert result is True
        assert load_key("s2_api_key") is None

    def test_delete_missing_key_returns_false(self, mock_keyring: _MockKeyring) -> None:
        """Deleting a missing key returns False."""
        result = delete_key("s2_api_key")
        assert result is False

    def test_delete_unknown_key_raises(self, mock_keyring: _MockKeyring) -> None:
        """Deleting an unknown key name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown key name"):
            delete_key("invalid_key")


# --- list_keys tests ---


class TestListKeys:
    """Tests for listing key status."""

    def test_list_all_none(self, mock_keyring: _MockKeyring) -> None:
        """Listing with no keys shows all as has_key=False."""
        keys = list_keys()
        assert len(keys) == 3  # s2, openalex, aminer
        assert all(not k.has_key for k in keys)

    def test_list_with_stored_key(self, mock_keyring: _MockKeyring) -> None:
        """Listing shows stored key as has_key=True."""
        store_key("s2_api_key", "test")
        keys = list_keys()
        s2_key = [k for k in keys if k.adapter_name == "s2"][0]
        assert s2_key.has_key is True

    def test_list_sorted_by_name(self, mock_keyring: _MockKeyring) -> None:
        """Keys are sorted alphabetically by key_name."""
        keys = list_keys()
        names = [k.key_name for k in keys]
        assert names == sorted(names)


# --- resolve_key tests ---


class TestResolveKey:
    """Tests for key resolution priority (env → store)."""

    def test_env_value_takes_priority(self, mock_keyring: _MockKeyring) -> None:
        """Environment variable value takes priority over stored key."""
        store_key("s2_api_key", "stored-key")
        result = resolve_key("s2_api_key", env_value="env-key")
        assert result == "env-key"

    def test_stored_key_as_fallback(self, mock_keyring: _MockKeyring) -> None:
        """Stored key is used when no env value is provided."""
        store_key("s2_api_key", "stored-key")
        result = resolve_key("s2_api_key", env_value=None)
        assert result == "stored-key"

    def test_returns_none_when_no_key(self, mock_keyring: _MockKeyring) -> None:
        """Returns None when neither env nor store has a key."""
        result = resolve_key("s2_api_key", env_value=None)
        assert result is None

    def test_empty_env_string_uses_store(self, mock_keyring: _MockKeyring) -> None:
        """Empty string env value falls back to store."""
        store_key("s2_api_key", "stored-key")
        result = resolve_key("s2_api_key", env_value="")
        assert result == "stored-key"


# --- _key_to_adapter tests ---


class TestKeyToAdapter:
    """Tests for key_name → adapter_name conversion."""

    def test_s2_api_key(self) -> None:
        assert _key_to_adapter("s2_api_key") == "s2"

    def test_openalex_api_key(self) -> None:
        assert _key_to_adapter("openalex_api_key") == "openalex"

    def test_aminer_api_key(self) -> None:
        assert _key_to_adapter("aminer_api_key") == "aminer"


# --- StoredKey dataclass tests ---


class TestStoredKey:
    """Tests for StoredKey dataclass."""

    def test_frozen(self) -> None:
        """StoredKey is immutable."""
        key = StoredKey(adapter_name="s2", key_name="s2_api_key", has_key=True)
        with pytest.raises(AttributeError):
            key.has_key = False  # type: ignore[misc]

    def test_equality(self) -> None:
        """StoredKeys with same values are equal."""
        k1 = StoredKey(adapter_name="s2", key_name="s2_api_key", has_key=True)
        k2 = StoredKey(adapter_name="s2", key_name="s2_api_key", has_key=True)
        assert k1 == k2
