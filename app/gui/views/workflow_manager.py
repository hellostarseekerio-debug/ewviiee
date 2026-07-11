from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QListWidget, QPushButton, QTextEdit, QVBoxLayout, QWidget

from app.core.config import get_settings
from app.workflow.loader import load_all_workflow_definitions


class WorkflowManagerView(QWidget):
    """Lists configured workflows (from config/workflows/*.yaml) and shows
    their stage pipeline. New workflows appear automatically - no code change
    needed, just add a YAML file."""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        heading = QLabel("Workflow Manager")
        heading.setStyleSheet("font-size: 20px; font-weight: 700;")
        layout.addWidget(heading)

        body = QHBoxLayout()
        self.workflow_list = QListWidget()
        self.workflow_list.currentTextChanged.connect(self._show_detail)
        body.addWidget(self.workflow_list, 1)

        self.detail_view = QTextEdit()
        self.detail_view.setReadOnly(True)
        body.addWidget(self.detail_view, 2)
        layout.addLayout(body)

        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.reload_workflows)
        layout.addWidget(refresh_button)

        self._definitions = {}
        self.reload_workflows()

    def reload_workflows(self) -> None:
        settings = get_settings()
        self._definitions = load_all_workflow_definitions(settings.config_dir / "workflows")
        self.workflow_list.clear()
        for name in self._definitions:
            self.workflow_list.addItem(name)

    def _show_detail(self, name: str) -> None:
        definition = self._definitions.get(name)
        if not definition:
            self.detail_view.setPlainText("")
            return
        stages_text = " → ".join(definition.stages)
        self.detail_view.setPlainText(
            f"{definition.display_name}\n\nPlugin: {definition.plugin}\n\n"
            f"Stages:\n{stages_text}\n\n{definition.description}"
        )
