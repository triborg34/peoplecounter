"""Login dialog with role handling and forced password change."""
from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from ..db.models import User
from ..services import auth as auth_service

log = logging.getLogger(__name__)


class LoginDialog(QDialog):
    """Username / password login. On success the user attribute holds the account."""

    def __init__(self, runtime, parent=None):
        super().__init__(parent)
        self.runtime = runtime
        self.user: Optional[User] = None
        self.setWindowTitle("People Counter - Sign in")
        self.setFixedWidth(380)

        layout = QVBoxLayout(self)
        title = QLabel("People Counter")
        title.setObjectName("HeaderTitle")
        subtitle = QLabel("Sign in to continue")
        subtitle.setObjectName("Muted")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(8)

        form = QFormLayout()
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("username")
        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText("password")
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("User", self.username_edit)
        form.addRow("Password", self.password_edit)
        layout.addLayout(form)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #ef4444;")
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        self.login_button = QPushButton("Sign in")
        self.login_button.setObjectName("PrimaryButton")
        self.login_button.setDefault(True)
        self.login_button.clicked.connect(self._attempt_login)
        buttons.addWidget(cancel)
        buttons.addWidget(self.login_button)
        layout.addLayout(buttons)

        self.username_edit.textChanged.connect(lambda _: self.error_label.setText(""))
        self.password_edit.returnPressed.connect(self._attempt_login)
        self.username_edit.setFocus()

    def _attempt_login(self) -> None:
        username = self.username_edit.text().strip()
        password = self.password_edit.text()
        if not username or not password:
            self.error_label.setText("Please enter a username and a password.")
            return
        with self.runtime.db.session_scope() as session:
            user = session.query(User).filter(User.username == username).first()
            if user is None or not auth_service.verify_password(password, user.password_hash):
                self.error_label.setText("Invalid username or password.")
                return
            if not user.is_active:
                self.error_label.setText("This account is deactivated.")
                return
            from ..db.models import utcnow

            user.last_login_at = utcnow()
            session.flush()
            user_id = user.id
            resolved_username = user.username
            role = user.role
            must_change = user.must_change_password

        self.user = User(
            id=user_id, username=resolved_username, role=role, must_change_password=must_change
        )

        if must_change:
            from .settings_page import ChangePasswordDialog

            accepted = ChangePasswordDialog(self.runtime, self.user, require_change=True).exec()
            if accepted != QDialog.DialogCode.Accepted:
                self.error_label.setText("You must change the password before continuing.")
                self.password_edit.clear()
                return
        self.accept()
