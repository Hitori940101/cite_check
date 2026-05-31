"""Unit tests for the fuzzy matching scorer."""

import pytest

from refchecker.core.models import ReferenceItem
from refchecker.core.scorer import (
    compute_author_score,
    compute_composite_score,
    compute_title_score,
    compute_venue_score,
    compute_year_score,
    score_match,
)


class TestComputeTitleScore:
    """Tests for title similarity scoring."""

    def test_exact_match(self) -> None:
        """Identical titles score 1.0."""
        assert compute_title_score("Deep Learning", "Deep Learning") == 1.0

    def test_case_insensitive(self) -> None:
        """Case-insensitive matching."""
        assert compute_title_score("Deep Learning", "deep learning") == 1.0

    def test_empty_query(self) -> None:
        """Empty query returns 0.0."""
        assert compute_title_score("", "Some Title") == 0.0

    def test_empty_candidate(self) -> None:
        """Empty candidate returns 0.0."""
        assert compute_title_score("Some Title", "") == 0.0

    def test_similar_titles(self) -> None:
        """Similar titles score above 0.5."""
        score = compute_title_score(
            "Attention Is All You Need",
            "Attention is all you need",
        )
        assert score >= 0.9

    def test_different_titles(self) -> None:
        """Completely different titles score low."""
        score = compute_title_score(
            "Deep Learning",
            "Natural Language Processing",
        )
        assert score < 0.5

    def test_reorder_tokens(self) -> None:
        """Token reordering handled by token_sort_ratio."""
        score = compute_title_score(
            "Learning Deep",
            "Deep Learning",
        )
        assert score >= 0.9


class TestComputeAuthorScore:
    """Tests for author similarity scoring."""

    def test_exact_match(self) -> None:
        """Identical author lists score 1.0."""
        score = compute_author_score(
            ["Smith, John", "Doe, Jane"],
            ["Smith, John", "Doe, Jane"],
        )
        assert score == 1.0

    def test_superset_candidate(self) -> None:
        """Candidate with more authors scores high (subset match)."""
        score = compute_author_score(
            ["Vaswani, Ashish"],
            ["Vaswani, Ashish", "Shazeer, Noam", "Parmar, Niki"],
        )
        assert score >= 0.7

    def test_empty_query(self) -> None:
        """Empty query returns 0.0."""
        assert compute_author_score([], ["Author"]) == 0.0

    def test_empty_candidate(self) -> None:
        """Empty candidate returns 0.0."""
        assert compute_author_score(["Author"], []) == 0.0

    def test_completely_different(self) -> None:
        """Completely different authors score low."""
        score = compute_author_score(
            ["Smith, John"],
            ["Zhang, Wei"],
        )
        assert score < 0.5


class TestComputeYearScore:
    """Tests for year match scoring."""

    def test_exact_match(self) -> None:
        """Same year returns 1.0."""
        assert compute_year_score(2023, 2023) == 1.0

    def test_within_tolerance(self) -> None:
        """±1 year returns 0.8."""
        assert compute_year_score(2023, 2022) == 0.8
        assert compute_year_score(2023, 2024) == 0.8

    def test_outside_tolerance(self) -> None:
        """More than ±1 year returns 0.0."""
        assert compute_year_score(2023, 2020) == 0.0

    def test_missing_query_year(self) -> None:
        """Missing query year returns 0.5 (no penalty)."""
        assert compute_year_score(None, 2023) == 0.5

    def test_missing_candidate_year(self) -> None:
        """Missing candidate year returns 0.5."""
        assert compute_year_score(2023, None) == 0.5

    def test_both_missing(self) -> None:
        """Both missing returns 0.5."""
        assert compute_year_score(None, None) == 0.5


class TestComputeVenueScore:
    """Tests for venue similarity scoring."""

    def test_exact_match(self) -> None:
        """Same venue returns 1.0."""
        assert compute_venue_score("Nature", "Nature") == 1.0

    def test_similar_venue(self) -> None:
        """Similar venue names score high."""
        score = compute_venue_score(
            "Advances in Neural Information Processing Systems",
            "Advances in Neural Information Processing Systems (NeurIPS)",
        )
        assert score >= 0.7

    def test_missing_query(self) -> None:
        """Missing query venue returns 0.5."""
        assert compute_venue_score(None, "Nature") == 0.5

    def test_missing_candidate(self) -> None:
        """Missing candidate venue returns 0.5."""
        assert compute_venue_score("Nature", None) == 0.5


class TestComputeCompositeScore:
    """Tests for weighted composite scoring."""

    def test_weights_sum_to_one(self) -> None:
        """Weights should sum to approximately 1.0."""
        composite = compute_composite_score(
            title_score=1.0,
            author_score=1.0,
            year_score=1.0,
            venue_score=1.0,
        )
        assert composite == pytest.approx(1.0)

    def test_zero_scores(self) -> None:
        """All zeros gives 0.0."""
        assert compute_composite_score(
            title_score=0.0,
            author_score=0.0,
            year_score=0.0,
            venue_score=0.0,
        ) == 0.0


class TestScoreMatch:
    """Integration tests for the full score_match function."""

    def _make_ref(self) -> ReferenceItem:
        return ReferenceItem(
            title="Attention Is All You Need",
            authors=["Vaswani, Ashish", "Shazeer, Noam"],
            year=2017,
            journal="Advances in Neural Information Processing Systems",
        )

    def test_perfect_match(self) -> None:
        """Perfect match gives composite ≈1.0."""
        ref = self._make_ref()
        t, a, y, v, c = score_match(
            ref,
            matched_title="Attention Is All You Need",
            matched_authors=["Vaswani, Ashish", "Shazeer, Noam"],
            matched_year=2017,
            matched_journal="Advances in Neural Information Processing Systems",
        )
        assert t == 1.0
        assert a == 1.0
        assert y == 1.0
        assert v == 1.0
        assert c == pytest.approx(1.0)

    def test_partial_match(self) -> None:
        """Partial match gives reasonable composite."""
        ref = self._make_ref()
        t, a, y, v, c = score_match(
            ref,
            matched_title="Attention is All You Need",
            matched_authors=["Vaswani A"],
            matched_year=2017,
        )
        assert t >= 0.9
        assert c >= 0.5

    def test_no_match(self) -> None:
        """No match gives low composite."""
        ref = self._make_ref()
        t, a, y, v, c = score_match(
            ref,
            matched_title="Completely Different Paper",
            matched_authors=["Unknown Author"],
            matched_year=2000,
            matched_journal="Random Journal",
        )
        assert c < 0.5
