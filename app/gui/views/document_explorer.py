from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class DropZone(QListWidget):
    """Drag & drop target for importing documents/folders."""

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setMinimumHeight(120)

    def dragEnterEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802 (Qt override)
        for url in event.mimeData().urls():
            self.addItem(url.toLocalFile())
        event.acceptProposedAction()


class DocumentExplorerView(QWidget):
    """Batch import queue + document table + processing progress bar."""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)

        heading = QLabel("Document Explorer")
        heading.setStyleSheet("font-size: 20px; font-weight: 700;")
        layout.addWidget(heading)

        layout.addWidget(QLabel("Drag & drop files/folders below, or use Browse:"))
        self.drop_zone = DropZone()
        layout.addWidget(self.drop_zone)

        button_row = QHBoxLayout()
        self.browse_button = QPushButton("Browse…")
        self.process_button = QPushButton("Process Batch")
        self.browse_button.clicked.connect(self._browse)
        button_row.addWidget(self.browse_button)
        button_row.addWidget(self.process_button)
        button_row.addStretch()
        layout.addLayout(button_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Filename", "District", "Estate", "Status", "Confidence"]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

    def _browse(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Select documents to import")
        for path in paths:
            self.drop_zone.addItem(path)

    def set_progress(self, percent: int) -> None:
        self.progress_bar.setValue(percent)

    def add_result_row(self, filename: str, district: str, estate: str, status: str, confidence: str) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        for col, value in enumerate([filename, district, estate, status, confidence]):
            self.table.setItem(row, col, QTableWidgetItem(value))
