"""CSV / Excel / PDF export helpers."""
from __future__ import annotations

import csv
import datetime as dt
import io
from typing import Any, Dict, Iterable, List, Optional, Sequence

EXPORT_FORMATS = ("csv", "excel", "pdf")


def export_csv(rows: Sequence[Dict[str, Any]], columns: Optional[Sequence[str]] = None) -> bytes:
    buffer = io.StringIO()
    if not rows:
        return buffer.getvalue().encode("utf-8")
    fieldnames = list(columns or rows[0].keys())
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in fieldnames})
    return buffer.getvalue().encode("utf-8-sig")


def export_excel(sheets: Dict[str, Sequence[Dict[str, Any]]]) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font

    workbook = Workbook()
    workbook.remove(workbook.active)
    for name, rows in sheets.items():
        sheet = workbook.create_sheet(title=(name or "Sheet")[:31])
        if not rows:
            sheet.append(["no data"])
            continue
        fieldnames = list(rows[0].keys())
        sheet.append(fieldnames)
        for cell in sheet[1]:
            cell.font = Font(bold=True)
        for row in rows:
            sheet.append([row.get(key, "") for key in fieldnames])
        for index, column in enumerate(fieldnames, start=1):
            width = max(len(str(column)) + 2, 12)
            sheet.column_dimensions[sheet.cell(row=1, column=index).column_letter].width = min(width, 40)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def export_pdf(
    title: str,
    summary: Dict[str, Any],
    tables: Sequence[Dict[str, Any]],
    timeseries: Optional[Sequence[Dict[str, Any]]] = None,
) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer, pagesize=landscape(A4), title=title, author="People Counter",
        leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm, bottomMargin=15 * mm,
    )
    styles = getSampleStyleSheet()
    story = [Paragraph(title, styles["Title"]), Spacer(1, 6 * mm)]

    summary_rows = [[str(key), str(value)] for key, value in summary.items()]
    summary_table = Table(summary_rows, colWidths=[70 * mm, 60 * mm])
    summary_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eef2ff")),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c7d2fe")),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ])
    )
    story.append(summary_table)
    story.append(Spacer(1, 6 * mm))

    for table in tables:
        title_text = table.get("title", "")
        rows = table.get("rows", [])
        if title_text:
            story.append(Paragraph(title_text, styles["Heading2"]))
        if not rows:
            story.append(Paragraph("No data", styles["Normal"]))
            story.append(Spacer(1, 4 * mm))
            continue
        header = list(rows[0].keys())
        data = [header] + [[str(row.get(key, "")) for key in header] for row in rows]
        table_obj = Table(data, repeatRows=1)
        table_obj.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#312e81")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#c7d2fe")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f3ff")]),
            ])
        )
        story.append(table_obj)
        story.append(Spacer(1, 5 * mm))

    document.build(story)
    return buffer.getvalue()


def export_report(fmt: str, rows: Sequence[Dict[str, Any]], summary: Dict[str, Any],
                  timeseries: Optional[Sequence[Dict[str, Any]]] = None) -> bytes:
    fmt = (fmt or "csv").lower()
    if fmt == "csv":
        return export_csv(rows)
    if fmt in ("excel", "xlsx"):
        return export_excel({"Events": rows})
    if fmt == "pdf":
        return export_pdf(
            "People counting report",
            summary,
            [{"title": "Events", "rows": list(rows)}],
            timeseries,
        )
    raise ValueError("unsupported export format: " + str(fmt))


def media_type(fmt: str) -> str:
    fmt = (fmt or "csv").lower()
    if fmt == "csv":
        return "text/csv"
    if fmt in ("excel", "xlsx"):
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if fmt == "pdf":
        return "application/pdf"
    return "application/octet-stream"


def file_extension(fmt: str) -> str:
    fmt = (fmt or "csv").lower()
    if fmt == "csv":
        return "csv"
    if fmt in ("excel", "xlsx"):
        return "xlsx"
    if fmt == "pdf":
        return "pdf"
    return "bin"
