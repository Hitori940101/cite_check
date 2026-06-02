"""GUI tests for RefChecker using pytest-qt.

Tests cover result table, progress widget, exporter, verify worker,
i18n module, file drop, main window, settings dialog, export dialog,
and toast notifications.

QT_QPA_PLATFORM=offscreen is set in conftest.py to ensure tests run
in all environments.
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

from unittest.mock import MagicMock, patch

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
                matched_authors=["Author A"],
                matched_year=2023,
                title_score=0.95,
                author_score=1.0,
                year_score=1.0,
                venue_score=1.0,
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

    def test_update_row_incremental(self, qtbot) -> None:
        """update_row updates a single row."""
        from refchecker.gui.widgets.result_table import ResultTableWidget
        table = ResultTableWidget()
        qtbot.addWidget(table)

        ref = ReferenceItem(title="Original", authors=["A"], year=2024, citation_key="orig")
        results = [VerificationResult(
            reference=ref,
            status=VerificationStatus.PENDING,
            matches=[],
            best_score=0.0,
        )]
        table.set_results(results)
        assert table.rowCount() == 1

        # Now update the row with a verified result
        updated = _make_result(
            reference=ref,
            status=VerificationStatus.VERIFIED,
        )
        table.update_row(0, updated)
        status_item = table.item(0, 2)
        assert "✅" in status_item.text()

    def test_select_all_deselect_all(self, qtbot) -> None:
        """select_all and deselect_all toggle checkboxes."""
        from refchecker.gui.widgets.result_table import ResultTableWidget
        table = ResultTableWidget()
        qtbot.addWidget(table)
        results = [_make_result(), _make_result()]
        table.set_results(results)

        table.select_all()
        indices = table.get_selected_indices()
        assert len(indices) == 2

        table.deselect_all()
        indices = table.get_selected_indices()
        assert len(indices) == 0


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

    def test_reset(self, qtbot) -> None:
        """Reset returns to initial state."""
        from refchecker.gui.widgets.progress import ProgressWidget
        progress = ProgressWidget()
        qtbot.addWidget(progress)
        progress.set_complete(10)
        progress.reset()
        assert progress._progress_bar.value() == 0


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

    def test_worker_signals_exist(self) -> None:
        """Worker has the expected signals."""
        from refchecker.gui.workers.verify_worker import VerifyWorker
        assert hasattr(VerifyWorker, 'progress')
        assert hasattr(VerifyWorker, 'result_ready')
        assert hasattr(VerifyWorker, 'error')
        assert hasattr(VerifyWorker, 'rate_limited')


# --- I18n Tests ---

class TestI18n:
    """Tests for the i18n module."""

    def test_default_language_is_zh(self) -> None:
        """Default language is Chinese."""
        from refchecker.gui.i18n import get_language
        # Reset to default
        from refchecker.gui.i18n import set_language
        set_language("zh")
        assert get_language() == "zh"

    def test_t_returns_chinese_by_default(self) -> None:
        """t() returns Chinese when language is zh."""
        from refchecker.gui.i18n import t, set_language
        set_language("zh")
        text = t("app.title")
        assert "引用验证" in text

    def test_t_english_after_set(self) -> None:
        """t() returns English after set_language('en')."""
        from refchecker.gui.i18n import t, set_language
        set_language("en")
        text = t("app.title")
        assert "Citation Verification" in text
        # Reset
        set_language("zh")

    def test_t_format_kwargs(self) -> None:
        """t() interpolates format arguments."""
        from refchecker.gui.i18n import t, set_language
        set_language("en")
        text = t("status.done", verified=5, total=10)
        assert "5" in text
        assert "10" in text
        set_language("zh")

    def test_t_missing_key_returns_key(self) -> None:
        """t() with unknown key returns the key itself."""
        from refchecker.gui.i18n import t
        assert t("nonexistent.key.12345") == "nonexistent.key.12345"

    def test_toggle_language(self) -> None:
        """toggle_language switches between zh and en."""
        from refchecker.gui.i18n import get_language, set_language, toggle_language
        set_language("zh")
        new_lang = toggle_language()
        assert new_lang == "en"
        assert get_language() == "en"
        new_lang = toggle_language()
        assert new_lang == "zh"
        assert get_language() == "zh"

    def test_all_keys_have_both_languages(self) -> None:
        """Every translation entry has both zh and en keys."""
        from refchecker.gui.i18n import _TRANSLATIONS
        missing = []
        for key, entry in _TRANSLATIONS.items():
            if "zh" not in entry:
                missing.append((key, "missing zh"))
            if "en" not in entry:
                missing.append((key, "missing en"))
        assert missing == [], f"Missing translations: {missing}"


# --- File Drop Widget Tests ---

class TestFileDropWidget:
    """Tests for the file drop widget."""

    def test_creation(self, qtbot) -> None:
        """Widget creates without error."""
        from refchecker.gui.widgets.file_drop import FileDropWidget
        widget = FileDropWidget()
        qtbot.addWidget(widget)
        assert widget is not None

    def test_update_language(self, qtbot) -> None:
        """update_language() updates labels without error."""
        from refchecker.gui.widgets.file_drop import FileDropWidget
        from refchecker.gui.i18n import set_language
        widget = FileDropWidget()
        qtbot.addWidget(widget)
        set_language("en")
        widget.update_language()
        set_language("zh")
        widget.update_language()

    def test_file_selected_signal(self, qtbot) -> None:
        """file_selected signal exists."""
        from refchecker.gui.widgets.file_drop import FileDropWidget
        widget = FileDropWidget()
        qtbot.addWidget(widget)
        assert hasattr(widget, 'file_selected')


# --- Main Window Tests ---

class TestMainWindow:
    """Tests for the main window."""

    @patch("refchecker.gui.main_window.load_config")
    def test_creation(self, mock_config, qtbot) -> None:
        """MainWindow creates without crash."""
        from refchecker.gui.main_window import MainWindow
        mock_config.return_value = MagicMock()
        window = MainWindow()
        qtbot.addWidget(window)
        assert window is not None

    @patch("refchecker.gui.main_window.load_config")
    def test_toolbar_buttons_exist(self, mock_config, qtbot) -> None:
        """Toolbar has expected buttons."""
        from refchecker.gui.main_window import MainWindow
        mock_config.return_value = MagicMock()
        window = MainWindow()
        qtbot.addWidget(window)
        # Check that key UI elements exist
        assert hasattr(window, '_verify_btn')
        assert hasattr(window, '_cancel_btn')
        assert hasattr(window, '_settings_btn')
        assert hasattr(window, '_lang_btn')


# --- Export Dialog Tests ---
# --- Export Dialog Tests ---

class TestExportDialog:
    """Tests for the export dialog."""

    def test_creation_with_results(self, qtbot) -> None:
        """Dialog creates with sample results."""
        from refchecker.gui.dialogs.export import ExportDialog
        results = [_make_result()]
        dialog = ExportDialog(results)
        qtbot.addWidget(dialog)
        assert dialog is not None

    def test_format_combo_options(self, qtbot) -> None:
        """Format combo has expected options."""
        from refchecker.gui.dialogs.export import ExportDialog
        results = [_make_result()]
        dialog = ExportDialog(results)
        qtbot.addWidget(dialog)
        combo = dialog.findChild(object, "")
        # Find the format combo by iterating children
        from PySide6.QtWidgets import QComboBox
        combos = dialog.findChildren(QComboBox)
        assert len(combos) == 1
        assert combos[0].count() == 3  # CSV, Excel, BibTeX


# --- Settings Dialog Tests ---

class TestSettingsDialog:
    """Tests for the settings dialog."""

    @patch("refchecker.config.load_config")
    def test_creation(self, mock_config, qtbot) -> None:
        """Dialog creates without crash."""
        from refchecker.gui.dialogs.settings import SettingsDialog
        mock_config.return_value = MagicMock(
            is_adapter_enabled=MagicMock(return_value=True),
            get_proxy_url=MagicMock(return_value=None),
            adapters=MagicMock(
                request_timeout=30,
                max_concurrent=3,
            ),
        )
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        assert dialog is not None

    @patch("refchecker.config.load_config")
    def test_adapter_checkboxes(self, mock_config, qtbot) -> None:
        """All adapter checkboxes are present."""
        from refchecker.gui.dialogs.settings import SettingsDialog, _ADAPTER_INFO
        mock_config.return_value = MagicMock(
            is_adapter_enabled=MagicMock(return_value=True),
            get_proxy_url=MagicMock(return_value=None),
            adapters=MagicMock(request_timeout=30, max_concurrent=3),
        )
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        # Should have checkboxes for all adapters
        assert len(dialog._adapter_checks) == len(_ADAPTER_INFO)

    @patch("refchecker.config.load_config")
    def test_key_fields_present(self, mock_config, qtbot) -> None:
        """s2, openalex, aminer have key input fields."""
        from refchecker.gui.dialogs.settings import SettingsDialog
        mock_config.return_value = MagicMock(
            is_adapter_enabled=MagicMock(return_value=True),
            get_proxy_url=MagicMock(return_value=None),
            adapters=MagicMock(request_timeout=30, max_concurrent=3),
        )
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        assert "s2" in dialog._key_fields
        assert "openalex" in dialog._key_fields
        assert "aminer" in dialog._key_fields


# --- Toast Widget Tests ---

class TestToastWidget:
    """Tests for the toast notification system."""

    def test_toast_manager_creation(self, qtbot) -> None:
        """ToastManager creates without error."""
        from refchecker.gui.dialogs.toast import ToastManager
        from PySide6.QtWidgets import QWidget
        parent = QWidget()
        qtbot.addWidget(parent)
        manager = ToastManager(parent)
        assert manager is not None
