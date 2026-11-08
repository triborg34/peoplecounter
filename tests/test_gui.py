"""Regression tests for the desktop shell.

They run head less with the offscreen Qt platform.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtCore import QEvent, QPoint, QPointF, Qt
from PyQt6.QtGui import QImage, QMouseEvent
from PyQt6.QtWidgets import QApplication

from app.db.models import User
from app.gui.camera_tile import CameraTile
from app.gui.main_window import MainWindow
from app.gui.theme import current_theme
from app.gui.zone_editor import MODE_AREA, MODE_LINE, ZoneCanvas


@pytest.fixture(scope="module")
def qapp():
    application = QApplication.instance() or QApplication([])
    yield application


@pytest.fixture()
def admin_user(runtime):
    with runtime.db.session_scope() as session:
        user = session.query(User).filter(User.username == "admin").first()
        if user is None:
            user = User(username="admin", password_hash="x", role="admin", is_active=True)
            session.add(user)
            session.commit()
        user_id = user.id
    return User(id=user_id, username="admin", role="admin")


def test_main_window_builds_without_an_application_reference(runtime, qapp, admin_user):
    """The window used to crash when the QApplication was not handed over."""
    window = MainWindow(runtime, admin_user)
    try:
        assert window.nav.count() >= 1
        assert window.stack.count() >= 1
    finally:
        window.shutdown()
        window.close()
        window.deleteLater()
        qapp.processEvents()


def test_main_window_builds_with_an_application_reference(runtime, qapp, admin_user):
    window = MainWindow(runtime, admin_user, qapp)
    try:
        assert window.nav.count() >= 1
        assert window.settings_page is not None
    finally:
        window.shutdown()
        window.close()
        window.deleteLater()
        qapp.processEvents()


def test_theme_helpers_survive_a_missing_application():
    from app.gui.theme import apply_theme

    assert current_theme(None) == "dark"
    apply_theme(None, "light")  # must not raise


def test_camera_tile_accepts_a_qimage(qapp):
    """setPixmap needs a QPixmap, not the QImage that scaled() returns."""
    import numpy as np

    from app.engine.types import FramePacket

    tile = CameraTile(1, "Entrance")
    tile.resize(480, 360)
    try:
        frame = np.zeros((360, 640, 3), dtype=np.uint8)
        packet = FramePacket(camera_id=1, frame=frame, timestamp=0.0)
        del frame  # the bridge copies the buffer

        from app.gui.bridge import EngineBridge

        # same conversion the engine bridge performs for every frame
        image = EngineBridge._to_image(packet.frame)
        assert image is not None
        tile.set_image(image)  # must not raise TypeError
        assert tile.video.pixmap() is not None
        assert not tile.video.pixmap().isNull()
    finally:
        tile.deleteLater()
        qapp.processEvents()


# -- zone editor drawing ------------------------------------------------

def _send_mouse(qapp, canvas: ZoneCanvas, event_type, pos, button=Qt.MouseButton.LeftButton,
                buttons=Qt.MouseButton.LeftButton):
    """Deliver a mouse event to the canvas viewport."""
    local = QPointF(*pos)
    global_pos = QPointF(canvas.viewport().mapToGlobal(QPoint(*pos)))
    event = QMouseEvent(event_type, local, global_pos, button, buttons, Qt.KeyboardModifier.NoModifier)
    qapp.sendEvent(canvas.viewport(), event)


def test_line_preview_follows_the_cursor(qapp):
    """After the first click the draft rubber band is visible, and it
    disappears again once the second click created the line."""
    from PyQt6.QtWidgets import QGraphicsLineItem

    canvas = ZoneCanvas()
    canvas.resize(640, 480)
    created = []
    canvas._on_new_zone = lambda kind, points: created.append((kind, list(points)))
    try:
        canvas.set_mode(MODE_LINE)
        _send_mouse(qapp, canvas, QEvent.Type.MouseButtonPress, (100, 200))
        assert canvas._pending and canvas._draft is None  # not yet, no mouse move
        _send_mouse(qapp, canvas, QEvent.Type.MouseMove, (350, 260))
        assert canvas._draft is not None, "no rubber band after moving the mouse"
        assert any(isinstance(item, QGraphicsLineItem) for item in canvas._draft.childItems())
        _send_mouse(qapp, canvas, QEvent.Type.MouseButtonPress, (450, 300))
        qapp.processEvents()
        assert created and created[0][0] == "line"
        assert len(created[0][1]) == 2
        assert canvas._draft is None  # finished, preview cleared
    finally:
        canvas.deleteLater()
        qapp.processEvents()


def test_area_double_click_keeps_the_closing_vertex(qapp):
    """The double click is a click without a press, so the polygon must take
    the closing point from the double click event itself."""
    canvas = ZoneCanvas()
    canvas.resize(640, 480)
    created = []
    canvas._on_new_zone = lambda kind, points: created.append((kind, list(points)))
    try:
        canvas.set_mode(MODE_AREA)
        corners = [(100, 100), (300, 100), (300, 300), (100, 300)]
        for corner in corners:
            _send_mouse(qapp, canvas, QEvent.Type.MouseButtonPress, corner)
        _send_mouse(qapp, canvas, QEvent.Type.MouseMove, (250, 250))
        assert canvas._draft is not None, "no polygon preview while drawing"

        closing = (200, 400)
        _send_mouse(qapp, canvas, QEvent.Type.MouseButtonDblClick, closing)
        qapp.processEvents()
        assert created and created[0][0] == "area"
        points = created[0][1]
        # 4 clicks + the double click vertex; the closing point is included
        assert len(points) == 5
        expected = canvas.mapToScene(QPoint(*closing))
        assert points[-1].x() == pytest.approx(expected.x())
        assert points[-1].y() == pytest.approx(expected.y())
        assert canvas._draft is None
    finally:
        canvas.deleteLater()
        qapp.processEvents()


def test_area_double_click_on_last_vertex_does_not_duplicate(qapp):
    """Double clicking exactly on the last corner closes the polygon without
    adding the same coordinate twice."""
    canvas = ZoneCanvas()
    canvas.resize(640, 480)
    created = []
    canvas._on_new_zone = lambda kind, points: created.append((kind, list(points)))
    try:
        canvas.set_mode(MODE_AREA)
        _send_mouse(qapp, canvas, QEvent.Type.MouseButtonPress, (100, 100))
        _send_mouse(qapp, canvas, QEvent.Type.MouseButtonPress, (300, 300))
        _send_mouse(qapp, canvas, QEvent.Type.MouseButtonPress, (400, 200))
        _send_mouse(qapp, canvas, QEvent.Type.MouseButtonDblClick, (400, 200))  # on the last vertex
        qapp.processEvents()
        assert created[0][0] == "area"
        assert len(created[0][1]) == 3
    finally:
        canvas.deleteLater()
        qapp.processEvents()


def test_clicks_are_mapped_to_scene_coordinates(qapp):
    """Mouse events arrive in viewport pixels; the drawing must use scene
    coordinates, otherwise a zoomed snapshot shifts every new zone."""
    canvas = ZoneCanvas()
    canvas.resize(640, 480)
    created = []
    canvas._on_new_zone = lambda kind, points: created.append((kind, list(points)))
    try:
        image = QImage(1920, 1080, QImage.Format.Format_RGB888)
        image.fill(0x20242b)
        canvas.set_image(image)  # applies fitInView: viewport != scene now

        canvas.set_mode(MODE_LINE)
        viewport_pos = (200, 150)
        _send_mouse(qapp, canvas, QEvent.Type.MouseButtonPress, viewport_pos)
        expected = canvas.mapToScene(QPoint(*viewport_pos))
        got = canvas._pending[0]
        assert (abs(got.x() - expected.x()) < 1e-6 and abs(got.y() - expected.y()) < 1e-6), \
            "click not mapped to scene: got %s, expected %s" % (got, expected)
    finally:
        canvas.deleteLater()
        qapp.processEvents()


def test_stored_zones_render_scaled_to_the_snapshot(runtime, qapp):
    """Previous draws are stored normalized but drawn in scene pixels; they
    must be scaled back up or every saved zone piles into the corner."""
    from PyQt6.QtWidgets import QGraphicsLineItem

    from app.db.models import Camera, CounterLine
    from app.gui.zone_editor import ZoneEditor

    with runtime.db.session_scope() as session:
        camera = Camera(name="zoned", source_type="file", enabled=False)
        session.add(camera)
        session.flush()
        session.add(CounterLine(camera_id=camera.id, name="Main",
                                x1=0.5, y1=0.5, x2=1.0, y2=0.5, direction="A_TO_B"))
        camera_id = camera.id

    editor = ZoneEditor(runtime, camera_id)
    try:
        image = QImage(1920, 1080, QImage.Format.Format_RGB888)
        image.fill(0x20242b)
        editor.canvas.set_image(image)
        editor._reload_zones()

        graphic = editor._line_items.get(next(iter(editor._line_items)))
        line_item = graphic.line
        x1, y1, x2, y2 = line_item.line().x1(), line_item.line().y1(), line_item.line().x2(), line_item.line().y2()
        assert (x1, y1) == pytest.approx((960.0, 540.0)), (x1, y1)
        assert (x2, y2) == pytest.approx((1920.0, 540.0)), (x2, y2)
    finally:
        editor.deleteLater()
        qapp.processEvents()


def test_persist_graphic_writes_normalized_coordinates(runtime, qapp):
    """Saving a moved handle must divide the scene pixels back to 0..1."""
    from app.db.models import Camera, CounterArea, CounterLine
    from app.gui.zone_editor import LineGraphic, ZoneEditor

    with runtime.db.session_scope() as session:
        camera = Camera(name="zoned2", source_type="file", enabled=False)
        session.add(camera)
        session.flush()
        session.add(CounterLine(camera_id=camera.id, name="L",
                                x1=0.1, y1=0.1, x2=0.2, y2=0.2))
        session.add(CounterArea(camera_id=camera.id, name="A",
                                points="[[0.1,0.1],[0.5,0.1],[0.3,0.4]]"))
        camera_id = camera.id

    editor = ZoneEditor(runtime, camera_id)
    try:
        image = QImage(1920, 1080, QImage.Format.Format_RGB888)
        image.fill(0x20242b)
        editor.canvas.set_image(image)
        editor._reload_zones()

        line_graphic = next(iter(editor._line_items.values()))
        line_graphic._points = [(960.0, 540.0), (1200.0, 540.0)]
        editor._persist_graphic(line_graphic)
        area_graphic = next(iter(editor._area_items.values()))
        area_graphic._points = [(480.0, 270.0), (960.0, 270.0), (720.0, 540.0)]
        editor._persist_graphic(area_graphic)

        with runtime.db.session_scope() as session:
            line = session.query(CounterLine).filter(CounterLine.camera_id == camera_id).one()
            assert (line.x1, line.y1, line.x2, line.y2) == pytest.approx((0.5, 0.5, 0.625, 0.5))
            area = session.query(CounterArea).filter(CounterArea.camera_id == camera_id).one()
            from app.db.models import CounterArea as CA

            points = area.points_list
            assert len(points) == 3
            for got, want in zip(points, [(0.25, 0.25), (0.5, 0.25), (0.375, 0.5)]):
                assert got == pytest.approx(want)
    finally:
        editor.deleteLater()
        qapp.processEvents()


def test_bridge_poll_handles_keyboard_interrupt(qapp, runtime):
    """KeyboardInterrupt is a BaseException, so the bridge must not rely on
    ``except Exception`` - Ctrl+C during a poll used to crash the app."""
    from app.gui.bridge import EngineBridge

    bridge = EngineBridge(runtime)
    quit_called = []
    bridge._request_quit = lambda: quit_called.append(True)

    def boom():
        raise KeyboardInterrupt

    runtime.counts_snapshot = boom
    try:
        bridge._poll()  # must not propagate
        assert quit_called == [True]
    finally:
        bridge.stop()
        bridge.deleteLater()
        qapp.processEvents()
