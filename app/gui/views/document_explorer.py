from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal
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
from app.core.friendly_errors import humanize_error
from app.core.models import UserRole
from app.core.security import role_rank
from app.plugins.manager import PluginManager
from app.workflow.engine import WorkflowEngine
from app.workflow.loader import load_all_workflow_definitions
from app.workflow.models import WorkflowDefinition
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


class _BatchWorker(QObject):
    """Runs a batch of documents through a workflow off the UI thread.

    Processing thousands of documents (OCR, PDF generation, DB writes) can
    take minutes; doing that on the Qt main thread would freeze the entire
    window for the whole run, making the application look hung and
    tempting non-technical staff to force-quit mid-batch. This worker runs
    on a `QThread` instead and reports progress back via signals, which Qt
    safely marshals onto the UI thread."""

    row_ready = Signal(str, str, str, str, str)
    progress = Signal(int)
    finished = Signal()

    def __init__(
        self,
        paths: list[str],
        definition: WorkflowDefinition,
        engine: WorkflowEngine,
        roots: list[Path],
        triggered_by: str,
    ) -> None:
        super().__init__()
        self._paths = paths
        self._definition = definition
        self._engine = engine
        self._roots = roots
        self._triggered_by = triggered_by

    def run(self) -> None:
        # `finished` must be emitted no matter what happens below - if an
        # unexpected exception escaped this loop without it, the QThread
        # would never be told to quit, leaving the GUI stuck showing
        # "Processing..." forever and, worse, crashing the whole
        # application on close (Qt aborts the process if a QThread object
        # is destroyed while still running). Every failure mode for a
        # single document must become a row in the table, never a crash.
        try:
            total = len(self._paths) or 1
            for index, path_str in enumerate(self._paths, start=1):
                try:
                    with session_scope() as session:
                        result = run_document_through_workflow(
                            db=session,
                            engine=self._engine,
                            definition=self._definition,
                            document_path=Path(path_str),
                            allowed_roots=self._roots,
                            triggered_by=self._triggered_by,
                        )
                    status = "Success" if result.success else f"Failed: {result.halt_reason}"
                    self.row_ready.emit(
                        Path(path_str).name,
                        str(result.fields.get("district") or ""),
                        str(result.fields.get("estate") or ""),
                        status,
                        str(result.fields.get("ai_confidence", "-")),
                    )
                except UnsafeFileError as exc:
                    self.row_ready.emit(Path(path_str).name, "", "", f"Rejected: {exc}", "-")
                except Exception as exc:  # noqa: BLE001 - must never crash the batch or the thread
                    self.row_ready.emit(
                        Path(path_str).name, "", "", humanize_error(str(exc)), "-"
                    )
                self.progress.emit(int(index / total * 100))
        finally:
            self.finished.emit()


class DocumentExplorerView(QWidget):
    """Batch import queue + document table + processing progress bar."""

    def __init__(self, current_user) -> None:
        super().__init__()
        self._current_user = current_user
        self._plugin_manager: PluginManager | None = None
        self._thread: QThread | None = None
        self._worker: _BatchWorker | None = None

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

        self._can_process = role_rank(current_user.role) >= role_rank(UserRole.EDITOR)
        self.process_button.setEnabled(self._can_process)
        if not self._can_process:
            self.process_button.setToolTip("Editor role or above required to run workflows")

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #888;")
        layout.addWidget(self.status_label)

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
        if self._thread is not None:
            QMessageBox.information(self, "Already running", "A batch is already being processed.")
            return

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
        self.progress_bar.setValue(0)
        self.status_label.setText(f"Processing {len(paths)} document(s)…")
        self.process_button.setEnabled(False)
        self.browse_button.setEnabled(False)
        self.drop_zone.clear()

        self._thread = QThread(self)
        self._worker = _BatchWorker(paths, definition, engine, roots, self._current_user.username)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.row_ready.connect(self.add_result_row)
        self._worker.progress.connect(self.set_progress)
        # Order matters here and must not include a blocking wait(): the
        # worker's `finished` signal first updates the UI, then asks the
        # thread to quit. Cleanup of the QThread object itself happens on
        # QThread's own `finished` signal (fired once its event loop has
        # actually stopped) rather than by blocking the UI thread with
        # `thread.wait()` inside a slot - calling wait() here would deadlock,
        # since the `thread.quit()` request (connected after this slot)
        # would never be delivered while this slot is blocked waiting for
        # exactly that to happen.
        self._worker.finished.connect(self._on_batch_finished)
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup_thread)
        self._thread.start()

    def _on_batch_finished(self) -> None:
        self.status_label.setText(f"Done - {self.table.rowCount()} document(s) processed.")
        self.process_button.setEnabled(self._can_process)
        self.browse_button.setEnabled(True)

    def _cleanup_thread(self) -> None:
        self._thread = None
        self._worker = None

    def set_progress(self, percent: int) -> None:
        self.progress_bar.setValue(percent)

    def add_result_row(self, filename: str, district: str, estate: str, status: str, confidence: str) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        for col, value in enumerate([filename, district, estate, status, confidence]):
            self.table.setItem(row, col, QTableWidgetItem(value))
