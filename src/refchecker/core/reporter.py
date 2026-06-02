"""Markdown verification report generator for RefChecker.

Produces a structured Markdown report with summary statistics,
detailed results grouped by verification status, and suggested actions.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Sequence

from refchecker.core.logging import get_logger
from refchecker.core.models import VerificationResult, VerificationStatus

logger = get_logger(__name__)

# Status display order and labels
_STATUS_ORDER: list[tuple[VerificationStatus, str]] = [
    (VerificationStatus.VERIFIED, "✅ Verified"),
    (VerificationStatus.SUSPICIOUS, "⚠️ Suspicious"),
    (VerificationStatus.LIKELY_FABRICATED, "❌ Likely Fabricated"),
    (VerificationStatus.UNABLE_TO_VERIFY, "ℹ️ Unable to Verify"),
    (VerificationStatus.PENDING, "🔄 Pending"),
]


def generate_report(
    results: Sequence[VerificationResult],
    *,
    source_file: str | None = None,
    adapters: list[str] | None = None,
) -> str:
    """Generate a structured Markdown verification report.

    Args:
        results: Verification results to report on.
        source_file: Optional path to the source file that was verified.
        adapters: Optional list of adapter names used for verification.

    Returns:
        Markdown report as a string.
    """
    lines: list[str] = []

    # --- Title and Metadata ---
    lines.append("# RefChecker Verification Report")
    lines.append("")
    lines.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if source_file:
        lines.append(f"**Source file**: `{source_file}`")
    if adapters:
        lines.append(f"**Adapters**: {', '.join(adapters)}")
    lines.append(f"**Total references**: {len(results)}")
    lines.append("")

    # --- Summary Statistics Table ---
    lines.append("## Summary")
    lines.append("")
    lines.append("| Status | Count | Percentage |")
    lines.append("|--------|-------|------------|")

    total = len(results)
    for status, label in _STATUS_ORDER:
        count = sum(1 for r in results if r.status == status)
        pct = f"{count / total * 100:.1f}%" if total > 0 else "0.0%"
        lines.append(f"| {label} | {count} | {pct} |")

    lines.append("")

    # --- Detailed Results by Status ---
    lines.append("## Detailed Results")
    lines.append("")

    for status, label in _STATUS_ORDER:
        group = [r for r in results if r.status == status]
        if not group:
            continue

        lines.append(f"### {label} ({len(group)})")
        lines.append("")
        lines.append("| # | Title | Authors | Year | Best Score | Source |")
        lines.append("|---|-------|---------|------|------------|--------|")

        for i, r in enumerate(group, 1):
            title = r.reference.title[:60]
            authors = r.reference.display_authors[:40]
            year = str(r.reference.year or "—")
            score = f"{r.best_score:.2f}"

            # Find best source adapter
            source = ""
            for m in r.matches:
                if m.found and m.composite_score == r.best_score:
                    source = m.adapter_name
                    break

            lines.append(f"| {i} | {title} | {authors} | {year} | {score} | {source} |")

        lines.append("")

    # --- Suggested Actions ---
    actions = _suggest_actions(results)
    if actions:
        lines.append("## Suggested Actions")
        lines.append("")
        for action in actions:
            lines.append(f"- {action}")
        lines.append("")

    return "\n".join(lines)


def generate_report_to_file(
    results: Sequence[VerificationResult],
    path: str | Path,
    **kwargs: object,
) -> None:
    """Write Markdown report to a file.

    Args:
        results: Verification results to report on.
        path: Output file path.
        **kwargs: Additional arguments passed to generate_report().
    """
    path = Path(path)
    report = generate_report(results, **kwargs)  # type: ignore[arg-type]
    path.write_text(report, encoding="utf-8")
    logger.info("report_written", path=str(path), size=len(report))


def _suggest_actions(results: Sequence[VerificationResult]) -> list[str]:
    """Generate suggested actions based on verification results."""
    actions: list[str] = []

    fabricated = [r for r in results if r.status == VerificationStatus.LIKELY_FABRICATED]
    if fabricated:
        actions.append(
            f"**{len(fabricated)} references** were not found in any database. "
            "Manually verify these citations — they may be fabricated or have "
            "significant errors in title, authors, or year."
        )

    suspicious = [r for r in results if r.status == VerificationStatus.SUSPICIOUS]
    if suspicious:
        actions.append(
            f"**{len(suspicious)} references** have partial matches. "
            "Check for typos in titles, missing co-authors, or incorrect years."
        )

    unable = [r for r in results if r.status == VerificationStatus.UNABLE_TO_VERIFY]
    if unable:
        actions.append(
            f"**{len(unable)} references** could not be verified due to network "
            "errors or unavailable sources. Re-run verification when connectivity "
            "is restored."
        )

    return actions
