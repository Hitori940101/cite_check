"""Additional tests for scholar_adapter to improve coverage.

Tests pure-logic methods (_parse_results, _extract_link_text,
cache methods) that don't require network access.
"""

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from refchecker.core.models import ReferenceItem
from refchecker.adapters.scholar_adapter import ScholarAdapter


def _ref(
    title: str = "Attention Is All You Need",
    authors: list[str] | None = None,
    year: int | None = 2017,
) -> ReferenceItem:
    return ReferenceItem(
        title=title,
        authors=authors or ["Ashish Vaswani", "Noam Shazeer"],
        year=year,
    )


@pytest.fixture
def adapter() -> ScholarAdapter:
    return ScholarAdapter()


class TestParseResults:
    """Tests for _parse_results (pure logic, no network)."""

    def test_matching_html(self, adapter: ScholarAdapter) -> None:
        """Well-formed Scholar HTML with matching title returns found."""
        html = '''
        <div class="gs_r gs_or gs_scl">
          <div class="gs_ri">
            <h3 class="gs_rt"><a href="https://example.com">Attention Is All You Need</a></h3>
            <div class="gs_a">Vaswani, A - Shazeer, N - 2017 - NeurIPS</div>
          </div>
        </div>
        '''
        ref = _ref()
        match = adapter._parse_results(html, ref)
        assert match.found is True
        assert match.composite_score > 0.6

    def test_no_results_html(self, adapter: ScholarAdapter) -> None:
        """Empty HTML returns not-found match."""
        match = adapter._parse_results("<html><body></body></html>", _ref())
        assert match.found is False

    def test_alt_pattern_html(self, adapter: ScholarAdapter) -> None:
        """HTML without gs_rt class uses alt pattern."""
        html = '''
        <h3><a href="https://example.com">Attention Is All You Need</a></h3>
        <div class="gs_a">Vaswani, A - Shazeer, N - 2017</div>
        '''
        match = adapter._parse_results(html, _ref())
        # Should at least parse something
        assert match.adapter_name == "scholar"

    def test_unrelated_title_low_score(self, adapter: ScholarAdapter) -> None:
        """Unrelated title produces low composite score."""
        html = '''
        <div class="gs_r gs_or gs_scl">
          <div class="gs_ri">
            <h3 class="gs_rt"><a href="https://example.com">Completely Unrelated Paper Title</a></h3>
            <div class="gs_a">Smith, J - 2020 - Nature</div>
          </div>
        </div>
        '''
        match = adapter._parse_results(html, _ref())
        assert match.composite_score < 0.6
        assert match.found is False

    def test_multiple_results_best_wins(self, adapter: ScholarAdapter) -> None:
        """Multiple results selects the best scoring match."""
        html = '''
        <div class="gs_r gs_or gs_scl">
          <div class="gs_ri">
            <h3 class="gs_rt"><a href="#">Unrelated Paper</a></h3>
            <div class="gs_a">X, Y - 2020</div>
          </div>
        </div>
        <div class="gs_r gs_or gs_scl">
          <div class="gs_ri">
            <h3 class="gs_rt"><a href="#">Attention Is All You Need</a></h3>
            <div class="gs_a">Vaswani, A - Shazeer, N - 2017 - NeurIPS</div>
          </div>
        </div>
        '''
        match = adapter._parse_results(html, _ref())
        assert match.found is True
        assert "Attention" in (match.matched_title or "")


class TestExtractLinkText:
    """Tests for _extract_link_text static helper."""

    def test_with_anchor_tag(self) -> None:
        """Extracts text from <a> tag."""
        result = ScholarAdapter._extract_link_text('<a href="x">My Title</a>')
        assert result == "My Title"

    def test_without_anchor_tag(self) -> None:
        """Returns plain text if no <a> tag."""
        result = ScholarAdapter._extract_link_text("Plain text")
        assert result == "Plain text"

    def test_empty_string(self) -> None:
        """Empty string returns empty."""
        result = ScholarAdapter._extract_link_text("")
        assert result == ""


class TestCacheMethods:
    """Tests for mirror cache I/O methods."""

    def test_load_cached_mirror_exists(self, adapter: ScholarAdapter, tmp_path: Path) -> None:
        """Load returns URL when cache file exists."""
        cache_file = tmp_path / "gufen_mirror.json"
        cache_file.write_text(json.dumps({"url": "https://mirror.example.com", "timestamp": time.time()}))
        with patch("refchecker.adapters.scholar_adapter._MIRROR_CACHE_FILE", cache_file):
            result = adapter._load_cached_mirror()
        assert result == "https://mirror.example.com"

    def test_load_cached_mirror_missing(self, adapter: ScholarAdapter, tmp_path: Path) -> None:
        """Load returns None when cache file doesn't exist."""
        cache_file = tmp_path / "nonexistent.json"
        with patch("refchecker.adapters.scholar_adapter._MIRROR_CACHE_FILE", cache_file):
            result = adapter._load_cached_mirror()
        assert result is None

    def test_save_cached_mirror(self, adapter: ScholarAdapter, tmp_path: Path) -> None:
        """Save writes JSON to cache file."""
        cache_file = tmp_path / "gufen_mirror.json"
        with patch("refchecker.adapters.scholar_adapter._MIRROR_CACHE_FILE", cache_file), \
             patch("refchecker.adapters.scholar_adapter._MIRROR_CACHE_DIR", tmp_path):
            adapter._save_cached_mirror("https://mirror.example.com")
        assert cache_file.exists()
        data = json.loads(cache_file.read_text())
        assert data["url"] == "https://mirror.example.com"

    def test_is_cache_stale_fresh(self, adapter: ScholarAdapter, tmp_path: Path) -> None:
        """Fresh cache returns False."""
        cache_file = tmp_path / "gufen_mirror.json"
        cache_file.write_text(json.dumps({"url": "https://mirror.example.com", "timestamp": time.time()}))
        with patch("refchecker.adapters.scholar_adapter._MIRROR_CACHE_FILE", cache_file):
            assert adapter._is_cache_stale() is False

    def test_is_cache_stale_old(self, adapter: ScholarAdapter, tmp_path: Path) -> None:
        """Old cache returns True."""
        cache_file = tmp_path / "gufen_mirror.json"
        cache_file.write_text(json.dumps({"url": "https://mirror.example.com", "timestamp": time.time() - 100000}))
        with patch("refchecker.adapters.scholar_adapter._MIRROR_CACHE_FILE", cache_file):
            assert adapter._is_cache_stale() is True

    def test_is_cache_stale_no_file(self, adapter: ScholarAdapter, tmp_path: Path) -> None:
        """Missing cache file returns True."""
        cache_file = tmp_path / "nonexistent.json"
        with patch("refchecker.adapters.scholar_adapter._MIRROR_CACHE_FILE", cache_file):
            assert adapter._is_cache_stale() is True


class TestScholarAdapterInit:
    """Tests for adapter initialization."""

    def test_name(self) -> None:
        """Adapter name is 'scholar'."""
        adapter = ScholarAdapter()
        assert adapter.name == "scholar"

    def test_default_init(self) -> None:
        """Adapter initializes with defaults."""
        adapter = ScholarAdapter()
        assert adapter._working_mirror is None
