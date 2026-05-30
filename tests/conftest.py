"""Shared test fixtures and configuration."""

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    """Return path to test fixtures directory."""
    return FIXTURES_DIR


@pytest.fixture
def sample_bib_path(fixtures_dir: Path) -> Path:
    """Return path to a sample .bib file for testing."""
    return fixtures_dir / "sample.bib"
