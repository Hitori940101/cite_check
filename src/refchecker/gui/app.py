"""QApplication entry point for RefChecker GUI.

Usage:
    python -m refchecker.gui
"""

import sys

from PySide6.QtWidgets import QApplication

from refchecker.core.logging import configure_logging


def run_gui() -> int:
    """Create and run the RefChecker GUI application.

    Returns:
        Exit code from the Qt event loop.
    """
    configure_logging(level="INFO")

    app = QApplication(sys.argv)
    app.setApplicationName("RefChecker")
    app.setApplicationVersion("0.1.0")
    app.setOrganizationName("DeepScientist")

    # Apply a clean style
    app.setStyle("Fusion")

    from refchecker.gui.main_window import MainWindow

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(run_gui())
