"""Unit tests for refchecker.core.reporter module."""

from pathlib import Path

import pytest

from refchecker.core.models import (
    AdapterMatch,
    ReferenceItem,
    VerificationResult,
    VerificationStatus,
)
from refchecker.core.reporter import generate_report, generate_report_to_file


# --- Helpers ---

def _ref(
    title: str = "Test Paper",
    authors: list[str] | None = None,
    year: int | None = 2024,
    citation_key: str = "test2024",
) -> ReferenceItem:
    return ReferenceItem(
        title=title, authors=authors or ["Alice Smith"],
        year=year, citation_key=citation_key,
    )


def _match(
    adapter_name: str = "crossref",
    found: bool = True,
    score: float = 0.95,
) -> AdapterMatch:
    return AdapterMatch(
        adapter_name=adapter_name, found=found,
        composite_score=score, title_score=score,
        author_score=score, year_score=1.0, venue_score=1.0,
        matched_title="Test Paper" if found else None,
        matched_authors=["Alice Smith"] if found else [],
        matched_year=2024 if found else None,
    )


def _result(
    ref: ReferenceItem | None = None,
    status: VerificationStatus = VerificationStatus.VERIFIED,
    matches: list[AdapterMatch] | None = None,
    best_score: float = 0.95,
) -> VerificationResult:
    return VerificationResult(
        reference=ref or _ref(), status=status,
        matches=matches or [_match()], best_score=best_score,
    )


# --- Tests ---

class TestGenerateReport:
    """Tests for generate_report()."""

    def test_empty_results(self) -> None:
        """Empty results produce a valid report with zeros."""
        report = generate_report([])
        assert "# RefChecker Verification Report" in report
        assert "**Total references**: 0" in report

    def test_all_verified(self) -> None:
        """All verified produces 100% in summary."""
        results = [_result(), _result(ref=_ref(title="Paper 2"))]
        report = generate_report(results)
        assert "100.0%" in report
        assert "✅ Verified" in report

    def test_all_fabricated(self) -> None:
        """All fabricated results trigger action suggestion."""
        results = [_result(
            status=VerificationStatus.LIKELY_FABRICATED,
            best_score=0.3,
            matches=[_match(found=False, score=0.3)],
        )]
        report = generate_report(results)
        assert "❌ Likely Fabricated" in report
        assert "manually verify" in report.lower()

    def test_mixed_statuses(self) -> None:
        """Mixed statuses produce all expected sections."""
        results = [
            _result(status=VerificationStatus.VERIFIED),
            _result(
                ref=_ref(title="Suspicious Paper"),
                status=VerificationStatus.SUSPICIOUS,
                best_score=0.70,
                matches=[_match(score=0.70)],
            ),
            _result(
                ref=_ref(title="Fake Paper"),
                status=VerificationStatus.LIKELY_FABRICATED,
                best_score=0.3,
                matches=[_match(found=False, score=0.3)],
            ),
        ]
        report = generate_report(results)
        assert "✅ Verified" in report
        assert "⚠️ Suspicious" in report
        assert "❌ Likely Fabricated" in report
        assert "Suggested Actions" in report

    def test_contains_summary_table(self) -> None:
        """Report has a Markdown summary table."""
        report = generate_report([_result()])
        assert "| Status | Count | Percentage |" in report
        assert "|--------|-------|------------|" in report

    def test_contains_timestamp(self) -> None:
        """Report header includes a timestamp."""
        report = generate_report([_result()])
        assert "**Generated**:" in report

    def test_chinese_title_renders(self) -> None:
        """Chinese characters in title render correctly."""
        results = [_result(ref=_ref(title="中文论文标题测试"))]
        report = generate_report(results)
        assert "中文论文标题测试" in report

    def test_statistics_accuracy(self) -> None:
        """Counts and percentages are accurate."""
        results = [
            _result(status=VerificationStatus.VERIFIED),
            _result(status=VerificationStatus.VERIFIED),
            _result(
                status=VerificationStatus.LIKELY_FABRICATED,
                best_score=0.2,
                matches=[_match(found=False, score=0.2)],
            ),
        ]
        report = generate_report(results)
        # 2 verified of 3 = 66.7%
        assert "66.7%" in report
        # 1 fabricated of 3 = 33.3%
        assert "33.3%" in report

    def test_with_source_file(self) -> None:
        """source_file appears in metadata."""
        report = generate_report([_result()], source_file="paper.bib")
        assert "**Source file**: `paper.bib`" in report

    def test_with_adapter_names(self) -> None:
        """adapter names appear in metadata."""
        report = generate_report([_result()], adapters=["crossref", "s2"])
        assert "**Adapters**: crossref, s2" in report

    def test_suggests_actions_for_unable(self) -> None:
        """Unable-to-verify results trigger action."""
        results = [_result(
            status=VerificationStatus.UNABLE_TO_VERIFY,
            best_score=0.0,
            matches=[AdapterMatch(
                adapter_name="crossref", found=False,
                composite_score=0.0, title_score=0.0,
                author_score=0.0, year_score=0.0, venue_score=0.0,
                matched_title=None, matched_authors=[], matched_year=None,
                error="network timeout",
            )],
        )]
        report = generate_report(results)
        assert "network" in report.lower() or "Re-run" in report

    def test_no_actions_when_all_verified(self) -> None:
        """No actions section when all verified."""
        results = [_result()]
        report = generate_report(results)
        assert "Suggested Actions" not in report


class TestGenerateReportToFile:
    """Tests for generate_report_to_file()."""

    def test_writes_file(self, tmp_path: Path) -> None:
        """Report is written to the specified file."""
        out = tmp_path / "report.md"
        generate_report_to_file([_result()], out)
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "# RefChecker Verification Report" in content

    def test_file_with_kwargs(self, tmp_path: Path) -> None:
        """Keyword args are forwarded to generate_report."""
        out = tmp_path / "report.md"
        generate_report_to_file([_result()], out, source_file="test.bib")
        content = out.read_text(encoding="utf-8")
        assert "test.bib" in content
