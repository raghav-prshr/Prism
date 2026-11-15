"""Build the processed Excel workbook (a real .xlsx) from an analysis result."""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

FONT = "Arial"
PURPLE = "6D28D9"
THIN = Side(style="thin", color="DDD6EE")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
CLASS_FILLS = {
    "Advanced": "D1FAE5",
    "Average": "DBEAFE",
    "Needs Attention": "FEE2E2",
    "No Data": "F3F4F6",
}


def _set(ws, row: int, col: int, value: Any):
    """Write a cell. Text starting with '=' is stored as text, never as a formula."""
    cell = ws.cell(row=row, column=col)
    cell.value = value
    if isinstance(value, str) and cell.data_type == "f":
        cell.data_type = "s"
    return cell


def _header(cell) -> None:
    cell.font = Font(name=FONT, size=10, bold=True, color="FFFFFF")
    cell.fill = PatternFill("solid", start_color=PURPLE)
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    cell.border = BORDER


def build_workbook(result: dict) -> bytes:
    subjects = result["columns"]["subjects"]
    students = result["students"]
    wb = Workbook()

    # ---- Sheet 1: student performance ------------------------------------- #
    ws = wb.active
    ws.title = "Student Performance"
    headers = ["Roll No", "Name", *subjects, "Attendance (%)", "Average", "Percentage (%)", "Classification"]
    for c, h in enumerate(headers, start=1):
        _header(_set(ws, 1, c, h))
    ws.row_dimensions[1].height = 30

    n_sub = len(subjects)
    col_att, col_avg, col_pct, col_cls = n_sub + 3, n_sub + 4, n_sub + 5, n_sub + 6
    for r, s in enumerate(students, start=2):
        row = [s["roll_no"], s["name"], *[s["marks"].get(sub) for sub in subjects],
               s["attendance"], s["average"], s["percentage"], s["classification"]]
        for c, v in enumerate(row, start=1):
            cell = _set(ws, r, c, v)
            cell.font = Font(name=FONT, size=10)
            cell.border = BORDER
            cell.alignment = Alignment(horizontal="left" if c <= 2 else "center", vertical="center")
            if c in (col_att, col_avg, col_pct):
                cell.number_format = "0.00"
        fill = CLASS_FILLS.get(s["classification"])
        if fill:
            ws.cell(row=r, column=col_cls).fill = PatternFill("solid", start_color=fill)

    ws.freeze_panes = "C2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{len(students) + 1}"
    widths = {1: 14, 2: min(34, max([len(str(s["name"])) for s in students] + [12]) + 2)}
    for c in range(1, len(headers) + 1):
        ws.column_dimensions[get_column_letter(c)].width = widths.get(c, 16 if c >= col_att else 11)
    ws.column_dimensions[get_column_letter(col_cls)].width = 18

    # ---- Sheet 2: summary ------------------------------------------------- #
    sm = wb.create_sheet("Summary")
    summary, th = result["summary"], result["thresholds"]
    r = 1
    _set(sm, r, 1, "PRISM – Student Performance Summary").font = Font(name=FONT, size=14, bold=True, color=PURPLE)
    r += 1
    _set(sm, r, 1, f"Source file: {result['filename']}").font = Font(name=FONT, size=10)
    r += 1
    _set(sm, r, 1, f"Generated (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}").font = Font(name=FONT, size=10)
    r += 2

    def block(title: str, rows: list[tuple]) -> None:
        nonlocal r
        _header(_set(sm, r, 1, title))
        _header(_set(sm, r, 2, "Value"))
        for label, value in rows:
            r += 1
            a = _set(sm, r, 1, label)
            b = _set(sm, r, 2, value)
            for cell in (a, b):
                cell.font = Font(name=FONT, size=10)
                cell.border = BORDER
            b.alignment = Alignment(horizontal="right")
            if isinstance(value, float):
                b.number_format = "0.00"
        r += 2

    hi, lo = summary["highest"], summary["lowest"]
    block("Class statistics", [
        ("Total students", summary["total_students"]),
        ("Class average (%)", summary["class_average"]),
        ("Highest percentage", hi["value"] if hi else None),
        ("Highest scorer", (hi["name"] or hi["roll_no"]) if hi else None),
        ("Lowest percentage", lo["value"] if lo else None),
        ("Lowest scorer", (lo["name"] or lo["roll_no"]) if lo else None),
        ("Average attendance (%)", summary["attendance_average"]),
    ])
    block("Classification thresholds", [
        (f"Advanced (percentage ≥)", th["advanced"]),
        (f"Average (percentage ≥)", th["attention"]),
        ("Needs Attention", f"below {th['attention']:g}"),
    ])
    block("Classification distribution", [(k, v) for k, v in result["distribution"].items()])

    _header(_set(sm, r, 1, "Subject"))
    for c, h in enumerate(["Average", "Highest", "Lowest", "Valid marks"], start=2):
        _header(_set(sm, r, c, h))
    for st in result["subject_stats"]:
        r += 1
        for c, v in enumerate([st["subject"], st["average"], st["highest"], st["lowest"], st["count"]], start=1):
            cell = _set(sm, r, c, v)
            cell.font = Font(name=FONT, size=10)
            cell.border = BORDER
            if c in (2, 3, 4):
                cell.number_format = "0.00"
    r += 2
    note = ("Classification is rule-based, using the thresholds above. It is not a machine-learning prediction. "
            "Averages and percentages are calculated from the uploaded marks, assuming a 0–100 scale.")
    _set(sm, r, 1, note).font = Font(name=FONT, size=9, italic=True)
    sm.column_dimensions["A"].width = 34
    for col in "BCDE":
        sm.column_dimensions[col].width = 16

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
