from __future__ import annotations

from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.database import session_scope
from app.search.query import SearchFilters, search_documents


class SearchView(QWidget):
    """Multi-field document search (estate, district, workflow, keyword, OCR
    text, politician, reference number, filename, date range)."""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        heading = QLabel("Search")
        heading.setStyleSheet("font-size: 20px; font-weight: 700;")
        layout.addWidget(heading)

        form = QGridLayout()
        self.estate_input = QLineEdit()
        self.district_input = QLineEdit()
        self.keyword_input = QLineEdit()
        self.politician_input = QLineEdit()
        self.reference_input = QLineEdit()
        self.filename_input = QLineEdit()

        fields = [
            ("Estate", self.estate_input),
            ("District", self.district_input),
            ("Keyword", self.keyword_input),
            ("Politician", self.politician_input),
            ("Reference #", self.reference_input),
            ("Filename", self.filename_input),
        ]
        for i, (label, widget) in enumerate(fields):
            form.addWidget(QLabel(label), i // 2, (i % 2) * 2)
            form.addWidget(widget, i // 2, (i % 2) * 2 + 1)
        layout.addLayout(form)

        search_button = QPushButton("Search")
        search_button.clicked.connect(self.run_search)
        layout.addWidget(search_button)

        self.results_table = QTableWidget(0, 5)
        self.results_table.setHorizontalHeaderLabels(
            ["Filename", "District", "Estate", "Politician", "Status"]
        )
        self.results_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.results_table)

    def run_search(self) -> None:
        filters = SearchFilters(
            estate=self.estate_input.text() or None,
            district=self.district_input.text() or None,
            keyword=self.keyword_input.text() or None,
            politician=self.politician_input.text() or None,
            reference_number=self.reference_input.text() or None,
            filename=self.filename_input.text() or None,
        )
        with session_scope() as session:
            results, _total = search_documents(session, filters)
            self.results_table.setRowCount(0)
            for document in results:
                row = self.results_table.rowCount()
                self.results_table.insertRow(row)
                values = [
                    document.filename,
                    document.district or "",
                    document.estate or "",
                    document.politician or "",
                    document.status.value if document.status else "",
                ]
                for col, value in enumerate(values):
                    self.results_table.setItem(row, col, QTableWidgetItem(value))
