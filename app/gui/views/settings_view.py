from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QFormLayout, QLabel, QVBoxLayout, QWidget

from app.core.config import AIProviderName, get_settings


class SettingsView(QWidget):
    """AI provider switch, OCR engine preference, theme toggle - all backed
    by the same Settings object the backend/CLI use."""

    def __init__(self, on_theme_change=None) -> None:
        super().__init__()
        self._on_theme_change = on_theme_change
        layout = QVBoxLayout(self)
        heading = QLabel("Settings")
        heading.setStyleSheet("font-size: 20px; font-weight: 700;")
        layout.addWidget(heading)

        form = QFormLayout()

        self.ai_provider_combo = QComboBox()
        self.ai_provider_combo.addItems([p.value for p in AIProviderName])
        settings = get_settings()
        self.ai_provider_combo.setCurrentText(settings.ai_provider.value)
        form.addRow("AI Provider", self.ai_provider_combo)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Light", "Dark"])
        self.theme_combo.currentTextChanged.connect(self._theme_changed)
        form.addRow("Theme", self.theme_combo)

        layout.addLayout(form)

        note = QLabel(
            "Changing the AI provider here updates this session only.\n"
            "To persist it, set OAP_AI_PROVIDER in your .env file."
        )
        note.setStyleSheet("color: #888;")
        layout.addWidget(note)
        layout.addStretch()

    def _theme_changed(self, value: str) -> None:
        if self._on_theme_change:
            self._on_theme_change(value.lower())
