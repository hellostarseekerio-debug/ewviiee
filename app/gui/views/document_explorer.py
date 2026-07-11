from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.config import get_settings
from app.core.database import session_scope
from app.core.file_safety import UnsafeFileError
from app.core.models import UserRole
from app.core.security import role_rank
from app.plugins.manager import PluginManager
from app.workflow.engine import WorkflowEngine
from app.workflow.loader import load_all_workflow_definitions
from app.workflow.runner import allowed_import_roots, run_document_through_workflow


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

    def __init__(self, current_user) -> None:
        super().__init__()
        self._current_user = current_user
        self._plugin_manager: PluginManager | None = None

        layout = QVBoxLayout(self)

        heading = QLabel("Document Explorer")
        heading.setStyleSheet("font-size: 20px; font-weight: 700;")
        layout.addWidget(heading)

        layout.addWidget(QLabel("Drag & drop files/folders below, or use Browse:"))
        self.drop_zone = DropZone()
        layout.addWidget(self.drop_zone)

        button_row = QHBoxLayout()
        self.workflow_combo = QComboBox()
        self.browse_button = QPushButton("Browse…")
        self.process_button = QPushButton("Process Batch")
        self.browse_button.clicked.connect(self._browse)
        self.process_button.clicked.connect(self._process_batch)
        button_row.addWidget(QLabel("Workflow:"))
        button_row.addWidget(self.workflow_combo)
        button_row.addWidget(self.browse_button)
        button_row.addWidget(self.process_button)
        button_row.addStretch()
        layout.addLayout(button_row)

        can_process = role_rank(current_user.role) >= role_rank(UserRole.EDITOR)
        self.process_button.setEnabled(can_process)
        if not can_process:
            self.process_button.setToolTip("Editor role or above required to run workflows")

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Filename", "District", "Estate", "Status", "Confidence"]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        self._load_workflows()

    def _load_workflows(self) -> None:
        settings = get_settings()
        definitions = load_all_workflow_definitions(settings.config_dir / "workflows")
        self.workflow_combo.clear()
        self.workflow_combo.addItems(list(definitions.keys()))

    def _browse(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Select documents to import")
        for path in paths:
            self.drop_zone.addItem(path)

    def _get_plugin_manager(self) -> PluginManager:
        if self._plugin_manager is None:
            self._plugin_manager = PluginManager()
            self._plugin_manager.discover_and_load()
        return self._plugin_manager

    def _process_batch(self) -> None:
        workflow_name = self.workflow_combo.currentText()
        if not workflow_name:
            QMessageBox.warning(self, "No workflow", "No workflow selected.")
            return

        paths = [self.drop_zone.item(i).text() for i in range(self.drop_zone.count())]
        if not paths:
            QMessageBox.information(self, "Nothing to process", "Add files first.")
            return

        settings = get_settings()
        definitions = load_all_workflow_definitions(settings.config_dir / "workflows")
        definition = definitions.get(workflow_name)
        if definition is None:
            QMessageBox.critical(self, "Unknown workflow", f"'{workflow_name}' is not configured.")
            return

        manager = self._get_plugin_manager()
        engine = WorkflowEngine(plugin_registry={p.plugin_id: p for p in manager.list_plugins()})
        roots = allowed_import_roots(settings)

        self.table.setRowCount(0)
        total = len(paths)
        for index, path_str in enumerate(paths, start=1):
            try:
                with session_scope() as session:
                    result = run_document_through_workflow(
                        db=session,
                        engine=engine,
                        definition=definition,
                        document_path=Path(path_str),
                        allowed_roots=roots,
                        triggered_by=self._current_user.username,
                    )
                status = "Success" if result.success else f"Failed: {result.halt_reason}"
                self.add_result_row(
                    Path(path_str).name,
                    str(result.fields.get("district") or ""),
                    str(result.fields.get("estate") or ""),
                    status,
                    str(result.fields.get("ai_confidence", "-")),
                )
            except UnsafeFileError as exc:
                self.add_result_row(Path(path_str).name, "", "", f"Rejected: {exc}", "-")
            self.set_progress(int(index / total * 100))

        self.drop_zone.clear()

    def set_progress(self, percent: int) -> None:
        self.progress_bar.setValue(percent)

    def add_result_row(self, filename: str, district: str, estate: str, status: str, confidence: str) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        for col, value in enumerate([filename, district, estate, status, confidence]):
            self.table.setItem(row, col, QTableWidgetItem(value))
