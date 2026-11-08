"""Main window: sidebar navigation, live view, pages and system tray."""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QAction, QBrush, QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QStackedWidget,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from ..db.models import Camera
from ..services import auth as auth_service
from .bridge import EngineBridge
from .cameras_page import CamerasPage
from .live_view import LiveView
from .reports_page import ReportsPage
from .settings_page import SettingsPage, load_settings
from .users_page import UsersPage
from .zones_page import ZonesPage

log = logging.getLogger(__name__)

PAGES = ("Live", "Cameras", "Lines and areas", "Reports", "Users", "Settings")


def _make_icon(color: str = "#4f6ef7") -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QBrush(QColor(color)))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(6, 6, 52, 52, 14, 14)
    painter.setPen(QColor("white"))
    font = painter.font()
    font.setBold(True)
    font.setPointSize(26)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "PC")
    painter.end()
    return QIcon(pixmap)



class MainWindow(QMainWindow):
    """The application shell."""

    def __init__(self, runtime, user, app=None):
        super().__init__()
        self.runtime = runtime
        self.user = user
        self.app = app
        self.setWindowTitle("People Counter")
        self.resize(1440, 900)

        self.bridge = EngineBridge(runtime, self)
        self._fullscreen_dialog = None

        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # sidebar
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(190)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(10, 12, 10, 12)
        brand = QLabel("People Counter")
        brand.setObjectName("HeaderTitle")
        side_layout.addWidget(brand)
        side_layout.addSpacing(10)
        self.nav = QListWidget()
        self.nav.setObjectName("SidebarList")
        for name in PAGES:
            self.nav.addItem(QListWidgetItem(name))
        self.nav.currentRowChanged.connect(self._on_nav)
        side_layout.addWidget(self.nav)
        side_layout.addStretch(1)
        self.user_label = QLabel(user.username + " (" + user.role + ")")
        self.user_label.setObjectName("Muted")
        side_layout.addWidget(self.user_label)
        logout_button = QLabel("Log out")
        logout_button.setStyleSheet("color: #9aa4b2; padding: 6px;")
        logout_button.setCursor(Qt.CursorShape.PointingHandCursor)
        logout_button.mousePressEvent = lambda event: self.logout()
        side_layout.addWidget(logout_button)
        root.addWidget(sidebar)

        # pages
        self.stack = QStackedWidget()
        self.live_view = LiveView(runtime, user)
        self.cameras_page = CamerasPage(runtime, user)
        self.zones_page = ZonesPage(runtime, user)
        self.reports_page = ReportsPage(runtime, user)
        self.users_page = UsersPage(runtime, user)
        self.settings_page = SettingsPage(runtime, user, app)
        for page in (self.live_view, self.cameras_page, self.zones_page,
                     self.reports_page, self.users_page, self.settings_page):
            self.stack.addWidget(page)
        root.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        # permissions: hide pages the role may not use
        if not auth_service.can(user.role, auth_service.PERM_USERS_MANAGE):
            self._remove_nav("Users")
        if not auth_service.can(user.role, auth_service.PERM_CAMERAS_MANAGE):
            self._remove_nav("Cameras")
            self._remove_nav("Lines and areas")

        # tray (not every platform offers one)
        self.tray = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = QSystemTrayIcon(_make_icon(), self)
            self.tray.setToolTip("People Counter")
            menu = QMenu()
            show_action = QAction("Show", self)
            show_action.triggered.connect(self._restore_from_tray)
            menu.addAction(show_action)
            self.tray.setContextMenu(menu)
            self.tray.activated.connect(self._tray_activated)
            self.tray.show()
        self._minimize_to_tray = bool(load_settings(runtime).get("minimize_to_tray", True))
        if self.tray is None:
            self._minimize_to_tray = False

        # wiring
        self.bridge.frameReady.connect(self.live_view.on_frame)
        self.bridge.cameraCountsChanged.connect(self.live_view.on_camera_counts)
        self.bridge.cameraStatusChanged.connect(self.live_view.on_status)
        self.bridge.countsChanged.connect(self.live_view.update_global)
        self.bridge.countEvent.connect(self._on_count_event)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._refresh_pages)
        self.refresh_timer.start(3000)

        self.statusBar().showMessage("Ready")
        self._refresh_pages()
        self.nav.setCurrentRow(0)

    def shutdown(self) -> None:
        """Stop every timer so Qt can be torn down cleanly."""
        self.bridge.stop()
        self.refresh_timer.stop()

    # -- navigation ------------------------------------------------------
    def _remove_nav(self, name: str) -> None:
        for index in range(self.nav.count()):
            if self.nav.item(index).text() == name:
                self.nav.takeItem(index)
                break

    def _on_nav(self, row: int) -> None:
        if row < 0:
            return
        self.stack.setCurrentIndex(row)
        page = self.stack.currentWidget()
        if hasattr(page, "refresh"):
            page.refresh()

    def _refresh_pages(self) -> None:
        try:
            self._reload_cameras()
            for index in (self.stack.indexOf(self.cameras_page), self.stack.indexOf(self.zones_page)):
                if index == self.stack.currentIndex():
                    page = self.stack.widget(index)
                    if hasattr(page, "refresh"):
                        page.refresh()
        except Exception:  # pragma: no cover
            log.exception("Periodic refresh failed")

    def _reload_cameras(self) -> None:
        with self.runtime.db.session_scope() as session:
            cameras = session.query(Camera).order_by(Camera.name).all()
            payload = [
                {
                    "id": camera.id,
                    "name": camera.name,
                    "enabled": camera.enabled,
                    "location": camera.location or "",
                    "source_type": camera.source_type,
                }
                for camera in cameras
            ]
        self.live_view.set_cameras(payload)

    # -- events ----------------------------------------------------------
    def _on_count_event(self, event: dict) -> None:
        camera = event.get("camera_name") or ("camera " + str(event.get("camera_id")))
        target = event.get("target_name") or "zone"
        self.statusBar().showMessage(
            "{direction} at {target} ({camera}) - track {track}".format(
                direction=event.get("direction", ""),
                target=target,
                camera=camera,
                track=event.get("track_id", ""),
            ),
            6000,
        )

    # -- zone editor -----------------------------------------------------
    def open_zone_editor(self, camera_id: int) -> None:
        from .zone_editor import ZoneEditor

        dialog = ZoneEditor(self.runtime, camera_id, self)
        dialog.exec()
        self._reload_cameras()
        self.cameras_page.refresh()
        self.zones_page.refresh()

    # -- tray ------------------------------------------------------------
    def apply_tray_setting(self, enabled: bool) -> None:
        self._minimize_to_tray = bool(enabled)

    def _tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._restore_from_tray()

    def _restore_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        if self._minimize_to_tray and self.tray is not None and self.tray.isVisible():
            event.ignore()
            self.hide()
            self.tray.showMessage(
                "People Counter", "The application is running in the system tray.", QSystemTrayIcon.MessageIcon.Information, 2500
            )
            return
        self.shutdown()
        event.accept()

    # -- logout ----------------------------------------------------------
    def logout(self) -> None:
        answer = QMessageBox.question(self, "Log out", "Log out of People Counter?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        if hasattr(self, "on_logout"):
            self.on_logout()
        self.close()
