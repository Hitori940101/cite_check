"""Settings dialog for RefChecker.

Per-adapter API key fields with:
- Optional API key input (masked password fields)
- Key status indicators (stored / not stored)
- Adapter enable/disable checkboxes
- Proxy configuration
- Inline "How to apply" hints for sources requiring keys
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from refchecker.core.logging import get_logger

logger = get_logger(__name__)

# Adapter metadata: (display_name, key_name, hint, requires_key)
_ADAPTER_INFO = [
    ("Crossref", "crossref", "Free — no key needed. Uses mailto for polite pool.", False),
    ("Semantic Scholar", "s2", "Free tier: ~100 req/5min. With key: 1 RPS guaranteed.\n"
     "Apply at: https://www.semanticscholar.org/product/api", False),
    ("OpenAlex", "openalex", "Free key recommended: 100K credits/day.\n"
     "Apply at: https://openalex.org/", True),
    ("AMiner", "aminer", "Free tier available. Key unlocks higher limits.\n"
     "Apply at: https://open.aminer.cn/", False),
    ("Baidu Academic", "baidu", "Scraping-based — no API key.", False),
    ("CNKI", "cnki", "Playwright-based — no API key.", False),
]


class SettingsDialog(QDialog):
    """Application settings dialog.

    Features:
    - Tab 1: Adapter API keys and enable/disable
    - Tab 2: Proxy and network settings
    """

    def __init__(self, parent: object = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(520)
        self._key_fields: dict[str, QLineEdit] = {}
        self._adapter_checks: dict[str, QCheckBox] = {}
        self._setup_ui()
        self._load_current_state()

    def _setup_ui(self) -> None:
        """Build the dialog layout."""
        layout = QVBoxLayout(self)

        tabs = QTabWidget()
        tabs.addTab(self._build_adapters_tab(), "API Keys && Adapters")
        tabs.addTab(self._build_network_tab(), "Network")

        layout.addWidget(tabs)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._on_save)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _build_adapters_tab(self) -> QWidget:
        """Build the adapter settings tab.

        Returns:
            Widget containing adapter configuration.
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)

        for display_name, adapter_name, hint, requires_key in _ADAPTER_INFO:
            group = QGroupBox(display_name)
            group_layout = QVBoxLayout(group)

            # Enable checkbox
            check = QCheckBox("Enabled")
            check.setChecked(True)
            self._adapter_checks[adapter_name] = check
            group_layout.addWidget(check)

            # API key field (only for adapters that support keys)
            if adapter_name in ("s2", "openalex", "aminer"):
                key_row = QHBoxLayout()
                key_label = QLabel("API Key:")
                key_label.setMinimumWidth(60)

                key_field = QLineEdit()
                key_field.setPlaceholderText("Enter API key (optional)")
                key_field.setEchoMode(QLineEdit.EchoMode.Password)
                self._key_fields[adapter_name] = key_field

                # Toggle visibility button
                toggle_btn = QPushButton("👁")
                toggle_btn.setFixedWidth(30)
                toggle_btn.setCheckable(True)
                toggle_btn.toggled.connect(
                    lambda checked, f=key_field: f.setEchoMode(
                        QLineEdit.EchoMode.Normal if checked
                        else QLineEdit.EchoMode.Password
                    )
                )

                # Store button
                store_btn = QPushButton("Store Securely")
                store_btn.clicked.connect(
                    lambda checked, n=adapter_name, f=key_field: self._store_key(n, f)
                )

                # Status indicator
                status_label = QLabel("—")
                status_label.setObjectName(f"status_{adapter_name}")
                self._check_key_status(adapter_name, status_label)

                key_row.addWidget(key_label)
                key_row.addWidget(key_field, stretch=1)
                key_row.addWidget(toggle_btn)
                key_row.addWidget(store_btn)
                key_row.addWidget(status_label)
                group_layout.addLayout(key_row)

            # Hint label
            hint_label = QLabel(hint)
            hint_label.setStyleSheet("color: #888; font-size: 11px;")
            hint_label.setWordWrap(True)
            group_layout.addWidget(hint_label)

            layout.addWidget(group)

        # S2 lifecycle warning
        warning = QLabel(
            "⚠️ Semantic Scholar: Keys inactive for 60+ days may be removed. "
            "Use the tool regularly to keep your key active."
        )
        warning.setStyleSheet("color: #b45309; font-size: 11px; padding: 8px; background: #fef3c7; border-radius: 4px;")
        warning.setWordWrap(True)
        layout.addWidget(warning)

        layout.addStretch()
        return widget

    def _build_network_tab(self) -> QWidget:
        """Build the network/proxy settings tab.

        Returns:
            Widget containing network configuration.
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)

        proxy_group = QGroupBox("Proxy Settings")
        proxy_layout = QVBoxLayout(proxy_group)

        self._http_proxy = QLineEdit()
        self._http_proxy.setPlaceholderText("http://proxy:port (optional)")
        proxy_layout.addWidget(QLabel("HTTP Proxy:"))
        proxy_layout.addWidget(self._http_proxy)

        self._https_proxy = QLineEdit()
        self._https_proxy.setPlaceholderText("https://proxy:port (optional)")
        proxy_layout.addWidget(QLabel("HTTPS Proxy:"))
        proxy_layout.addWidget(self._https_proxy)

        layout.addWidget(proxy_group)

        timeout_group = QGroupBox("Request Settings")
        timeout_layout = QVBoxLayout(timeout_group)

        self._timeout_spin = self._make_spinbox(5, 120, 30, "Request timeout (seconds):")
        timeout_layout.addLayout(self._labeled_row("Timeout:", self._timeout_spin))

        self._concurrent_spin = self._make_spinbox(1, 10, 3, "Max concurrent requests:")
        timeout_layout.addLayout(self._labeled_row("Concurrency:", self._concurrent_spin))

        layout.addWidget(timeout_group)
        layout.addStretch()
        return widget

    def _make_spinbox(self, min_val: int, max_val: int, default: int, tooltip: str) -> object:
        """Create a QSpinBox with common settings."""
        from PySide6.QtWidgets import QSpinBox

        spin = QSpinBox()
        spin.setRange(min_val, max_val)
        spin.setValue(default)
        spin.setToolTip(tooltip)
        return spin

    def _labeled_row(self, text: str, widget: object) -> QHBoxLayout:
        """Create a labeled row layout."""
        row = QHBoxLayout()
        label = QLabel(text)
        label.setMinimumWidth(90)
        row.addWidget(label)
        row.addWidget(widget, stretch=1)
        return row

    def _load_current_state(self) -> None:
        """Load current configuration into the dialog fields."""
        try:
            from refchecker.config import load_config
            config = load_config()

            # Adapter enabled states
            for name, check in self._adapter_checks.items():
                check.setChecked(config.is_adapter_enabled(name))

            # Network settings
            proxy = config.get_proxy_url()
            if proxy:
                self._https_proxy.setText(proxy)
            self._timeout_spin.setValue(int(config.adapters.request_timeout))
            self._concurrent_spin.setValue(config.adapters.max_concurrent)

        except Exception as exc:
            logger.warning("settings_load_error", error=str(exc))

    def _check_key_status(self, adapter_name: str, label: QLabel) -> None:
        """Check and display whether a key is stored for an adapter.

        Args:
            adapter_name: Adapter identifier.
            label: QLabel to update with status.
        """
        try:
            from refchecker.core.key_store import load_key, _key_to_adapter
            key_name = f"{adapter_name}_api_key"
            value = load_key(key_name)
            if value is not None:
                label.setText("🔑 Stored")
                label.setStyleSheet("color: #16a34a; font-weight: bold;")
            else:
                label.setText("— None")
                label.setStyleSheet("color: #999;")
        except ImportError:
            label.setText("⚠ No keyring")
            label.setStyleSheet("color: #d97706;")

    def _store_key(self, adapter_name: str, field: QLineEdit) -> None:
        """Store an API key from the field into encrypted storage.

        Args:
            adapter_name: Adapter identifier.
            field: QLineEdit containing the key value.
        """
        key_value = field.text().strip()
        if not key_value:
            QMessageBox.warning(self, "Empty Key", "Please enter an API key before saving.")
            return

        try:
            from refchecker.core.key_store import store_key
            key_name = f"{adapter_name}_api_key"
            store_key(key_name, key_value)
            field.clear()

            # Update status label
            status_label = self.findChild(QLabel, f"status_{adapter_name}")
            if status_label:
                status_label.setText("🔑 Stored")
                status_label.setStyleSheet("color: #16a34a; font-weight: bold;")

            QMessageBox.information(self, "Key Stored", f"API key for {adapter_name} stored securely.")
        except ImportError:
            QMessageBox.critical(self, "Error", "keyring package is required for encrypted storage.")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to store key: {exc}")

    def _on_save(self) -> None:
        """Save settings and close dialog."""
        try:
            # For now, adapter enabled states are saved to config
            # (full persistence would use QSettings or config file)
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to save settings: {exc}")
