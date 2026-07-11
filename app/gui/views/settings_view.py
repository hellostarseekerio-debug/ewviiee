from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ai.factory import is_cloud_provider
from app.core.config import get_settings
from app.core.database import session_scope
from app.core.logging_config import record_audit
from app.core.mfa import generate_enrollment, hash_recovery_codes, verify_totp_code
from app.core.models import User, UserRole
from app.core.security import EncryptionKeyMissingError, SecretBox, role_rank, verify_password
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

        security_heading = QLabel("Security")
        security_heading.setStyleSheet("font-size: 16px; font-weight: 700; margin-top: 12px;")
        layout.addWidget(security_heading)

        with session_scope() as session:
            fresh_user = session.get(User, current_user.id)
            mfa_enabled = bool(fresh_user and fresh_user.mfa_enabled)

        self.mfa_status_label = QLabel(
            "Two-factor authentication: " + ("enabled" if mfa_enabled else "disabled")
        )
        layout.addWidget(self.mfa_status_label)

        mfa_button_row = QHBoxLayout()
        self.enable_mfa_button = QPushButton("Enable Two-Factor Authentication")
        self.disable_mfa_button = QPushButton("Disable Two-Factor Authentication")
        self.enable_mfa_button.setEnabled(not mfa_enabled)
        self.disable_mfa_button.setEnabled(mfa_enabled)
        self.enable_mfa_button.clicked.connect(self._enable_mfa)
        self.disable_mfa_button.clicked.connect(self._disable_mfa)
        mfa_button_row.addWidget(self.enable_mfa_button)
        mfa_button_row.addWidget(self.disable_mfa_button)
        mfa_button_row.addStretch()
        layout.addLayout(mfa_button_row)

        layout.addStretch()

    def _enable_mfa(self) -> None:
        try:
            box = SecretBox()
        except EncryptionKeyMissingError:
            QMessageBox.critical(
                self, "Cannot enable MFA",
                "The server administrator has not configured OAP_ENCRYPTION_KEY yet. "
                "This must be set before two-factor authentication can be used - see docs/SECURITY.md.",
            )
            return

        enrollment = generate_enrollment(self._current_user.username)

        QMessageBox.information(
            self, "Set up your authenticator app",
            "Scan or manually enter this into your authenticator app "
            f"(e.g. Google Authenticator, Authy):\n\n{enrollment.otpauth_uri}\n\n"
            f"Manual entry secret: {enrollment.secret}\n\n"
            "Save these one-time recovery codes somewhere safe - each can be used "
            "once if you lose access to your authenticator app:\n\n"
            + "\n".join(enrollment.recovery_codes),
        )

        code, ok = QInputDialog.getText(self, "Confirm setup", "Enter the 6-digit code to confirm:")
        if not ok or not code.strip():
            return
        if not verify_totp_code(enrollment.secret, code.strip()):
            QMessageBox.critical(self, "Incorrect code", "That code did not match - MFA was not enabled.")
            return

        with session_scope() as session:
            user = session.get(User, self._current_user.id)
            user.mfa_secret_encrypted = box.encrypt(enrollment.secret)
            user.mfa_recovery_codes = hash_recovery_codes(enrollment.recovery_codes)
            user.mfa_enabled = True
        record_audit(actor=self._current_user.username, action="mfa_enabled")

        self.mfa_status_label.setText("Two-factor authentication: enabled")
        self.enable_mfa_button.setEnabled(False)
        self.disable_mfa_button.setEnabled(True)
        QMessageBox.information(self, "Enabled", "Two-factor authentication is now required at sign-in.")

    def _disable_mfa(self) -> None:
        password, ok = QInputDialog.getText(
            self, "Confirm your password", "Password:", QLineEdit.Password
        )
        if not ok:
            return

        with session_scope() as session:
            user = session.get(User, self._current_user.id)
            if not verify_password(password, user.hashed_password):
                QMessageBox.critical(self, "Incorrect password", "Two-factor authentication was not disabled.")
                return
            user.mfa_enabled = False
            user.mfa_secret_encrypted = None
            user.mfa_pending_secret_encrypted = None
            user.mfa_recovery_codes = None
        record_audit(actor=self._current_user.username, action="mfa_disabled")

        self.mfa_status_label.setText("Two-factor authentication: disabled")
        self.enable_mfa_button.setEnabled(True)
        self.disable_mfa_button.setEnabled(False)

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
