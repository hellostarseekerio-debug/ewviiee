from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from app.ai.factory import is_cloud_provider
from app.core.config import get_settings
from app.core.database import session_scope
from app.core.logging_config import record_audit
from app.core.models import UserRole
from app.core.security import role_rank
from app.core.system_settings import ALLOW_CLOUD_AI, get_bool_setting, set_setting


class SettingsView(QWidget):
    """AI provider display, privacy controls (cloud-AI kill switch), and
    theme toggle. The cloud-AI switch is DB-backed (`system_settings`) and
    takes effect immediately, unlike the AI provider selection itself which
    is a `.env` value requiring a restart - the note below explains why."""

    def __init__(self, current_user, on_theme_change=None) -> None:
        super().__init__()
        self._current_user = current_user
        self._on_theme_change = on_theme_change
        layout = QVBoxLayout(self)
        heading = QLabel("Settings")
        heading.setStyleSheet("font-size: 20px; font-weight: 700;")
        layout.addWidget(heading)

        form = QFormLayout()

        settings = get_settings()
        provider_label = QLabel(settings.ai_provider.value)
        cloud = is_cloud_provider(settings.ai_provider)
        provider_label.setText(
            f"{settings.ai_provider.value} ({'cloud - external' if cloud else 'local - private'})"
        )
        form.addRow("AI Provider (set via OAP_AI_PROVIDER in .env)", provider_label)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Light", "Dark"])
        self.theme_combo.currentTextChanged.connect(self._theme_changed)
        form.addRow("Theme", self.theme_combo)

        layout.addLayout(form)

        privacy_heading = QLabel("Privacy")
        privacy_heading.setStyleSheet("font-size: 16px; font-weight: 700; margin-top: 12px;")
        layout.addWidget(privacy_heading)

        self.cloud_ai_checkbox = QCheckBox(
            "Allow cloud AI providers (OpenAI / Anthropic / Azure OpenAI)"
        )
        with session_scope() as session:
            self.cloud_ai_checkbox.setChecked(get_bool_setting(session, ALLOW_CLOUD_AI))
        self.cloud_ai_checkbox.stateChanged.connect(self._toggle_cloud_ai)

        is_admin = role_rank(current_user.role) >= role_rank(UserRole.ADMIN)
        self.cloud_ai_checkbox.setEnabled(is_admin)
        layout.addWidget(self.cloud_ai_checkbox)

        note = QLabel(
            "When disabled (the default), only the local AI provider is used and no "
            "document text ever leaves this machine. Only an Administrator can enable "
            "cloud AI providers. Every AI call is logged (provider, operation, timing) "
            "without storing document content - see the Logs screen and docs/PRIVACY.md."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #888;")
        layout.addWidget(note)
        layout.addStretch()

    def _theme_changed(self, value: str) -> None:
        if self._on_theme_change:
            self._on_theme_change(value.lower())

    def _toggle_cloud_ai(self, _state: int) -> None:
        enabled = self.cloud_ai_checkbox.isChecked()
        with session_scope() as session:
            set_setting(session, ALLOW_CLOUD_AI, "true" if enabled else "false", updated_by=self._current_user.username)
        record_audit(
            actor=self._current_user.username,
            action="cloud_ai_setting_changed",
            detail={"allow_cloud_ai": enabled},
        )
        if enabled:
            QMessageBox.warning(
                self, "Cloud AI enabled",
                "Cloud AI providers are now allowed. Document text may be sent to a "
                "third-party API when the rule engine cannot resolve a field. Make sure "
                "this is consistent with office policy before processing sensitive documents.",
            )
