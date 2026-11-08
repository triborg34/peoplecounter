"""Report queries and exports."""
from __future__ import annotations

import datetime as dt
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from ....services import auth as auth_service
from ....services import export as export_service
from ....services import reports as report_service
from ...deps import get_db, require_permission
from ..schemas import ReportResponse

log = logging.getLogger(__name__)
router = APIRouter(prefix="/reports", tags=["reports"])


def _filters(
    start: Optional[dt.datetime] = None,
    end: Optional[dt.datetime] = None,
    camera_id: Optional[List[int]] = Query(default=None),
    kind: Optional[str] = None,
    target_id: Optional[int] = None,
    direction: Optional[str] = None,
) -> report_service.ReportFilters:
    return report_service.ReportFilters(
        start=start,
        end=end,
        camera_ids=list(camera_id or []),
        kind=kind if kind in ("line", "area") else None,
        target_id=target_id,
        direction=direction.upper() if direction else None,
    )


@router.get("/summary", response_model=ReportResponse)
def summary(
    request: Request,
    start: Optional[dt.datetime] = None,
    end: Optional[dt.datetime] = None,
    camera_id: Optional[List[int]] = Query(default=None),
    kind: Optional[str] = None,
    target_id: Optional[int] = None,
    direction: Optional[str] = None,
    interval: str = "hour",
    session: Session = Depends(get_db),
    _: object = Depends(require_permission(auth_service.PERM_REPORTS_VIEW)),
) -> ReportResponse:
    filters = _filters(start, end, camera_id, kind, target_id, direction)
    return ReportResponse(
        filters={"start": str(start), "end": str(end), "camera_ids": filters.camera_ids,
                 "kind": filters.kind, "target_id": filters.target_id, "direction": filters.direction,
                 "interval": interval},
        totals=report_service.totals(session, filters),
        timeseries=report_service.timeseries(session, filters, interval),
        by_camera=report_service.summary_by_camera(session, filters),
        by_target=report_service.summary_by_target(session, filters),
        peak_hours=report_service.peak_hours(session, filters),
        events=report_service.event_rows(session, filters)[:2000],
    )


@router.get("/export")
def export_report(
    request: Request,
    format: str = "csv",
    start: Optional[dt.datetime] = None,
    end: Optional[dt.datetime] = None,
    camera_id: Optional[List[int]] = Query(default=None),
    kind: Optional[str] = None,
    target_id: Optional[int] = None,
    direction: Optional[str] = None,
    session: Session = Depends(get_db),
    _: object = Depends(require_permission(auth_service.PERM_REPORTS_EXPORT)),
):
    filters = _filters(start, end, camera_id, kind, target_id, direction)
    rows = report_service.event_rows(session, filters)
    totals = report_service.totals(session, filters)
    series = report_service.timeseries(session, filters, "day")
    try:
        payload = export_service.export_report(format, rows, totals, series)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    filename = "people-counter-report." + export_service.file_extension(format)
    return Response(
        content=payload,
        media_type=export_service.media_type(format),
        headers={"Content-Disposition": 'attachment; filename="' + filename + '"'},
    )
