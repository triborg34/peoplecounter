"""Line / area editor: draw counting lines and polygons on a live snapshot."""
from __future__ import annotations

import json
import logging
from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QImage, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsItemGroup,
    QGraphicsLineItem,
    QGraphicsPathItem,
    QGraphicsPolygonItem,
    QGraphicsScene,
    QGraphicsView,
)

from ..db.models import Camera, CounterArea, CounterLine

log = logging.getLogger(__name__)

MODE_SELECT = "select"
MODE_LINE = "line"
MODE_AREA = "area"

DRAFT_COLOR = "#eab308"

# The draft preview is a live rubber band: for a line, from the first click to
# the cursor; for an area, the polygon built so far plus a dashed rubber band
# from the last vertex to the cursor.  It is rebuilt on every mouse move and
# carries the vertices as handles, so the drawing is visible before it exists.
DRAFT_PEN_STYLE = Qt.PenStyle.DashLine


def _qcolor(value: str, fallback: str = "#22c55e") -> QColor:
    color = QColor(value)
    return color if color.isValid() else QColor(fallback)


class _Handle(QGraphicsEllipseItem):
    """A draggable vertex handle."""

    def __init__(self, owner, index: int):
        super().__init__(-5, -5, 10, 10)
        self.owner = owner
        self.index = index
        self.setBrush(QBrush(QColor("#f59e0b")))
        self.setPen(QPen(QColor("#ffffff"), 1))
        self.setZValue(12)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable
                     | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged and self.owner is not None:
            self.owner.handle_moved(self.index, self.pos())
        return super().itemChange(change, value)


class LineGraphic(QGraphicsItemGroup):
    """Visual representation of a counting line."""

    def __init__(self, line_id: int, x1: float, y1: float, x2: float, y2: float,
                 color: str, name: str, direction: str, on_change):
        super().__init__()
        self.line_id = line_id
        self.name = name
        self.direction = direction
        self.on_change = on_change
        self.color = _qcolor(color)

        self.line = QGraphicsLineItem(0, 0, 1, 1)
        self.line.setPen(QPen(self.color, 3))
        self.line.setZValue(10)
        self.addToGroup(self.line)

        self.handle_a = _Handle(self, 0)
        self.handle_b = _Handle(self, 1)
        self.addToGroup(self.handle_a)
        self.addToGroup(self.handle_b)

        # arrow showing the walking direction that is counted as IN
        self.arrow = QGraphicsLineItem()
        self.arrow.setPen(QPen(self.color, 3))
        self.arrow.setZValue(13)
        self.addToGroup(self.arrow)
        self.arrow_head = QGraphicsPolygonItem()
        self.arrow_head.setBrush(QBrush(self.color))
        self.arrow_head.setPen(QPen(self.color, 1))
        self.arrow_head.setZValue(14)
        self.addToGroup(self.arrow_head)

        self.set_points([(x1, y1), (x2, y2)])

    def set_points(self, points: List[Tuple[float, float]]) -> None:
        self._points = list(points)
        self.line.setLine(self._points[0][0], self._points[0][1], self._points[1][0], self._points[1][1])
        self.handle_a.setPos(QPointF(*self._points[0]))
        self.handle_b.setPos(QPointF(*self._points[1]))
        self._update_arrow()

    def _update_arrow(self) -> None:
        """Draw the perpendicular arrow that marks the counted direction."""
        import math

        (x1, y1), (x2, y2) = self._points
        vx, vy = x2 - x1, y2 - y1
        norm = math.hypot(vx, vy)
        if norm < 1e-6:
            return
        nx, ny = -vy / norm, vx / norm
        mid_x, mid_y = (x1 + x2) / 2.0, (y1 + y2) / 2.0
        # the arrow was designed for a 0..1 drawing space; scale it with the
        # actual line length so it stays visible on a pixel sized canvas
        half = max(16.0, min(80.0, norm * 0.06))
        size = max(6.0, half * 0.3)
        sign = -1 if self.direction == "B_TO_A" else 1
        start = QPointF(mid_x - nx * half * sign, mid_y - ny * half * sign)
        end = QPointF(mid_x + nx * half * sign, mid_y + ny * half * sign)
        self.arrow.setLine(start.x(), start.y(), end.x(), end.y())
        head = QPolygonF([
            QPointF(end.x(), end.y()),
            QPointF(end.x() - nx * size * sign - vx / norm * size * 0.6,
                    end.y() - ny * size * sign - vy / norm * size * 0.6),
            QPointF(end.x() - nx * size * sign + vx / norm * size * 0.6,
                    end.y() - ny * size * sign + vy / norm * size * 0.6),
        ])
        self.arrow_head.setPolygon(head)

    def handle_moved(self, index: int, position: QPointF) -> None:
        points = list(self._points)
        points[index] = (position.x(), position.y())
        self._points = points
        self.line.setLine(points[0][0], points[0][1], points[1][0], points[1][1])
        self.on_change(self)

    def points(self) -> List[Tuple[float, float]]:
        """Current endpoints as plain tuples (scene coordinates)."""
        return list(self._points)


class AreaGraphic(QGraphicsItemGroup):
    """Visual representation of a counting area (polygon)."""

    def __init__(self, area_id: int, points: List[Tuple[float, float]], color: str,
                 name: str, on_change):
        super().__init__()
        self.area_id = area_id
        self.name = name
        self.on_change = on_change
        self.color = _qcolor(color, "#3b82f6")

        self.polygon = QGraphicsPolygonItem()
        self.polygon.setPen(QPen(self.color, 2))
        fill = QColor(self.color.red(), self.color.green(), self.color.blue(), 45)
        brush = QBrush(fill)
        self.polygon.setBrush(brush)
        self.polygon.setZValue(9)
        self.addToGroup(self.polygon)

        self.handles: List[_Handle] = []
        self.set_points(points)

    def set_points(self, points) -> None:
        self._points = [
            (p.x(), p.y()) if isinstance(p, QPointF) else (float(p[0]), float(p[1]))
            for p in points
        ]
        polygon = QPolygonF([QPointF(*p) for p in self._points])
        self.polygon.setPolygon(polygon)
        while len(self.handles) < len(self._points):
            handle = _Handle(self, len(self.handles))
            self.handles.append(handle)
            self.addToGroup(handle)
        for index, handle in enumerate(self.handles):
            if index < len(self._points):
                handle.setVisible(True)
                handle.setPos(QPointF(*self._points[index]))
            else:
                handle.setVisible(False)

    def handle_moved(self, index: int, position: QPointF) -> None:
        points = list(self._points)
        points[index] = (position.x(), position.y())
        self._points = points
        self.polygon.setPolygon(QPolygonF([QPointF(x, y) for x, y in points]))
        self.on_change(self)

    def points(self) -> List[Tuple[float, float]]:
        """Current vertices as plain tuples (scene coordinates)."""
        return list(self._points)


class ZoneCanvas(QGraphicsView):
    """Drawing canvas on top of the camera snapshot."""

    zonesChanged = pyqtSignal()
    selectionChanged = pyqtSignal(object)
    pointsChanged = pyqtSignal(int)   # number of points in the current drawing

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setBackgroundBrush(QBrush(QColor("#0f1115")))
        # hover moves are needed for the live draft preview (rubber band)
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self.mode = MODE_SELECT
        # a sensible canvas when there is no snapshot yet (e.g. camera offline):
        # stored zones still render scaled inside a 1000x1000 space
        self.image_rect = QRectF(0, 0, 1000, 1000)
        self._pending: List[QPointF] = []
        self._draft: Optional[QGraphicsItemGroup] = None
        self._mouse_pos: Optional[QPointF] = None
        self._on_new_zone = None

    # -- helpers ---------------------------------------------------------
    def set_image(self, image: Optional[QImage]) -> None:
        scene = self.scene()
        for item in list(scene.items()):
            if item.zValue() < 0:
                scene.removeItem(item)
        if image is None:
            return
        pixmap = QPixmap.fromImage(image)
        item = scene.addPixmap(pixmap)
        item.setZValue(-1)
        width, height = image.width(), image.height()
        self.setSceneRect(QRectF(0, 0, width, height))
        self.fitInView(QRectF(0, 0, width, height), Qt.AspectRatioMode.KeepAspectRatio)
        self.image_rect = QRectF(0, 0, width, height)

    def to_normalized(self, position: QPointF) -> Tuple[float, float]:
        if self.image_rect.width() <= 0 or self.image_rect.height() <= 0:
            return (0.0, 0.0)
        x = (position.x() - self.image_rect.left()) / self.image_rect.width()
        y = (position.y() - self.image_rect.top()) / self.image_rect.height()
        return (max(0.0, min(1.0, x)), max(0.0, min(1.0, y)))

    def place(self, x: float, y: float) -> QPointF:
        """Scene position of a stored normalized coordinate.  Zones are stored
        in normalized 0..1 but drawn in scene pixels, so loading them must
        scale them back up by the snapshot size."""
        return self.to_scene(x, y)

    def to_scene(self, x: float, y: float) -> QPointF:
        return QPointF(
            self.image_rect.left() + x * self.image_rect.width(),
            self.image_rect.top() + y * self.image_rect.height(),
        )

    # -- drawing ---------------------------------------------------------
    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self._pending = []
        self._mouse_pos = None
        self._clear_draft()
        self.pointsChanged.emit(0)

    def _clear_draft(self) -> None:
        if self._draft is not None:
            self.scene().removeItem(self._draft)
            self._draft = None

    def _scene_position(self, event) -> QPointF:
        """Mouse events arrive in viewport coordinates; the drawing works in
        scene coordinates, so they must be mapped through the view transform."""
        return self.mapToScene(event.position().toPoint())

    def mousePressEvent(self, event):
        if self.mode == MODE_SELECT:
            super().mousePressEvent(event)
            return
        position = self._scene_position(event)
        if self.mode == MODE_LINE:
            self._pending.append(position)
            self.pointsChanged.emit(len(self._pending))
            if len(self._pending) == 2:
                self._create_line(self._pending[0], self._pending[1])
                self._pending = []
                self._clear_draft()
                self.pointsChanged.emit(0)
            else:
                self._update_draft()
        elif self.mode == MODE_AREA:
            # ignore clicks on the rubber band when a vertex already sits there
            if self._pending and self._points_near(self._pending[-1], position, self._dedupe_radius()):
                return
            self._pending.append(position)
            self._update_draft()
            self.pointsChanged.emit(len(self._pending))

    def mouseMoveEvent(self, event):
        if self.mode in (MODE_LINE, MODE_AREA):
            self._mouse_pos = self._scene_position(event)
            self._update_draft()
        else:
            super().mouseMoveEvent(event)

    def mouseDoubleClickEvent(self, event):
        if self.mode == MODE_AREA and len(self._pending) >= 3:
            position = self._scene_position(event)
            if not self._points_near(self._pending[-1], position, self._dedupe_radius()):
                # The closing click arrives as a double click, not as a
                # press, so the final vertex would otherwise be lost.
                self._pending.append(position)
            self._create_area(list(self._pending))
            self._pending = []
            self._mouse_pos = None
            self._clear_draft()
            self.pointsChanged.emit(0)
            return
        super().mouseDoubleClickEvent(event)

    @staticmethod
    def _points_near(first: QPointF, second: QPointF, radius: float) -> bool:
        return (first - second).manhattanLength() <= radius

    def _dedupe_radius(self) -> float:
        """The double-click dedupe is tuned in viewport pixels; positions are
        now scene pixels, so scale the radius by the current zoom so it stays
        ~5 viewport px regardless of fitInView."""
        scale = abs(self.transform().m11())
        return 5.0 / scale if scale > 1e-6 else 5.0

    def _update_draft(self) -> None:
        """Rebuild the rubber band preview for the current drawing mode."""
        self._clear_draft()
        points = self._pending
        cursor = self._mouse_pos

        if self.mode == MODE_LINE:
            if not points or cursor is None:
                return
            group, line = self._draft_group(points[0])
            line.setLine(points[0].x(), points[0].y(), cursor.x(), cursor.y())
            self.scene().addItem(group)
            self._draft = group
            return

        if self.mode != MODE_AREA or not points:
            return

        group = QGraphicsItemGroup()
        path = QPainterPath()
        path.moveTo(points[0])
        for point in points[1:]:
            path.lineTo(point)
        band_end = cursor if cursor is not None else points[-1]
        path.lineTo(band_end)
        path_item = QGraphicsPathItem(path)
        path_item.setPen(QPen(QColor(DRAFT_COLOR), 2, DRAFT_PEN_STYLE))
        path_item.setBrush(QBrush(QColor(0, 0, 0, 0)))
        path_item.setZValue(20)
        group.addToGroup(path_item)

        # vertex markers plus a small cross on the rubber band tip
        for point in points:
            dot = QGraphicsEllipseItem(point.x() - 3, point.y() - 3, 6, 6)
            dot.setBrush(QBrush(QColor(DRAFT_COLOR)))
            dot.setPen(QPen(QColor("#ffffff"), 1))
            dot.setZValue(21)
            group.addToGroup(dot)
        if cursor is not None and len(points) >= 2:
            cross = QGraphicsEllipseItem(cursor.x() - 2, cursor.y() - 2, 4, 4)
            cross.setBrush(QBrush(QColor("#ffffff")))
            cross.setPen(QPen(QColor(DRAFT_COLOR), 1))
            cross.setZValue(21)
            group.addToGroup(cross)

        self.scene().addItem(group)
        self._draft = group

    def _draft_group(self, start: QPointF):
        group = QGraphicsItemGroup()
        line = QGraphicsLineItem()
        line.setPen(QPen(QColor(DRAFT_COLOR), 2, DRAFT_PEN_STYLE))
        line.setZValue(20)
        dot = QGraphicsEllipseItem(-3, -3, 6, 6)
        dot.setBrush(QBrush(QColor(DRAFT_COLOR)))
        dot.setPen(QPen(QColor("#ffffff"), 1))
        dot.setZValue(21)
        dot.setPos(start)
        group.addToGroup(dot)
        group.addToGroup(line)
        return group, line

    def _create_line(self, start: QPointF, end: QPointF) -> None:
        if self._on_new_zone is None:
            return
        self._on_new_zone("line", [start, end])

    def _create_area(self, points: List[QPointF]) -> None:
        if self._on_new_zone is None:
            return
        self._on_new_zone("area", points)


class ZoneEditor(QDialog):
    """Dialog to create, move and delete counting lines and areas."""

    def __init__(self, runtime, camera_id: int, parent=None):
        super().__init__(parent)
        self.runtime = runtime
        self.camera_id = camera_id
        self.setWindowTitle("Line / Area editor")
        self.resize(1180, 720)

        with self.runtime.db.session_scope() as session:
            camera = session.get(Camera, camera_id)
            self.camera_name = camera.name if camera else ""
        self._line_items: Dict[int, LineGraphic] = {}
        self._area_items: Dict[int, AreaGraphic] = {}
        self._selected: Optional[object] = None

        root = QVBoxLayout(self)

        self.mode_hint = QLabel("Select a mode from the toolbar to start drawing.")
        self.mode_hint.setObjectName("Muted")
        self.mode_hint.setStyleSheet("background-color: rgba(0,0,0,0); color: #9aa4b2;")
        root.addWidget(self.mode_hint)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Mode"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Select / move points", MODE_SELECT)
        self.mode_combo.addItem("Draw line (click A then B)", MODE_LINE)
        self.mode_combo.addItem("Draw area (click points, double click to close)", MODE_AREA)
        self.mode_combo.currentIndexChanged.connect(
            lambda _: self._on_mode_changed()
        )
        toolbar.addWidget(self.mode_combo)
        self.direction_combo = QComboBox()
        self.direction_combo.addItem("A -> B", "A_TO_B")
        self.direction_combo.addItem("B -> A", "B_TO_A")
        self.direction_combo.addItem("Both directions", "BOTH")
        toolbar.addWidget(QLabel("Direction"))
        toolbar.addWidget(self.direction_combo)
        toolbar.addStretch(1)
        refresh = QPushButton("Refresh snapshot")
        refresh.clicked.connect(self._refresh_snapshot)
        toolbar.addWidget(refresh)
        root.addLayout(toolbar)

        body = QHBoxLayout()
        self.canvas = ZoneCanvas()
        self.canvas._on_new_zone = self._on_new_zone
        self.canvas.selectionChanged.connect(self._on_selection)
        self.canvas.pointsChanged.connect(self._on_points_changed)
        body.addWidget(self.canvas, 1)

        side = QVBoxLayout()
        side.addWidget(QLabel("Lines"))
        self.lines_list = QListWidget()
        self.lines_list.currentItemChanged.connect(lambda *_: self._on_list_selection(self.lines_list, "line"))
        side.addWidget(self.lines_list, 1)
        side.addWidget(QLabel("Areas"))
        self.areas_list = QListWidget()
        self.areas_list.currentItemChanged.connect(lambda *_: self._on_list_selection(self.areas_list, "area"))
        side.addWidget(self.areas_list, 1)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("selected object name")
        side.addWidget(self.name_edit)
        self.enabled_check = QCheckBox("Enabled")
        self.enabled_check.setChecked(True)
        side.addWidget(self.enabled_check)

        actions = QHBoxLayout()
        self.apply_button = QPushButton("Apply changes")
        self.apply_button.clicked.connect(self._apply_selected)
        self.delete_button = QPushButton("Delete")
        self.delete_button.setObjectName("DangerButton")
        self.delete_button.clicked.connect(self._delete_selected)
        actions.addWidget(self.apply_button)
        actions.addWidget(self.delete_button)
        side.addLayout(actions)

        side.addWidget(QLabel("Drag the round handles in the picture to move points."))
        side.addWidget(QLabel("Line crossings are counted at the bottom centre (feet) of a person."))
        body.addLayout(side)
        root.addLayout(body)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        root.addLayout(buttons)

        self._refresh_snapshot()
        self._reload_zones()

    # -- data ------------------------------------------------------------
    def _on_mode_changed(self) -> None:
        mode = self.mode_combo.currentData()
        self.canvas.set_mode(mode)
        if mode == MODE_LINE:
            self.mode_hint.setText("Draw a line: click point A, then move the mouse - the dashed preview follows the cursor - click point B to finish.")
        elif mode == MODE_AREA:
            self.mode_hint.setText("Draw an area: click the corners (each click adds a vertex), then double click to close the polygon.")
        else:
            self.mode_hint.setText("Select / move points: drag the round handles in the picture.")

    def _on_points_changed(self, count: int) -> None:
        mode = self.mode_combo.currentData()
        if mode == MODE_LINE:
            if count == 0:
                self.mode_hint.setText("Line: click point A to start (the dashed preview follows the cursor).")
            else:
                self.mode_hint.setText("Line: point A set - move the mouse and click point B to finish. Your drawing is shown as a dashed preview.")
        elif mode == MODE_AREA:
            if count == 0:
                self.mode_hint.setText("Area: click the first corner.")
            elif count < 3:
                self.mode_hint.setText("Area: {} point(s) placed so far - the rubber band shows the shape. Keep clicking corners, then double click to close.".format(count))
            else:
                self.mode_hint.setText("Area: {} corners placed - double click to close the polygon.".format(count))

    def _refresh_snapshot(self) -> None:
        packet = self.runtime.camera_manager.latest_packet(self.camera_id)
        if packet is None or packet.raw_frame is None:
            self.canvas.set_image(None)
            return
        import cv2
        from PyQt6.QtGui import QImage

        frame = packet.raw_frame
        height, width = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = QImage(rgb.data, width, height, 3 * width, QImage.Format.Format_RGB888).copy()
        self.canvas.set_image(image)

    def _reload_zones(self) -> None:
        for item in list(self.canvas.scene().items()):
            if isinstance(item, (LineGraphic, AreaGraphic)):
                self.canvas.scene().removeItem(item)
        self._line_items.clear()
        self._area_items.clear()
        self.lines_list.clear()
        self.areas_list.clear()

        with self.runtime.db.session_scope() as session:
            for line in session.query(CounterLine).filter(CounterLine.camera_id == self.camera_id).all():
                p1 = self.canvas.place(line.x1, line.y1)
                p2 = self.canvas.place(line.x2, line.y2)
                graphic = LineGraphic(
                    line.id, p1.x(), p1.y(), p2.x(), p2.y(), line.color, line.name,
                    line.direction, self._on_geometry_changed,
                )
                self.canvas.scene().addItem(graphic)
                self._line_items[line.id] = graphic
                item = QListWidgetItem(line.name + "  [" + line.direction + "]")
                item.setData(Qt.ItemDataRole.UserRole, line.id)
                self.lines_list.addItem(item)
            for area in session.query(CounterArea).filter(CounterArea.camera_id == self.camera_id).all():
                points = [self.canvas.place(x, y) for x, y in area.points_list]
                if len(points) < 3:
                    continue
                graphic = AreaGraphic(area.id, points, area.color, area.name, self._on_geometry_changed)
                self.canvas.scene().addItem(graphic)
                self._area_items[area.id] = graphic
                item = QListWidgetItem(area.name)
                item.setData(Qt.ItemDataRole.UserRole, area.id)
                self.areas_list.addItem(item)

    def _on_geometry_changed(self, graphic) -> None:
        self._persist_graphic(graphic)

    def _persist_graphic(self, graphic) -> None:
        with self.runtime.db.session_scope() as session:
            if isinstance(graphic, LineGraphic):
                line = session.get(CounterLine, graphic.line_id)
                if line is None:
                    return
                (x1, y1), (x2, y2) = graphic.points()
                line.x1, line.y1 = self.canvas.to_normalized(QPointF(x1, y1))
                line.x2, line.y2 = self.canvas.to_normalized(QPointF(x2, y2))
            else:
                area = session.get(CounterArea, graphic.area_id)
                if area is None:
                    return
                normalized = [self.canvas.to_normalized(QPointF(x, y)) for x, y in graphic.points()]
                area.points = json.dumps([[x, y] for x, y in normalized])
        self.runtime.sync_camera(self.camera_id)

    # -- selection -------------------------------------------------------
    def _on_list_selection(self, widget: QListWidget, kind: str) -> None:
        item = widget.currentItem()
        if item is None:
            return
        identifier = item.data(Qt.ItemDataRole.UserRole)
        self._selected = self._line_items.get(identifier) if kind == "line" else self._area_items.get(identifier)
        if self._selected is None:
            return
        self.name_edit.setText(self._selected.name)
        self.enabled_check.setChecked(True)
        if isinstance(self._selected, LineGraphic):
            self.direction_combo.setCurrentText(
                {"A_TO_B": "A -> B", "B_TO_A": "B -> A", "BOTH": "Both directions"}.get(
                    self._selected.direction, "Both directions"
                )
            )

    def _on_selection(self, graphic) -> None:
        self._selected = graphic

    def _apply_selected(self) -> None:
        if self._selected is None:
            return
        name = self.name_edit.text().strip() or self._selected.name
        with self.runtime.db.session_scope() as session:
            if isinstance(self._selected, LineGraphic):
                line = session.get(CounterLine, self._selected.line_id)
                if line is None:
                    return
                line.name = name
                line.direction = self.direction_combo.currentData()
                line.enabled = self.enabled_check.isChecked()
                self._selected.name = name
                self._selected.direction = line.direction
                self._selected._update_arrow()
            else:
                area = session.get(CounterArea, self._selected.area_id)
                if area is None:
                    return
                area.name = name
                area.enabled = self.enabled_check.isChecked()
                self._selected.name = name
        self.runtime.sync_camera(self.camera_id)
        self._reload_zones()

    def _delete_selected(self) -> None:
        if self._selected is None:
            return
        answer = QMessageBox.question(self, "Delete", "Delete the selected object?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        with self.runtime.db.session_scope() as session:
            if isinstance(self._selected, LineGraphic):
                line = session.get(CounterLine, self._selected.line_id)
                if line is not None:
                    session.delete(line)
            else:
                area = session.get(CounterArea, self._selected.area_id)
                if area is not None:
                    session.delete(area)
        self.runtime.sync_camera(self.camera_id)
        self._selected = None
        self._reload_zones()

    # -- creation --------------------------------------------------------
    def _on_new_zone(self, kind: str, points: List[QPointF]) -> None:
        if kind == "area" and len(points) < 3:
            return
        if kind == "line" and len(points) < 2:
            return
        if kind == "line":
            name, ok = QInputDialog.getText(self, "New line", "Name of the counting line:")
            if not ok or not name.strip():
                return
            x1, y1 = self.canvas.to_normalized(points[0])
            x2, y2 = self.canvas.to_normalized(points[1])
            with self.runtime.db.session_scope() as session:
                line = CounterLine(
                    camera_id=self.camera_id,
                    name=name.strip(),
                    color="#22c55e",
                    x1=x1, y1=y1, x2=x2, y2=y2,
                    direction=self.direction_combo.currentData(),
                    enabled=True,
                )
                session.add(line)
            self.runtime.sync_camera(self.camera_id)
        else:
            name, ok = QInputDialog.getText(self, "New area", "Name of the counting area:")
            if not ok or not name.strip():
                return
            normalized = [self.canvas.to_normalized(point) for point in points]
            with self.runtime.db.session_scope() as session:
                area = CounterArea(
                    camera_id=self.camera_id,
                    name=name.strip(),
                    color="#3b82f6",
                    points=json.dumps([[x, y] for x, y in normalized]),
                    enabled=True,
                )
                session.add(area)
            self.runtime.sync_camera(self.camera_id)
        self._reload_zones()
