"""Main window for RefChecker desktop GUI.

Layout:
  ┌─────────────────────────────────────┐
  │  Toolbar: [Verify] [Export] [Settings]│
  ├─────────────────────────────────────┤
  │  File Drop Area (collapsible)        │
  ├─────────────────────────────────────┤
  │  Adapter selector checkboxes         │
  ├─────────────────────────────────────┤
  │  Progress bar                        │
  ├─────────────────────────────────────┤
  │  Result Table (stretch)              │
  └─────────────────────────────────────┘
"""

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from refchecker.adapters.aminer_adapter import AMinerAdapter
from refchecker.adapters.arxiv_adapter import ArxivAdapter
from refchecker.adapters.baidu_adapter import BaiduAdapter
from refchecker.adapters.cnki_adapter import CNKIAdapter
from refchecker.adapters.crossref_adapter import CrossrefAdapter
from refchecker.adapters.openalex_adapter import OpenAlexAdapter
from refchecker.adapters.s2_adapter import S2Adapter
from refchecker.adapters.scholar_adapter import ScholarAdapter
from refchecker.config import load_config
from refchecker.core.logging import get_logger
from refchecker.core.models import ReferenceItem, VerificationResult
from refchecker.core.parser import parse_file
from refchecker.engine import VerificationEngine

logger = get_logger(__name__)

_ADAPTER_REGISTRY = {
    "crossref": CrossrefAdapter,
    "s2": S2Adapter,
    "openalex": OpenAlexAdapter,
    "aminer": AMinerAdapter,
    "baidu": BaiduAdapter,
    "cnki": CNKIAdapter,
    "arxiv": ArxivAdapter,
    "scholar": ScholarAdapter,
}

# Adapters shown as checkboxes in the UI
_UI_ADAPTERS = ["crossref", "s2", "openalex", "aminer", "baidu", "arxiv", "scholar"]


class MainWindow(QMainWindow):
    """Main application window for RefChecker."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("RefChecker — Citation Verification")
        self.setMinimumSize(800, 600)
        self._worker: Optional[object] = None
        self._references: list[ReferenceItem] = []
        self._selected_indices: list[int] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build the main window layout."""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(8)

        # --- Toolbar ---
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self._verify_btn = QPushButton("▶ Verify")
        self._verify_btn.setEnabled(False)
        self._verify_btn.clicked.connect(self._start_verification)
        toolbar.addWidget(self._verify_btn)

        self._cancel_btn = QPushButton("✕ Cancel")
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.clicked.connect(self._cancel_verification)
        toolbar.addWidget(self._cancel_btn)

        toolbar.addSeparator()

        self._export_btn = QPushButton("📥 Export")
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self._show_export_dialog)
        toolbar.addWidget(self._export_btn)

        toolbar.addSeparator()

        settings_btn = QPushButton("⚙ Settings")
        settings_btn.clicked.connect(self._show_settings)
        toolbar.addWidget(settings_btn)

        # --- File drop area ---
        from refchecker.gui.widgets.file_drop import FileDropWidget
        self._file_drop = FileDropWidget()
        self._file_drop.file_selected.connect(self._on_file_selected)
        layout.addWidget(self._file_drop)

        # --- Adapter selector ---
        adapter_row = QHBoxLayout()
        adapter_label = QLabel("Adapters:")
        adapter_label.setStyleSheet("font-weight: bold;")
        adapter_row.addWidget(adapter_label)

        self._adapter_checks: dict[str, QCheckBox] = {}
        config = load_config()
        for name in _UI_ADAPTERS:
            check = QCheckBox(name)
            check.setChecked(config.is_adapter_enabled(name))
            self._adapter_checks[name] = check
            adapter_row.addWidget(check)

        adapter_row.addStretch()
        layout.addLayout(adapter_row)

        # --- Progress ---
        from refchecker.gui.widgets.progress import ProgressWidget
        self._progress = ProgressWidget()
        layout.addWidget(self._progress)

        # --- Result table ---
        from refchecker.gui.widgets.result_table import ResultTableWidget
        self._result_table = ResultTableWidget()
        self._result_table.export_requested.connect(self._show_export_dialog)
        layout.addWidget(self._result_table, stretch=1)

        # --- Status bar ---
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._statusbar.showMessage("Ready — drop a .bib or .txt file to start")

        # --- Toast manager ---
        from refchecker.gui.dialogs.toast import ToastManager
        self._toast_manager: Optional[object] = None

    def _get_toast_manager(self) -> object:
        """Lazily create toast manager after window is shown."""
        from refchecker.gui.dialogs.toast import ToastManager
        if self._toast_manager is None:
            self._toast_manager = ToastManager(self.centralWidget())
        return self._toast_manager

    # --- File handling ---

    def _on_file_selected(self, path: Path) -> None:
        """Handle file selection from drop widget.

        Args:
            path: Path to the selected reference file.
        """
        try:
            self._references = parse_file(str(path))
            count = len(self._references)
            self._statusbar.showMessage(f"Loaded {count} references from {path.name}")
            self._verify_btn.setEnabled(count > 0)
            self._file_drop.setHidden(True)

            # Immediately show references in the result table
            self._result_table.set_references(self._references)
            self._export_btn.setEnabled(False)
        except Exception as exc:
            QMessageBox.critical(self, "Parse Error", f"Failed to parse file:\n{exc}")

    # --- Verification ---

    def _build_adapters(self) -> list:
        """Build adapter instances from enabled checkboxes.

        Returns:
            List of VerificationAdapter instances.
        """
        config = load_config()
        adapters = []
        for name, check in self._adapter_checks.items():
            if check.isChecked() and name in _ADAPTER_REGISTRY:
                adapter_config = config.get_adapter_config(name)
                adapters.append(_ADAPTER_REGISTRY[name](**adapter_config))
        return adapters

    def _start_verification(self) -> None:
        """Start background verification."""
        if not self._references:
            return

        # Get only the references the user has checked
        selected_indices = self._result_table.get_selected_indices()
        if not selected_indices:
            QMessageBox.warning(self, "No Selection", "Please select at least one reference to verify.")
            return

        selected_refs = [self._references[i] for i in selected_indices]
        self._selected_indices = selected_indices

        adapters = self._build_adapters()
        if not adapters:
            QMessageBox.warning(self, "No Adapters", "Please enable at least one adapter.")
            return

        engine = VerificationEngine(adapters)

        from refchecker.gui.workers.verify_worker import VerifyWorker
        self._worker = VerifyWorker(selected_refs, engine, parent=self)
        self._worker.progress.connect(self._on_progress)
        self._worker.result_ready.connect(self._on_results_ready)
        self._worker.error.connect(self._on_error)
        self._worker.rate_limited.connect(self._on_rate_limited)

        self._verify_btn.setEnabled(False)
        self._cancel_btn.setEnabled(True)
        self._export_btn.setEnabled(False)
        self._progress.reset()

        self._statusbar.showMessage("Verifying…")
        self._worker.start()

    def _cancel_verification(self) -> None:
        """Cancel running verification."""
        if self._worker:
            self._worker.cancel()
            self._worker = None
        self._verify_btn.setEnabled(bool(self._references))
        self._cancel_btn.setEnabled(False)
        self._statusbar.showMessage("Verification cancelled")

    def _on_progress(self, current: int, total: int, result: object) -> None:
        """Handle incremental progress update from worker.

        Updates the progress bar and the individual table row.

        Args:
            current: Completed count (1-based).
            total: Total count.
            result: VerificationResult for the row that just completed.
        """
        self._progress.set_progress(current, total)

        if isinstance(result, VerificationResult) and self._selected_indices:
            # Map worker index (1-based) back to table row
            worker_idx = current - 1
            if worker_idx < len(self._selected_indices):
                table_row = self._selected_indices[worker_idx]
                self._result_table.update_row(table_row, result)

    def _on_results_ready(self, results: list) -> None:
        """Handle completed verification.

        Results are already in the table via incremental updates.
        This handler just updates UI state.

        Args:
            results: List of VerificationResult (complete batch).
        """
        self._progress.set_complete(len(results))
        self._verify_btn.setEnabled(True)
        self._cancel_btn.setEnabled(False)
        self._export_btn.setEnabled(True)
        self._worker = None

        verified = sum(1 for r in results if r.status.value == "verified")
        total = len(results)
        self._statusbar.showMessage(f"Done — {verified}/{total} verified")

    def _on_error(self, error_msg: str) -> None:
        """Handle verification error.

        Args:
            error_msg: Error message from worker.
        """
        self._verify_btn.setEnabled(bool(self._references))
        self._cancel_btn.setEnabled(False)
        self._statusbar.showMessage(f"Error: {error_msg}")
        QMessageBox.critical(self, "Verification Error", error_msg)

    def _on_rate_limited(self, adapter_name: str) -> None:
        """Handle rate-limit notification from worker.

        Args:
            adapter_name: Name of the rate-limited adapter.
        """
        toast_mgr = self._get_toast_manager()
        toast_mgr.show(
            f"⚠️ {adapter_name} rate limit reached. Add an API key in Settings for higher limits.",
            severity="warning",
            action_text="Open Settings",
            on_action=self._show_settings,
        )

    # --- Dialogs ---

    def _show_settings(self) -> None:
        """Open the settings dialog."""
        from refchecker.gui.dialogs.settings import SettingsDialog
        dialog = SettingsDialog(self)
        dialog.exec()

    def _show_export_dialog(self) -> None:
        """Open the export dialog."""
        results = self._result_table.get_results()
        if not results:
            QMessageBox.information(self, "No Results", "Run verification first.")
            return

        from refchecker.gui.dialogs.export import ExportDialog
        dialog = ExportDialog(results, self)
        dialog.exec()
