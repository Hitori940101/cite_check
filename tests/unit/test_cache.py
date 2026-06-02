"""Unit tests for refchecker.core.cache module."""

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from refchecker.core.cache import ResultCache
from refchecker.core.models import (
    AdapterMatch,
    ReferenceItem,
    VerificationResult,
    VerificationStatus,
)


# --- Helpers ---

def _ref(
    title: str = "Test Paper",
    authors: list[str] | None = None,
    year: int | None = 2024,
) -> ReferenceItem:
    return ReferenceItem(
        title=title, authors=authors or ["Alice Smith"], year=year,
    )


def _match(adapter: str = "crossref", found: bool = True, score: float = 0.95) -> AdapterMatch:
    return AdapterMatch(
        adapter_name=adapter, found=found, composite_score=score,
        title_score=score, author_score=score, year_score=1.0, venue_score=1.0,
        matched_title="Test Paper" if found else None,
        matched_authors=["Alice Smith"] if found else [],
        matched_year=2024 if found else None,
    )


def _result(
    ref: ReferenceItem | None = None,
    status: VerificationStatus = VerificationStatus.VERIFIED,
    best_score: float = 0.95,
) -> VerificationResult:
    return VerificationResult(
        reference=ref or _ref(), status=status,
        matches=[_match()], best_score=best_score,
    )


# --- Tests ---

class TestCacheKey:
    """Tests for cache key generation."""

    def test_key_normalization_case(self) -> None:
        """Different case produces same key."""
        cache = ResultCache()
        ref1 = _ref(title="Test Paper")
        ref2 = _ref(title="test paper")
        assert cache._make_key(ref1) == cache._make_key(ref2)

    def test_key_normalization_whitespace(self) -> None:
        """Extra whitespace produces same key."""
        cache = ResultCache()
        ref1 = _ref(title="Test Paper")
        ref2 = _ref(title="  Test Paper  ")
        assert cache._make_key(ref1) == cache._make_key(ref2)

    def test_key_uses_first_author(self) -> None:
        """Key is based on first author only."""
        cache = ResultCache()
        ref1 = _ref(authors=["Alice Smith", "Bob Jones"])
        ref2 = _ref(authors=["Alice Smith", "Carol White"])
        assert cache._make_key(ref1) == cache._make_key(ref2)

    def test_key_includes_year(self) -> None:
        """Different years produce different keys."""
        cache = ResultCache()
        ref1 = _ref(year=2023)
        ref2 = _ref(year=2024)
        assert cache._make_key(ref1) != cache._make_key(ref2)

    def test_key_different_title(self) -> None:
        """Different titles produce different keys."""
        cache = ResultCache()
        ref1 = _ref(title="Paper A")
        ref2 = _ref(title="Paper B")
        assert cache._make_key(ref1) != cache._make_key(ref2)

    def test_key_chinese_title(self) -> None:
        """Chinese characters normalize correctly."""
        cache = ResultCache()
        ref1 = _ref(title="中文论文标题")
        ref2 = _ref(title="中文论文标题")
        assert cache._make_key(ref1) == cache._make_key(ref2)


class TestCachePutGet:
    """Tests for put and get operations."""

    def test_put_and_get(self) -> None:
        """Store and retrieve a result."""
        cache = ResultCache()
        ref = _ref()
        result = _result(ref=ref)
        cache.put(ref, result)
        assert cache.get(ref) is not None
        assert cache.get(ref).status == VerificationStatus.VERIFIED

    def test_miss(self) -> None:
        """Non-existent key returns None."""
        cache = ResultCache()
        assert cache.get(_ref(title="Nonexistent")) is None

    def test_missing_year(self) -> None:
        """Reference with year=None still works."""
        cache = ResultCache()
        ref = _ref(year=None)
        result = _result(ref=ref)
        cache.put(ref, result)
        assert cache.get(ref) is not None


class TestCacheClear:
    """Tests for cache clearing."""

    def test_clear_memory(self) -> None:
        """Clear removes in-memory entries."""
        cache = ResultCache()
        ref = _ref()
        cache.put(ref, _result(ref=ref))
        assert cache.get(ref) is not None
        cache.clear()
        assert cache.get(ref) is None


class TestCacheTTL:
    """Tests for TTL enforcement."""

    def test_ttl_expired(self, tmp_path: Path) -> None:
        """Expired entries are not returned."""
        cache = ResultCache(cache_dir=tmp_path, ttl_days=7)
        ref = _ref()
        result = _result(ref=ref)

        # Write directly with an old timestamp
        key = cache._make_key(ref)
        path = tmp_path / f"{key}.json"
        old_timestamp = time.time() - 8 * 86400  # 8 days ago
        data = {"timestamp": old_timestamp, "result": result.model_dump()}
        tmp_path.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, default=str), encoding="utf-8")

        # Should return None (expired)
        assert cache.get(ref) is None

    def test_ttl_not_expired(self, tmp_path: Path) -> None:
        """Non-expired entries are returned."""
        cache = ResultCache(cache_dir=tmp_path, ttl_days=7)
        ref = _ref()
        result = _result(ref=ref)
        cache.put(ref, result)

        # Should be in cache
        assert cache.get(ref) is not None


class TestCacheFilePersistence:
    """Tests for file-based caching."""

    def test_persist_to_file(self, tmp_path: Path) -> None:
        """Results are written to JSON files."""
        cache = ResultCache(cache_dir=tmp_path)
        ref = _ref()
        cache.put(ref, _result(ref=ref))

        # A JSON file should exist
        json_files = list(tmp_path.glob("*.json"))
        assert len(json_files) == 1

    def test_load_from_file(self, tmp_path: Path) -> None:
        """Previously cached results are loaded from file."""
        cache1 = ResultCache(cache_dir=tmp_path)
        ref = _ref()
        result = _result(ref=ref)
        cache1.put(ref, result)

        # Create new cache instance pointing to same dir
        cache2 = ResultCache(cache_dir=tmp_path)
        loaded = cache2.get(ref)
        assert loaded is not None
        assert loaded.status == result.status

    def test_clear_removes_files(self, tmp_path: Path) -> None:
        """Clear removes cached JSON files."""
        cache = ResultCache(cache_dir=tmp_path)
        ref = _ref()
        cache.put(ref, _result(ref=ref))
        assert len(list(tmp_path.glob("*.json"))) == 1

        cache.clear()
        assert len(list(tmp_path.glob("*.json"))) == 0
