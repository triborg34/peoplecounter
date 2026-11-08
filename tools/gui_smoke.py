"""Headless smoke test of the PyQt6 user interface.

    python tools/gui_smoke.py [output.png]

Creates every window off screen, renders them and saves a screenshot so the
layout can be checked without a display.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PyQt6.QtWidgets import QApplication

from app.bootstrap import ensure_default_admin
from app.config import get_settings
from app.db.models import Camera, CounterLine, User
from app.engine.runtime import EngineRuntime
from app.gui.camera_dialog import CameraDialog
from app.gui.main_window import MainWindow
from app.gui.login_dialog import LoginDialog
from app.gui.reports_page import ReportsPage
from app.gui.settings_page import SettingsPage
from app.gui.users_page import UsersPage
from app.gui.zone_editor import ZoneEditor


def main() -> int:
    settings = get_settings()
    app = QApplication(sys.argv)
    from app.gui.theme import apply_theme

    apply_theme(app, "dark")

    runtime = EngineRuntime(settings)
    runtime.db.create_all()
    ensure_default_admin(runtime.db, settings)

    with runtime.db.session_scope() as session:
        camera = session.query(Camera).first()
        if camera is None:
            camera = Camera(
                name="Entrance",
                location="Ground floor",
                source_type="file",
                file_path=str(Path(settings.data_dir) / "sample" / "sample_walk.mp4"),
                enabled=False,
            )
            session.add(camera)
            session.flush()
            session.add(
                CounterLine(
                    camera_id=camera.id, name="Main door",
                    x1=0.2, y1=0.5, x2=0.8, y2=0.5, direction="A_TO_B",
                )
            )
            session.commit()
            camera_id = camera.id
        else:
            camera_id = camera.id

    admin = session_user = None
    with runtime.db.session_scope() as session:
        admin = session.query(User).filter(User.username == "admin").first()
        admin = User(
            id=admin.id, username=admin.username, role=admin.role,
            must_change_password=False,
        ) if admin else None
    assert admin is not None, "the admin user was not created"

    # every window must be constructible
    login = LoginDialog(runtime)
    window = MainWindow(runtime, admin, app)
    camera_dialog = CameraDialog(runtime, None, window)
    editor = ZoneEditor(runtime, camera_id, window)
    for page in (ReportsPage(runtime, admin), UsersPage(runtime, admin),
                 SettingsPage(runtime, admin, app)):
        page.refresh() if hasattr(page, "refresh") else None

    window.resize(1440, 900)
    window.show()
    app.processEvents()

    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("gui_smoke.png")
    window.grab().save(str(output))
    print("windows:", "login", "main", "camera dialog", "zone editor")
    print("nav items:", [window.nav.item(i).text() for i in range(window.nav.count())])
    print("tiles:", len(window.live_view.tiles))
    print("screenshot:", output.resolve())
    window.shutdown()
    window.close()
    window.deleteLater()
    app.processEvents()
    runtime.stop()
    app.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
