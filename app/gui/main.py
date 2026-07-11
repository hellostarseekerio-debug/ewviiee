"""Desktop GUI entrypoint."""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from app.core.config import get_settings
from app.core.database import init_db
from app.core.logging_config import configure_logging
from app.gui.login_dialog import LoginDialog
from app.gui.main_window import MainWindow


def run() -> None:
    configure_logging()
    settings = get_settings()
    try:
        settings.assert_secure_for_production()
    except RuntimeError as exc:
        # Fail loudly rather than starting with an insecure configuration.
        app = QApplication(sys.argv)
        QMessageBox.critical(None, "Insecure configuration", str(exc))
        sys.exit(1)

    init_db()
    app = QApplication(sys.argv)
    app.setApplicationName("Office Automation Platform")

    login = LoginDialog()
    if login.exec() != LoginDialog.Accepted or login.authenticated_user is None:
        sys.exit(0)

    window = MainWindow(current_user=login.authenticated_user)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run()
