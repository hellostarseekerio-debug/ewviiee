"""Desktop GUI entrypoint."""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.core.database import init_db
from app.core.logging_config import configure_logging
from app.gui.main_window import MainWindow


def run() -> None:
    configure_logging()
    init_db()
    app = QApplication(sys.argv)
    app.setApplicationName("Office Automation Platform")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run()
