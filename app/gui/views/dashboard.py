from __future__ import annotations

from PySide6.QtWidgets import QGridLayout, QLabel, QVBoxLayout, QWidget


class StatCard(QWidget):
    def __init__(self, title: str, value: str) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        value_label = QLabel(value)
        value_label.setStyleSheet("font-size: 28px; font-weight: 600;")
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #888;")
        layout.addWidget(value_label)
        layout.addWidget(title_label)


class DashboardView(QWidget):
    """Landing screen: quick stats + recent activity, refreshed from the DB."""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        heading = QLabel("Dashboard")
        heading.setStyleSheet("font-size: 20px; font-weight: 700;")
        layout.addWidget(heading)

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
        layout.addStretch()

    def refresh(self, stats: dict[str, int]) -> None:
        self.docs_card.findChildren(type(self.docs_card))  # no-op placeholder for future live refresh
