"""Dark/light stylesheets for the desktop shell."""
from __future__ import annotations

LIGHT_QSS = """
QMainWindow, QWidget { background-color: #f5f6f8; color: #1c1e21; }
QListWidget, QTreeWidget, QTableWidget { background-color: #ffffff; border: 1px solid #d9dce0; }
QPushButton { background-color: #2f6fed; color: white; border-radius: 6px; padding: 6px 14px; }
QPushButton:hover { background-color: #2559c7; }
QLineEdit, QComboBox { background-color: #ffffff; border: 1px solid #d9dce0; border-radius: 4px; padding: 4px; }
QProgressBar { border: 1px solid #d9dce0; border-radius: 4px; text-align: center; }
QProgressBar::chunk { background-color: #2f6fed; }
"""

DARK_QSS = """
QMainWindow, QWidget { background-color: #1e2126; color: #e8e9ec; }
QListWidget, QTreeWidget, QTableWidget { background-color: #262a30; border: 1px solid #3a3f46; }
QPushButton { background-color: #3f7bff; color: white; border-radius: 6px; padding: 6px 14px; }
QPushButton:hover { background-color: #5a8dff; }
QLineEdit, QComboBox { background-color: #262a30; border: 1px solid #3a3f46; border-radius: 4px; padding: 4px; color: #e8e9ec; }
QProgressBar { border: 1px solid #3a3f46; border-radius: 4px; text-align: center; color: #e8e9ec; }
QProgressBar::chunk { background-color: #3f7bff; }
"""
