"""Export dialog for RefChecker.

Allows the user to export verification results to:
- CSV (.csv)
- Excel (.xlsx) — color-coded
- Clean BibTeX (.bib) — only verified/suspicious entries
"""

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from PySide6.QtWidgets import QDialog

from refchecker.core.exporter import (
    export_bibtex_to_file,
    export_csv_to_file,
    export_excel,
)
from refchecker.core.logging import get_logger
from refchecker.core.models import VerificationResult, VerificationStatus

logger = get_logger(__name__)

_FORMAT_OPTIONS = [
    ("CSV (.csv)", "csv"),
    ("Excel (.xlsx) — color-coded", "xlsx"),
    ("BibTeX (.bib) — verified only", "bib"),
]


class ExportDialog(QDialog):
    """Dialog for exporting verification results.

    Args:
        results: List of verification results to export.
        parent: Parent widget.
    """

    def __init__(
        self,
        results: list[VerificationResult],
        parent: object = None,
    ) -> None:
        super().__init__(parent)
        self._results = results
        self.setWindowTitle("Export Results")
        self.setMinimumWidth(420)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build the dialog layout."""
        layout = QVBoxLayout(self)

        # Summary
        verified = sum(1 for r in self._results if r.status == VerificationStatus.VERIFIED)
        suspicious = sum(1 for r in self._results if r.status == VerificationStatus.SUSPICIOUS)
        fabricated = sum(1 for r in self._results if r.status == VerificationStatus.LIKELY_FABRICATED)
        unable = sum(1 for r in self._results if r.status == VerificationStatus.UNABLE_TO_VERIFY)

        summary = (
            f"Total: {len(self._results)} references\n"
            f"✅ Verified: {verified}  ⚠️ Suspicious: {suspicious}\n"
            f"❌ Fabricated: {fabricated}  ℹ️ Unable: {unable}"
        )
        summary_label = QLabel(summary)
        summary_label.setStyleSheet("padding: 8px; background: #f5f5f5; border-radius: 4px;")
        layout.addWidget(summary_label)

        # Format selection
        format_row = QHBoxLayout()
        format_label = QLabel("Format:")
        format_label.setMinimumWidth(60)

        self._format_combo = QComboBox()
        for display, _ in _FORMAT_OPTIONS:
            self._format_combo.addItem(display)

        format_row.addWidget(format_label)
        format_row.addWidget(self._format_combo, stretch=1)
        layout.addLayout(format_row)

        # File path
        path_row = QHBoxLayout()
        path_label = QLabel("Save to:")
        path_label.setMinimumWidth(60)

        self._path_field = QLineEdit()
        self._path_field.setPlaceholderText("Choose save location…")
        self._path_field.textChanged.connect(self._update_extension)

        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse)

        path_row.addWidget(path_label)
        path_row.addWidget(self._path_field, stretch=1)
        path_row.addWidget(browse_btn)
        layout.addLayout(path_row)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        export_btn = QPushButton("Export")
        export_btn.setDefault(True)
        export_btn.clicked.connect(self._do_export)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        btn_row.addWidget(export_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _browse(self) -> None:
        """Open file save dialog."""
        idx = self._format_combo.currentIndex()
        _, fmt = _FORMAT_OPTIONS[idx]

        filters = {
            "csv": "CSV Files (*.csv)",
            "xlsx": "Excel Files (*.xlsx)",
            "bib": "BibTeX Files (*.bib)",
        }

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Results",
            f"verification_results.{fmt}",
            filters.get(fmt, "All Files (*)"),
        )
        if path:
            self._path_field.setText(path)

    def _update_extension(self) -> None:
        """Ensure file path extension matches selected format."""
        pass  # Extension is set via browse dialog

    def _do_export(self) -> None:
        """Execute the export."""
        path_str = self._path_field.text().strip()
        if not path_str:
            QMessageBox.warning(self, "No Path", "Please choose a save location.")
            return

        path = Path(path_str)
        idx = self._format_combo.currentIndex()
        _, fmt = _FORMAT_OPTIONS[idx]

        try:
            if fmt == "csv":
                export_csv_to_file(self._results, path)
            elif fmt == "xlsx":
                export_excel(self._results, path)
            elif fmt == "bib":
                export_bibtex_to_file(self._results, path)
            else:
                QMessageBox.critical(self, "Error", f"Unknown format: {fmt}")
                return

            QMessageBox.information(
                self,
                "Export Complete",
                f"Results exported to:\n{path}",
            )
            self.accept()

        except Exception as exc:
            logger.error("export_error", error=str(exc))
            QMessageBox.critical(self, "Export Error", f"Failed to export:\n{exc}")
