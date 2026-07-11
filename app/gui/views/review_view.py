"""Review screen: lists documents awaiting approval, shows AI/OCR confidence,
and lets a Reviewer (or above) approve or reject each one. Rejecting keeps
the document and its generated output in place (nothing is deleted) but
flags it so it is excluded from any "ready to export" report until
re-processed.
"""
from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.database import session_scope
from app.core.logging_config import record_audit
from app.core.models import ApprovalStatus, Document, UserRole
from app.core.security import role_rank


class ReviewView(QWidget):
    def __init__(self, current_user) -> None:
        super().__init__()
        self._current_user = current_user
        self._document_ids: list[str] = []

        layout = QVBoxLayout(self)
        heading = QLabel("Review Queue")
        heading.setStyleSheet("font-size: 20px; font-weight: 700;")
        layout.addWidget(heading)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Filename", "District", "Estate", "AI Confidence", "OCR Confidence", "Status"]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.table)

        self.notes_input = QPlainTextEdit()
        self.notes_input.setPlaceholderText("Review notes (optional)")
        self.notes_input.setFixedHeight(60)
        layout.addWidget(self.notes_input)

        button_row = QHBoxLayout()
        self.approve_button = QPushButton("Approve")
        self.reject_button = QPushButton("Reject")
        self.refresh_button = QPushButton("Refresh")
        self.approve_button.clicked.connect(lambda: self._decide(ApprovalStatus.APPROVED))
        self.reject_button.clicked.connect(lambda: self._decide(ApprovalStatus.REJECTED))
        self.refresh_button.clicked.connect(self.refresh)
        button_row.addWidget(self.approve_button)
        button_row.addWidget(self.reject_button)
        button_row.addWidget(self.refresh_button)
        button_row.addStretch()
        layout.addLayout(button_row)

        can_review = role_rank(current_user.role) >= role_rank(UserRole.REVIEWER)
        self.approve_button.setEnabled(can_review)
        self.reject_button.setEnabled(can_review)
        if not can_review:
            self.notes_input.setPlaceholderText("Reviewer role or above required to approve/reject")

        self.refresh()

    def refresh(self) -> None:
        self.table.setRowCount(0)
        self._document_ids = []
        with session_scope() as session:
            pending = (
                session.query(Document)
                .filter(Document.approval_status == ApprovalStatus.PENDING, Document.is_deleted.is_(False))
                .order_by(Document.created_at.desc())
                .limit(200)
                .all()
            )
            for document in pending:
                row = self.table.rowCount()
                self.table.insertRow(row)
                values = [
                    document.filename,
                    document.district or "",
                    document.estate or "",
                    f"{document.ai_confidence:.2f}" if document.ai_confidence is not None else "-",
                    f"{document.ocr_confidence:.2f}" if document.ocr_confidence is not None else "-",
                    document.approval_status.value,
                ]
                for col, value in enumerate(values):
                    self.table.setItem(row, col, QTableWidgetItem(value))
                self._document_ids.append(document.id)

    def _on_selection_changed(self) -> None:
        pass

    def _decide(self, decision: ApprovalStatus) -> None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._document_ids):
            QMessageBox.information(self, "No selection", "Select a document to review first.")
            return
        document_id = self._document_ids[row]
        notes = self.notes_input.toPlainText().strip() or None

        with session_scope() as session:
            document = session.get(Document, document_id)
            if document is None:
                return
            document.approval_status = decision
            document.reviewed_by = self._current_user.username
            document.reviewed_at = datetime.utcnow()
            document.review_notes = notes

        record_audit(
            actor=self._current_user.username,
            action=f"document_{decision.value}",
            resource_type="document",
            resource_id=document_id,
            detail={"notes": notes},
        )
        self.refresh()
