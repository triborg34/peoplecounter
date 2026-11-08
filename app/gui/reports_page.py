"""Reports page: filters, charts, summary tables and exports."""
from __future__ import annotations

import datetime as dt
import logging
from pathlib import Path
from typing import List, Optional

from PyQt6.QtCore import QDateTime, Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..db.models import Camera
from ..services import export as export_service
from ..services import reports as report_service

log = logging.getLogger(__name__)

try:  # charts are optional
    import pyqtgraph as pg

    HAS_PG = True
except Exception:  # pragma: no cover
    pg = None
    HAS_PG = False


class ReportsPage(QWidget):
    """Aggregated counting reports with charts and export."""

    def __init__(self, runtime, user, parent=None):
        super().__init__(parent)
        self.runtime = runtime
        self.user = user
        self._camera_checks: List[QCheckBox] = []

        layout = QVBoxLayout(self)
        title = QLabel("Reports")
        title.setObjectName("HeaderTitle")
        layout.addWidget(title)

        filters = QHBoxLayout()
        filters.addWidget(QLabel("From"))
        self.from_edit = QDateTimeEdit(QDateTime.currentDateTime().addDays(-7))
        self.from_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        filters.addWidget(self.from_edit)
        filters.addWidget(QLabel("To"))
        self.to_edit = QDateTimeEdit(QDateTime.currentDateTime())
        self.to_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        filters.addWidget(self.to_edit)
        filters.addWidget(QLabel("Interval"))
        self.interval_combo = QComboBox()
        for label, value in (("Minute", "minute"), ("Hour", "hour"), ("Day", "day"),
                             ("Week", "week"), ("Month", "month")):
            self.interval_combo.addItem(label, value)
        self.interval_combo.setCurrentIndex(1)
        filters.addWidget(self.interval_combo)
        filters.addWidget(QLabel("Direction"))
        self.direction_combo = QComboBox()
        self.direction_combo.addItem("All", "")
        self.direction_combo.addItem("IN", "IN")
        self.direction_combo.addItem("OUT", "OUT")
        filters.addWidget(self.direction_combo)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setObjectName("PrimaryButton")
        self.refresh_button.clicked.connect(self.refresh)
        filters.addWidget(self.refresh_button)
        layout.addLayout(filters)

        camera_row = QHBoxLayout()
        camera_row.addWidget(QLabel("Cameras"))
        self.camera_box = QWidget()
        self.camera_layout = QHBoxLayout(self.camera_box)
        self.camera_layout.setContentsMargins(0, 0, 0, 0)
        camera_row.addWidget(self.camera_box)
        camera_row.addStretch(1)
        layout.addLayout(camera_row)

        export_row = QHBoxLayout()
        export_row.addWidget(QLabel("Export"))
        for fmt in ("csv", "excel", "pdf"):
            button = QPushButton(fmt.upper())
            button.clicked.connect(lambda _=False, f=fmt: self._export(f))
            export_row.addWidget(button)
        export_row.addStretch(1)
        self.summary_label = QLabel("")
        self.summary_label.setObjectName("Muted")
        export_row.addWidget(self.summary_label)
        layout.addLayout(export_row)

        if HAS_PG:
            pg.setConfigOption("background", "#16181d")
            pg.setConfigOption("foreground", "#c3cad6")
        self.chart_tabs = QWidget()
        self.chart_layout = QVBoxLayout(self.chart_tabs)
        self.chart_layout.setContentsMargins(0, 0, 0, 0)
        if HAS_PG:
            self.timeseries_plot = pg.PlotWidget(title="Counts over time")
            self.peak_plot = pg.PlotWidget(title="Peak hours")
            self.camera_plot = pg.PlotWidget(title="Camera comparison")
            for plot in (self.timeseries_plot, self.peak_plot, self.camera_plot):
                plot.showGrid(x=True, y=True, alpha=0.2)
            from PyQt6.QtWidgets import QTabWidget

            tabs = QTabWidget()
            tabs.addTab(self.timeseries_plot, "Time series")
            tabs.addTab(self.peak_plot, "Peak hours")
            tabs.addTab(self.camera_plot, "Cameras")
            self.chart_layout.addWidget(tabs)
        else:
            layout.addWidget(QLabel("Install pyqtgraph to see the charts."))
        layout.addWidget(self.chart_tabs, 1)

        self.summary_table = QTableWidget(0, 4)
        self.summary_table.setHorizontalHeaderLabels(["Camera", "IN", "OUT", "Total"])
        self.summary_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.summary_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.summary_table)

    # -- cameras ---------------------------------------------------------
    def refresh_cameras(self) -> None:
        while self.camera_layout.count():
            item = self.camera_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._camera_checks = []
        with self.runtime.db.session_scope() as session:
            cameras = session.query(Camera).order_by(Camera.name).all()
            for camera in cameras:
                check = QCheckBox(camera.name)
                check.setChecked(True)
                check.camera_id = camera.id
                self._camera_checks.append(check)
                self.camera_layout.addWidget(check)
        self.camera_layout.addStretch(1)

    def _selected_camera_ids(self) -> List[int]:
        return [check.camera_id for check in self._camera_checks if check.isChecked()]

    def _filters(self) -> report_service.ReportFilters:
        return report_service.ReportFilters(
            start=self.from_edit.dateTime().toPyDateTime(),
            end=self.to_edit.dateTime().toPyDateTime(),
            camera_ids=self._selected_camera_ids(),
            direction=self.direction_combo.currentData() or None,
        )

    # -- report ----------------------------------------------------------
    def refresh(self) -> None:
        filters = self._filters()
        interval = self.interval_combo.currentData()
        with self.runtime.db.session_scope() as session:
            totals = report_service.totals(session, filters)
            series = report_service.timeseries(session, filters, interval)
            by_camera = report_service.summary_by_camera(session, filters)
            peaks = report_service.peak_hours(session, filters)

        self.summary_label.setText(
            "IN {in}   OUT {out}   TOTAL {total}   events {events}".format(**totals)
        )
        self.summary_table.setRowCount(len(by_camera))
        for row, entry in enumerate(by_camera):
            values = [
                entry.get("camera_name") or str(entry.get("camera_id")),
                str(entry.get("in", 0)),
                str(entry.get("out", 0)),
                str(entry.get("total", 0)),
            ]
            for column, value in enumerate(values):
                self.summary_table.setItem(row, column, QTableWidgetItem(value))

        if HAS_PG:
            self._draw_series(series)
            self._draw_peaks(peaks)
            self._draw_cameras(by_camera)

    def _draw_series(self, series) -> None:
        plot = self.timeseries_plot
        plot.clear()
        if not series:
            return
        # a step plot needs the bucket edges on x (n+1) and n values on y
        x = list(range(len(series) + 1))
        inbound = [entry.get("in", 0) for entry in series]
        outbound = [entry.get("out", 0) for entry in series]
        plot.plot(x, inbound, stepMode="center", symbol="o", name="IN")
        plot.plot(x, outbound, stepMode="center", symbol="o", name="OUT")
        plot.setLabel("bottom", "bucket")
        plot.setLabel("left", "people")
        plot.addLegend()
        try:
            plot.setWindowTitle("Counts over time")
        except Exception:
            pass

    def _draw_peaks(self, peaks) -> None:
        plot = self.peak_plot
        plot.clear()
        if not peaks:
            return
        hours = [entry["hour"] for entry in peaks]
        counts = [entry["count"] for entry in peaks]
        bars = pg.BarGraphItem(x=hours, height=counts, width=0.7, brush="#4f6ef7")
        plot.addItem(bars)
        plot.setLabel("bottom", "hour of day")
        plot.setLabel("left", "events")

    def _draw_cameras(self, by_camera) -> None:
        plot = self.camera_plot
        plot.clear()
        if not by_camera:
            return
        names = [entry.get("camera_name") or str(entry.get("camera_id")) for entry in by_camera]
        inbound = [entry.get("in", 0) for entry in by_camera]
        outbound = [entry.get("out", 0) for entry in by_camera]
        x = list(range(len(names)))
        plot.plot(x, inbound, symbol="o", name="IN")
        plot.plot(x, outbound, symbol="s", name="OUT")
        plot.setLabel("bottom", "camera")
        plot.addLegend()
        try:
            ticks = [(index, name) for index, name in enumerate(names)]
            plot.getViewBox().setMouseEnabled(x=True, y=False)
            axis = plot.getAxis("bottom")
            axis.setTicks([ticks])
        except Exception:
            pass

    # -- export ----------------------------------------------------------
    def _export(self, fmt: str) -> None:
        filters = self._filters()
        with self.runtime.db.session_scope() as session:
            rows = report_service.event_rows(session, filters)
            totals = report_service.totals(session, filters)
            series = report_service.timeseries(session, filters, "day")
        try:
            payload = export_service.export_report(fmt, rows, totals, series)
        except Exception as exc:
            QMessageBox.warning(self, "Export", "Export failed: " + str(exc))
            return
        default = str(Path(self.runtime.settings.report_output_dir) /
                      ("people-counter-report." + export_service.file_extension(fmt)))
        path, _ = QFileDialog.getSaveFileName(self, "Save report", default)
        if not path:
            return
        try:
            Path(path).write_bytes(payload)
        except Exception as exc:
            QMessageBox.warning(self, "Export", "Could not write the file: " + str(exc))
            return
        QMessageBox.information(self, "Export", "Report written to " + path)
