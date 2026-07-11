from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import QGridLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from app.core.config import get_settings
from app.core.database import session_scope
from app.core.models import ApprovalStatus, Document, DocumentStatus
from app.workflow.loader import load_all_workflow_definitions


class StatCard(QWidget):
    def __init__(self, title: str, value: str) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        self.value_label = QLabel(value)
        self.value_label.setStyleSheet("font-size: 28px; font-weight: 600;")
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #888;")
        layout.addWidget(self.value_label)
        layout.addWidget(title_label)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)


class DashboardView(QWidget):
    """Landing screen: quick stats pulled live from the database."""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        heading_row = QVBoxLayout()
        heading = QLabel("Dashboard")
        heading.setStyleSheet("font-size: 20px; font-weight: 700;")
        heading_row.addWidget(heading)
        layout.addLayout(heading_row)

        grid = QGridLayout()
        self.docs_card = StatCard("Documents Processed Today", "0")
        self.pending_card = StatCard("Pending Review", "0")
        self.failed_card = StatCard("Failed Validations", "0")
        self.workflows_card = StatCard("Active Workflows", "0")
        grid.addWidget(self.docs_card, 0, 0)
        grid.addWidget(self.pending_card, 0, 1)
        grid.addWidget(self.failed_card, 0, 2)
        grid.addWidget(self.workflows_card, 0, 3)
        layout.addLayout(grid)

        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh)
        layout.addWidget(refresh_button)
        layout.addStretch()

        self.refresh()

    def refresh(self) -> None:
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        with session_scope() as session:
            processed_today = (
                session.query(Document)
                .filter(Document.created_at >= today_start, Document.is_deleted.is_(False))
                .count()
            )
            pending_review = (
                session.query(Document)
                .filter(Document.approval_status == ApprovalStatus.PENDING, Document.is_deleted.is_(False))
                .count()
            )
            failed = (
                session.query(Document)
                .filter(Document.status == DocumentStatus.FAILED, Document.is_deleted.is_(False))
                .count()
            )

        settings = get_settings()
        workflow_count = len(load_all_workflow_definitions(settings.config_dir / "workflows"))

        self.docs_card.set_value(str(processed_today))
        self.pending_card.set_value(str(pending_review))
        self.failed_card.set_value(str(failed))
        self.workflows_card.set_value(str(workflow_count))
