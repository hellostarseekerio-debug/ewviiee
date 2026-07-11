from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget

from app.core.config import get_settings
from app.core.logging_config import export_logs


class LogsView(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        heading = QLabel("Logs")
        heading.setStyleSheet("font-size: 20px; font-weight: 700;")
        layout.addWidget(heading)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view)

        button_row = QHBoxLayout()
        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh)
        export_button = QPushButton("Export Logs…")
        export_button.clicked.connect(self.export)
        button_row.addWidget(refresh_button)
        button_row.addWidget(export_button)
        button_row.addStretch()
        layout.addLayout(button_row)

        self.refresh()

    def refresh(self) -> None:
        settings = get_settings()
        log_path = settings.data_dir / "logs" / "application.log"
        if log_path.exists():
            self.log_view.setPlainText(log_path.read_text(encoding="utf-8", errors="replace")[-20000:])
        else:
            self.log_view.setPlainText("No logs yet.")

    def export(self) -> None:
        destination, _ = QFileDialog.getSaveFileName(self, "Export logs", "logs_export.txt")
        if destination:
            export_logs(destination=Path(destination))
