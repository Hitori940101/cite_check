"""Unit tests for Pydantic data models."""

import pytest

from refchecker.core.models import (
    AdapterMatch,
    ReferenceItem,
    VerificationResult,
    VerificationStatus,
)


class TestVerificationStatus:
    """Tests for the VerificationStatus enum."""

    def test_all_statuses_exist(self) -> None:
        """All five statuses are defined."""
        statuses = {s.value for s in VerificationStatus}
        assert statuses == {
            "verified",
            "suspicious",
            "likely_fabricated",
            "unable_to_verify",
            "pending",
        }

    def test_status_symbols(self) -> None:
        """Each status has a display symbol."""
        assert VerificationStatus.VERIFIED.symbol == "✅"
        assert VerificationStatus.SUSPICIOUS.symbol == "⚠️"
        assert VerificationStatus.LIKELY_FABRICATED.symbol == "❌"
        assert VerificationStatus.UNABLE_TO_VERIFY.symbol == "ℹ️"
        assert VerificationStatus.PENDING.symbol == "🔄"


class TestReferenceItem:
    """Tests for the ReferenceItem model."""

    def test_minimal_reference(self) -> None:
        """Create a reference with only a title."""
        ref = ReferenceItem(title="Test Paper")
        assert ref.title == "Test Paper"
        assert ref.authors == []
        assert ref.year is None
        assert ref.doi is None
        assert ref.journal is None

    def test_full_reference(self) -> None:
        """Create a reference with all fields."""
        ref = ReferenceItem(
            title="Deep Learning",
            authors=["Ian Goodfellow", "Yoshua Bengio", "Aaron Courville"],
            year=2016,
            journal="MIT Press",
            doi="10.1234/test",
            volume="1",
            issue="2",
            pages="1--100",
            publisher="MIT Press",
            entry_type="book",
            citation_key="goodfellow2016",
        )
        assert ref.year == 2016
        assert ref.doi == "10.1234/test"
        assert ref.volume == "1"
        assert ref.pages == "1--100"

    def test_frozen_immutability(self) -> None:
        """Reference items are immutable."""
        ref = ReferenceItem(title="Immutable")
        with pytest.raises(Exception):
            ref.title = "Mutated"  # type: ignore[misc]

    def test_year_coercion_from_string(self) -> None:
        """Year is coerced from string to int."""
        ref = ReferenceItem(title="Test", year="2023")
        assert ref.year == 2023
        assert isinstance(ref.year, int)

    def test_year_coercion_empty_string(self) -> None:
        """Empty year string becomes None."""
        ref = ReferenceItem(title="Test", year="  ")
        assert ref.year is None

    def test_year_coercion_invalid_string(self) -> None:
        """Invalid year string becomes None."""
        ref = ReferenceItem(title="Test", year="not-a-year")
        assert ref.year is None

    def test_year_none(self) -> None:
        """None year stays None."""
        ref = ReferenceItem(title="Test", year=None)
        assert ref.year is None

    def test_doi_normalization_url_prefix(self) -> None:
        """DOI is normalized by stripping URL prefix."""
        ref = ReferenceItem(title="Test", doi="https://doi.org/10.1234/test")
        assert ref.doi == "10.1234/test"

    def test_doi_normalization_http_prefix(self) -> None:
        """DOI is normalized for http prefix."""
        ref = ReferenceItem(title="Test", doi="http://doi.org/10.1234/test")
        assert ref.doi == "10.1234/test"

    def test_doi_normalization_doi_prefix(self) -> None:
        """DOI is normalized by stripping 'doi:' prefix."""
        ref = ReferenceItem(title="Test", doi="doi:10.1234/test")
        assert ref.doi == "10.1234/test"

    def test_doi_normalization_whitespace(self) -> None:
        """DOI whitespace is stripped."""
        ref = ReferenceItem(title="Test", doi="  10.1234/test  ")
        assert ref.doi == "10.1234/test"

    def test_doi_none(self) -> None:
        """None DOI stays None."""
        ref = ReferenceItem(title="Test", doi=None)
        assert ref.doi is None

    def test_doi_empty_string(self) -> None:
        """Empty DOI string becomes None."""
        ref = ReferenceItem(title="Test", doi="")
        assert ref.doi is None

    def test_display_authors_empty(self) -> None:
        """No authors shows 'Unknown'."""
        ref = ReferenceItem(title="Test")
        assert ref.display_authors == "Unknown"

    def test_display_authors_few(self) -> None:
        """Three or fewer authors are all shown."""
        ref = ReferenceItem(title="Test", authors=["A", "B", "C"])
        assert ref.display_authors == "A, B, C"

    def test_display_authors_many(self) -> None:
        """More than three authors shows first + et al."""
        ref = ReferenceItem(title="Test", authors=["A", "B", "C", "D"])
        assert ref.display_authors == "A et al."

    def test_has_doi_true(self) -> None:
        """has_doi returns True when DOI is present."""
        ref = ReferenceItem(title="Test", doi="10.1234/test")
        assert ref.has_doi is True

    def test_has_doi_false(self) -> None:
        """has_doi returns False when DOI is None."""
        ref = ReferenceItem(title="Test")
        assert ref.has_doi is False


class TestAdapterMatch:
    """Tests for the AdapterMatch model."""

    def test_basic_match(self) -> None:
        """Create a basic adapter match."""
        match = AdapterMatch(
            adapter_name="crossref",
            found=True,
            matched_title="Test Paper",
            composite_score=0.95,
        )
        assert match.adapter_name == "crossref"
        assert match.found is True
        assert match.composite_score == 0.95

    def test_no_match(self) -> None:
        """Create an adapter match where nothing was found."""
        match = AdapterMatch(
            adapter_name="s2",
            found=False,
        )
        assert match.found is False
        assert match.composite_score == 0.0

    def test_error_match(self) -> None:
        """Create an adapter match with an error."""
        match = AdapterMatch(
            adapter_name="openalex",
            found=False,
            error="Rate limited",
        )
        assert match.error == "Rate limited"

    def test_frozen(self) -> None:
        """Adapter matches are immutable."""
        match = AdapterMatch(adapter_name="test", found=True)
        with pytest.raises(Exception):
            match.found = False  # type: ignore[misc]


class TestVerificationResult:
    """Tests for the VerificationResult model."""

    def _make_ref(self) -> ReferenceItem:
        return ReferenceItem(title="Test Paper", authors=["Author A"], year=2023)

    def test_empty_result_is_fabricated(self) -> None:
        """No matches → LIKELY_FABRICATED."""
        ref = self._make_ref()
        result = VerificationResult(reference=ref)
        updated = result.determine_status()
        assert updated.status == VerificationStatus.LIKELY_FABRICATED

    def test_high_score_is_verified(self) -> None:
        """Score ≥ 0.85 → VERIFIED."""
        ref = self._make_ref()
        match = AdapterMatch(adapter_name="crossref", found=True, composite_score=0.92)
        result = VerificationResult(reference=ref, matches=[match], best_score=0.92)
        updated = result.determine_status()
        assert updated.status == VerificationStatus.VERIFIED

    def test_medium_score_is_suspicious(self) -> None:
        """Score 0.60–0.84 → SUSPICIOUS."""
        ref = self._make_ref()
        match = AdapterMatch(adapter_name="s2", found=True, composite_score=0.72)
        result = VerificationResult(reference=ref, matches=[match], best_score=0.72)
        updated = result.determine_status()
        assert updated.status == VerificationStatus.SUSPICIOUS

    def test_low_score_is_fabricated(self) -> None:
        """Score < 0.60 → LIKELY_FABRICATED."""
        ref = self._make_ref()
        match = AdapterMatch(adapter_name="s2", found=True, composite_score=0.45)
        result = VerificationResult(reference=ref, matches=[match], best_score=0.45)
        updated = result.determine_status()
        assert updated.status == VerificationStatus.LIKELY_FABRICATED

    def test_error_only_is_unable_to_verify(self) -> None:
        """Only errors, no found matches → UNABLE_TO_VERIFY."""
        ref = self._make_ref()
        match = AdapterMatch(adapter_name="s2", found=False, error="timeout")
        result = VerificationResult(reference=ref, matches=[match])
        updated = result.determine_status()
        assert updated.status == VerificationStatus.UNABLE_TO_VERIFY

    def test_with_match_accumulates(self) -> None:
        """with_match() adds a match and updates best score."""
        ref = self._make_ref()
        result = VerificationResult(reference=ref)
        match1 = AdapterMatch(adapter_name="crossref", found=True, composite_score=0.80)
        result = result.with_match(match1)
        assert len(result.matches) == 1
        assert result.best_score == 0.80

        match2 = AdapterMatch(adapter_name="s2", found=True, composite_score=0.90)
        result = result.with_match(match2)
        assert len(result.matches) == 2
        assert result.best_score == 0.90

    def test_with_match_no_found_gives_zero(self) -> None:
        """with_match() with unfound match keeps best_score 0."""
        ref = self._make_ref()
        result = VerificationResult(reference=ref)
        match = AdapterMatch(adapter_name="s2", found=False)
        result = result.with_match(match)
        assert result.best_score == 0.0

    def test_frozen(self) -> None:
        """Verification results are immutable."""
        ref = self._make_ref()
        result = VerificationResult(reference=ref)
        with pytest.raises(Exception):
            result.status = VerificationStatus.VERIFIED  # type: ignore[misc]
