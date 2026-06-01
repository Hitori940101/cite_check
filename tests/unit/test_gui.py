"""GUI tests for RefChecker using pytest-qt.

Tests cover result table, progress widget, exporter, and verify worker.
GUI widget tests are skipped if no display is available (headless CI).
"""

import os
import sys

import pytest

# GUI tests run on macOS (native display), Windows, or with QT_QPA_PLATFORM=offscreen
_HAS_DISPLAY = (
    os.environ.get("DISPLAY")
    or os.environ.get("QT_QPA_PLATFORM") == "offscreen"
    or sys.platform in ("win32", "darwin")
)
pytestmark = pytest.mark.skipif(not _HAS_DISPLAY, reason="No display available (headless)")

from refchecker.core.models import (
    AdapterMatch,
    ReferenceItem,
    VerificationResult,
    VerificationStatus,
)


def _make_result(**overrides) -> VerificationResult:
    """Create a test verification result."""
    defaults = {
        "reference": ReferenceItem(
            title="Test Paper",
            authors=["Author A"],
            year=2023,
        ),
        "matches": [
            AdapterMatch(
                adapter_name="test",
                found=True,
                composite_score=0.95,
                matched_title="Test Paper",
            )
        ],
        "best_score": 0.95,
        "status": VerificationStatus.VERIFIED,
    }
    defaults.update(overrides)
    return VerificationResult(**defaults)


# --- Result Table Tests ---

class TestResultTable:
    """Tests for the result table widget."""

    def test_empty_table(self, qtbot) -> None:
        """Empty table has no rows."""
        from refchecker.gui.widgets.result_table import ResultTableWidget
        table = ResultTableWidget()
        qtbot.addWidget(table)
        assert table.rowCount() == 0

    def test_set_results(self, qtbot) -> None:
        """Setting results populates rows."""
        from refchecker.gui.widgets.result_table import ResultTableWidget
        table = ResultTableWidget()
        qtbot.addWidget(table)
        results = [
            _make_result(status=VerificationStatus.VERIFIED),
            _make_result(status=VerificationStatus.SUSPICIOUS, best_score=0.70),
        ]
        table.set_results(results)
        assert table.rowCount() == 2
        assert table.get_results() == results

    def test_verified_row_has_checkmark(self, qtbot) -> None:
        """Verified rows show ✅ symbol."""
        from refchecker.gui.widgets.result_table import ResultTableWidget
        table = ResultTableWidget()
        qtbot.addWidget(table)
        table.set_results([_make_result(status=VerificationStatus.VERIFIED)])
        status_item = table.item(0, 2)  # Col 2 = Status (col 0=checkbox, col 1=#, col 2=status)
        assert status_item is not None
        assert "✅" in status_item.text()


# --- Progress Widget Tests ---

class TestProgressWidget:
    """Tests for the progress widget."""

    def test_initial_state(self, qtbot) -> None:
        """Progress starts at 0."""
        from refchecker.gui.widgets.progress import ProgressWidget
        progress = ProgressWidget()
        qtbot.addWidget(progress)
        assert progress._progress_bar.value() == 0

    def test_set_progress(self, qtbot) -> None:
        """Setting progress updates bar."""
        from refchecker.gui.widgets.progress import ProgressWidget
        progress = ProgressWidget()
        qtbot.addWidget(progress)
        progress.set_progress(5, 10)
        assert progress._progress_bar.value() == 50

    def test_set_complete(self, qtbot) -> None:
        """Complete sets to 100%."""
        from refchecker.gui.widgets.progress import ProgressWidget
        progress = ProgressWidget()
        qtbot.addWidget(progress)
        progress.set_complete(20)
        assert progress._progress_bar.value() == 100


# --- Exporter Module Tests ---

class TestExporter:
    """Tests for the exporter module (no display needed)."""

    @pytest.mark.skipif(False, reason="Always run")  # Override module skipif
    def test_csv_export(self) -> None:
        """CSV export produces valid content."""
        from refchecker.core.exporter import export_csv
        results = [_make_result()]
        csv_str = export_csv(results)
        assert "Test Paper" in csv_str
        assert "verified" in csv_str

    def test_bibtex_export(self) -> None:
        """BibTeX export produces valid entries."""
        from refchecker.core.exporter import export_bibtex
        results = [_make_result()]
        bib = export_bibtex(results)
        assert "@" in bib
        assert "Test Paper" in bib

    def test_bibtex_filters_fabricated(self) -> None:
        """BibTeX export excludes fabricated entries by default."""
        from refchecker.core.exporter import export_bibtex
        results = [
            _make_result(status=VerificationStatus.VERIFIED),
            _make_result(status=VerificationStatus.LIKELY_FABRICATED, best_score=0.3),
        ]
        bib = export_bibtex(results)
        assert "Test Paper" in bib
        assert bib.count("@") == 1


# --- Verify Worker Tests ---

class TestVerifyWorker:
    """Tests for the verify worker."""

    def test_worker_creation(self, qtbot) -> None:
        """Worker can be created with references and engine."""
        from refchecker.gui.workers.verify_worker import VerifyWorker
        from refchecker.engine import VerificationEngine

        engine = VerificationEngine([])
        refs = [ReferenceItem(title="Test", authors=[])]
        worker = VerifyWorker(refs, engine)
        # VerifyWorker is QThread, not QWidget — just verify creation
        assert worker is not None
        worker.deleteLater()

    def test_cancel(self) -> None:
        """Cancel sets cancelled flag."""
        from refchecker.gui.workers.verify_worker import VerifyWorker
        from refchecker.engine import VerificationEngine

        engine = VerificationEngine([])
        refs = [ReferenceItem(title="Test", authors=[])]
        worker = VerifyWorker(refs, engine)
        worker.cancel()
        assert worker._is_cancelled is True
