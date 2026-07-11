from __future__ import annotations

from PySide6.QtWidgets import QListWidget, QListWidgetItem, QMainWindow, QSplitter, QStackedWidget

from app.gui.theme import DARK_QSS, LIGHT_QSS
from app.gui.views.dashboard import DashboardView
from app.gui.views.document_explorer import DocumentExplorerView
from app.gui.views.logs_view import LogsView
from app.gui.views.search_view import SearchView
from app.gui.views.settings_view import SettingsView
from app.gui.views.workflow_manager import WorkflowManagerView


class MainWindow(QMainWindow):
    NAV_ITEMS = [
        "Dashboard",
        "Document Explorer",
        "Workflow Manager",
        "Search",
        "Logs",
        "Settings",
    ]

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Office Automation Platform")
        self.resize(1280, 800)

        splitter = QSplitter()
        self.setCentralWidget(splitter)

        self.nav_list = QListWidget()
        for name in self.NAV_ITEMS:
            QListWidgetItem(name, self.nav_list)
        self.nav_list.setFixedWidth(220)
        self.nav_list.currentRowChanged.connect(self._on_nav_changed)
        splitter.addWidget(self.nav_list)

        self.stack = QStackedWidget()
        self.dashboard_view = DashboardView()
        self.document_explorer_view = DocumentExplorerView()
        self.workflow_manager_view = WorkflowManagerView()
        self.search_view = SearchView()
        self.logs_view = LogsView()
        self.settings_view = SettingsView(on_theme_change=self.apply_theme)

        for view in (
            self.dashboard_view,
            self.document_explorer_view,
            self.workflow_manager_view,
            self.search_view,
            self.logs_view,
            self.settings_view,
        ):
            self.stack.addWidget(view)
        splitter.addWidget(self.stack)
        splitter.setStretchFactor(1, 1)

        self.nav_list.setCurrentRow(0)
        self.apply_theme("light")

    def _on_nav_changed(self, index: int) -> None:
        self.stack.setCurrentIndex(index)

    def apply_theme(self, mode: str) -> None:
        self.setStyleSheet(DARK_QSS if mode == "dark" else LIGHT_QSS)
