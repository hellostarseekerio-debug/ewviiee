"""Desktop login dialog.

The GUI is a full trust-boundary peer of the API - it reads/writes the same
database directly - so it must enforce the same authentication, account
lockout, and MFA rules rather than trusting whoever launched the process.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from app.core.database import session_scope
from app.core.mfa import verify_and_consume_recovery_code, verify_totp_code
from app.core.models import User
from app.core.security import (
    SecretBox,
    is_account_locked,
    register_failed_login,
    register_successful_login,
    verify_password,
)


class LoginDialog(QDialog):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Office Automation Platform - Sign in")
        self.setMinimumWidth(360)
        self.authenticated_user: User | None = None

        layout = QVBoxLayout(self)
        heading = QLabel("Office Automation Platform")
        heading.setStyleSheet("font-size: 18px; font-weight: 700;")
        layout.addWidget(heading)

        form = QFormLayout()
        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.returnPressed.connect(self._attempt_login)
        form.addRow("Username", self.username_input)
        form.addRow("Password", self.password_input)
        layout.addLayout(form)

        login_button = QPushButton("Sign in")
        login_button.clicked.connect(self._attempt_login)
        layout.addWidget(login_button)

    def _attempt_login(self) -> None:
        username = self.username_input.text().strip()
        password = self.password_input.text()

        with session_scope() as session:
            user = session.query(User).filter(User.username == username).first()

            if user and is_account_locked(user):
                QMessageBox.critical(
                    self, "Account locked",
                    "This account is temporarily locked due to repeated failed sign-in attempts.\n"
                    "Please wait 15 minutes and try again, or contact your administrator.",
                )
                return

            if not user or not user.is_active or not verify_password(password, user.hashed_password):
                if user:
                    register_failed_login(user)
                QMessageBox.critical(self, "Sign-in failed", "Incorrect username or password.")
                return

            if user.mfa_enabled and not self._verify_mfa(user):
                register_failed_login(user)
                return

            register_successful_login(user)
            # Detach a plain snapshot so it survives the session closing.
            self.authenticated_user = User(
                id=user.id, username=user.username, full_name=user.full_name,
                role=user.role, is_active=user.is_active,
            )

        self.accept()

    def _verify_mfa(self, user: User) -> bool:
        code, ok = QInputDialog.getText(
            self, "Two-factor authentication",
            "Enter the 6-digit code from your authenticator app\n(or a recovery code):",
        )
        if not ok or not code.strip():
            return False
        code = code.strip()

        if user.mfa_secret_encrypted:
            secret = SecretBox().decrypt(user.mfa_secret_encrypted)
            if verify_totp_code(secret, code):
                return True

        if user.mfa_recovery_codes:
            remaining = verify_and_consume_recovery_code(code, user.mfa_recovery_codes)
            if remaining is not None:
                user.mfa_recovery_codes = remaining
                return True

        QMessageBox.critical(self, "Sign-in failed", "Incorrect authentication code.")
        return False
