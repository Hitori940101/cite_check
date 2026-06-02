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
from refchecker.gui.i18n import t

logger = get_logger(__name__)


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
        self._format_extensions = ["csv", "xlsx", "bib"]
        self.setWindowTitle(t("export.dlg.title"))
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
            f"{t('export.dlg.summary_total', total=len(self._results))}\n"
            f"{t('export.dlg.summary_verified', count=verified)}  "
            f"{t('export.dlg.summary_suspicious', count=suspicious)}\n"
            f"{t('export.dlg.summary_fabricated', count=fabricated)}  "
            f"{t('export.dlg.summary_unable', count=unable)}"
        )
        summary_label = QLabel(summary)
        summary_label.setStyleSheet("padding: 8px; background: #f5f5f5; border-radius: 4px;")
        layout.addWidget(summary_label)

        # Format selection
        format_row = QHBoxLayout()
        format_label = QLabel(t("export.dlg.format_label"))
        format_label.setMinimumWidth(60)

        self._format_combo = QComboBox()
        self._format_combo.addItem(t("export.dlg.format_csv"))
        self._format_combo.addItem(t("export.dlg.format_xlsx"))
        self._format_combo.addItem(t("export.dlg.format_bib"))
        self._format_combo.currentIndexChanged.connect(self._update_extension)

        format_row.addWidget(format_label)
        format_row.addWidget(self._format_combo, stretch=1)
        layout.addLayout(format_row)

        # File path
        path_row = QHBoxLayout()
        path_label = QLabel(t("export.dlg.save_to"))
        path_label.setMinimumWidth(60)

        self._path_field = QLineEdit()
        self._path_field.setPlaceholderText(t("export.dlg.placeholder"))
        self._path_field.textChanged.connect(self._update_extension)

        browse_btn = QPushButton(t("export.dlg.browse"))
        browse_btn.clicked.connect(self._browse)

        path_row.addWidget(path_label)
        path_row.addWidget(self._path_field, stretch=1)
        path_row.addWidget(browse_btn)
        layout.addLayout(path_row)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        export_btn = QPushButton(t("export.dlg.save_btn"))
        export_btn.setDefault(True)
        export_btn.clicked.connect(self._do_export)

        cancel_btn = QPushButton(t("export.dlg.cancel_btn"))
        cancel_btn.clicked.connect(self.reject)

        btn_row.addWidget(export_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _browse(self) -> None:
        """Open file save dialog."""
        idx = self._format_combo.currentIndex()
        fmt = self._format_extensions[idx]

        filters = {
            "csv": t("export.dlg.filter_csv"),
            "xlsx": t("export.dlg.filter_xlsx"),
            "bib": t("export.dlg.filter_bib"),
        }

        path, _ = QFileDialog.getSaveFileName(
            self,
            t("export.dlg.save_title"),
            f"verification_results.{fmt}",
            filters.get(fmt, t("export.dlg.filter_all")),
        )
        if path:
            self._path_field.setText(path)

    def _update_extension(self) -> None:
        """Ensure file path extension matches selected format."""
        path_str = self._path_field.text().strip()
        if not path_str:
            return

        idx = self._format_combo.currentIndex()
        fmt = self._format_extensions[idx]
        ext_map = {0: ".csv", 1: ".xlsx", 2: ".bib"}
        target_ext = ext_map.get(idx, "")

        # Strip any known extension and add the correct one
        for e in (".csv", ".xlsx", ".bib"):
            if path_str.endswith(e):
                path_str = path_str[: -len(e)]
                break

        self._path_field.blockSignals(True)
        self._path_field.setText(path_str + target_ext)
        self._path_field.blockSignals(False)

    def _do_export(self) -> None:
        """Execute the export."""
        path_str = self._path_field.text().strip()
        if not path_str:
            QMessageBox.warning(
                self, t("export.dlg.no_path"), t("export.dlg.no_path_msg"),
            )
            return

        path = Path(path_str)
        idx = self._format_combo.currentIndex()
        fmt = self._format_extensions[idx]

        try:
            if fmt == "csv":
                export_csv_to_file(self._results, path)
            elif fmt == "xlsx":
                export_excel(self._results, path)
            elif fmt == "bib":
                export_bibtex_to_file(self._results, path)
            else:
                QMessageBox.critical(
                    self, t("export.dlg.error"), t("export.dlg.error_unknown", fmt=fmt),
                )
                return

            QMessageBox.information(
                self,
                t("export.dlg.complete"),
                t("export.dlg.complete_msg", path=path),
            )
            self.accept()

        except Exception as exc:
            logger.error("export_error", error=str(exc))
            QMessageBox.critical(
                self, t("export.dlg.export_error"), t("export.dlg.export_failed", exc=str(exc)),
            )
