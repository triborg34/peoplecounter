"""Users page (admin only): user management and the audit log."""
from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QComboBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..db.models import AuditLog, User
from ..services import auth as auth_service

log = logging.getLogger(__name__)


class UserDialog(QDialog):
    """Create or edit a user account."""

    def __init__(self, runtime, user=None, parent=None):
        super().__init__(parent)
        self.runtime = runtime
        self.user = user
        self.setWindowTitle("Edit user" if user else "Add user")
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.username_edit = QLineEdit()
        if user is not None:
            self.username_edit.setText(user.username)
            self.username_edit.setEnabled(False)
        self.full_name_edit = QLineEdit()
        self.email_edit = QLineEdit()
        self.role_combo = QComboBox()
        for role in ("admin", "operator", "viewer"):
            self.role_combo.addItem(role, role)
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText("at least 8 characters")
        form.addRow("Username", self.username_edit)
        form.addRow("Full name", self.full_name_edit)
        form.addRow("Email", self.email_edit)
        form.addRow("Role", self.role_combo)
        form.addRow("Password", self.password_edit)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save")
        save.setObjectName("PrimaryButton")
        save.clicked.connect(self._validate)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        layout.addLayout(buttons)

        if user is not None:
            self.full_name_edit.setText(user.full_name or "")
            self.email_edit.setText(user.email or "")
            index = self.role_combo.findData(user.role)
            if index >= 0:
                self.role_combo.setCurrentIndex(index)

    def _validate(self) -> None:
        if self.user is None:
            if len(self.username_edit.text().strip()) < 3:
                QMessageBox.warning(self, "User", "The username needs at least 3 characters.")
                return
            error = auth_service.password_strength_error(self.password_edit.text())
            if error:
                QMessageBox.warning(self, "User", error)
                return
        self.accept()

    def values(self) -> dict:
        return {
            "username": self.username_edit.text().strip(),
            "full_name": self.full_name_edit.text().strip(),
            "email": self.email_edit.text().strip() or None,
            "role": self.role_combo.currentData(),
            "password": self.password_edit.text() or None,
        }


class UsersPage(QWidget):
    """Manage user accounts and review the audit log."""

    def __init__(self, runtime, user, parent=None):
        super().__init__(parent)
        self.runtime = runtime
        self.user = user

        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)

        users_tab = QWidget()
        users_layout = QVBoxLayout(users_tab)
        header = QHBoxLayout()
        header.addWidget(QLabel("Users"))
        header.addStretch(1)
        self.add_button = QPushButton("Add user")
        self.add_button.setObjectName("PrimaryButton")
        self.add_button.clicked.connect(self._add_user)
        self.edit_button = QPushButton("Edit")
        self.edit_button.clicked.connect(self._edit_user)
        self.reset_button = QPushButton("Reset password")
        self.reset_button.clicked.connect(self._reset_password)
        self.delete_button = QPushButton("Delete")
        self.delete_button.setObjectName("DangerButton")
        self.delete_button.clicked.connect(self._delete_user)
        for button in (self.add_button, self.edit_button, self.reset_button, self.delete_button):
            header.addWidget(button)
        users_layout.addLayout(header)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Username", "Full name", "Email", "Role", "Active", "Last login"]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        users_layout.addWidget(self.table)
        tabs.addTab(users_tab, "Users")

        audit_tab = QWidget()
        audit_layout = QVBoxLayout(audit_tab)
        audit_layout.addWidget(QLabel("Audit log of important actions"))
        self.audit_table = QTableWidget(0, 5)
        self.audit_table.setHorizontalHeaderLabels(["Time", "User", "Action", "Entity", "Details"])
        self.audit_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.audit_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        audit_layout.addWidget(self.audit_table)
        tabs.addTab(audit_tab, "Audit log")

    def refresh(self) -> None:
        with self.runtime.db.session_scope() as session:
            users = session.query(User).order_by(User.username).all()
            rows = [
                (
                    u.id, u.username, u.full_name or "", u.email or "", u.role,
                    "yes" if u.is_active else "no",
                    u.last_login_at.isoformat(sep=" ", timespec="seconds") if u.last_login_at else "",
                )
                for u in users
            ]
            entries = session.query(AuditLog).order_by(AuditLog.id.desc()).limit(300).all()
            audit_rows = [
                (
                    entry.ts.isoformat(sep=" ", timespec="seconds"),
                    entry.username,
                    entry.action,
                    (entry.entity_type or "") + (str(entry.entity_id) if entry.entity_id else ""),
                    entry.details,
                )
                for entry in entries
            ]

        self.table.setRowCount(len(rows))
        for row, values in enumerate(rows):
            for column, value in enumerate(values):
                if column == 0:
                    continue
                self.table.setItem(row, column, QTableWidgetItem(str(value)))

        self.audit_table.setRowCount(len(audit_rows))
        for row, values in enumerate(audit_rows):
            for column, value in enumerate(values):
                self.audit_table.setItem(row, column, QTableWidgetItem(str(value)))

    def _selected_user(self) -> Optional[User]:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Users", "Please select a user first.")
            return None
        with self.runtime.db.session_scope() as session:
            users = session.query(User).order_by(User.username).all()
            if row < len(users):
                return users[row]
        return None

    def _add_user(self) -> None:
        dialog = UserDialog(self.runtime, None, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        with self.runtime.db.session_scope() as session:
            if session.query(User).filter(User.username == values["username"]).first():
                QMessageBox.warning(self, "Users", "This username already exists.")
                return
            session.add(
                User(
                    username=values["username"],
                    full_name=values["full_name"],
                    email=values["email"],
                    role=values["role"],
                    password_hash=auth_service.hash_password(values["password"]),
                    is_active=True,
                    must_change_password=True,
                )
            )
        self.refresh()

    def _edit_user(self) -> None:
        user = self._selected_user()
        if user is None:
            return
        dialog = UserDialog(self.runtime, user, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        with self.runtime.db.session_scope() as session:
            stored = session.get(User, user.id)
            if stored is None:
                return
            stored.full_name = values["full_name"]
            stored.email = values["email"]
            stored.role = values["role"]
            if values["password"]:
                stored.password_hash = auth_service.hash_password(values["password"])
                stored.must_change_password = True
        self.refresh()

    def _reset_password(self) -> None:
        user = self._selected_user()
        if user is None:
            return
        password, ok = QInputDialog.getText(
            self, "Reset password", "New password (the user must change it after login):",
            QLineEdit.EchoMode.Password,
        )
        if not ok or not password:
            return
        error = auth_service.password_strength_error(password)
        if error:
            QMessageBox.warning(self, "Users", error)
            return
        with self.runtime.db.session_scope() as session:
            stored = session.get(User, user.id)
            if stored is None:
                return
            stored.password_hash = auth_service.hash_password(password)
            stored.must_change_password = True
        self.refresh()

    def _delete_user(self) -> None:
        user = self._selected_user()
        if user is None:
            return
        if user.id == self.user.id:
            QMessageBox.warning(self, "Users", "You cannot delete your own account.")
            return
        answer = QMessageBox.question(self, "Users", "Delete the account " + user.username + "?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        with self.runtime.db.session_scope() as session:
            stored = session.get(User, user.id)
            if stored is not None:
                session.delete(stored)
        self.refresh()
