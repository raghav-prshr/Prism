"""Regenerate the PRISM demo workbook.

If PRISM_sample_class_dataset.xlsx already exists, its first two columns
(Roll No and Name) are preserved as the class roster. Marks and attendance
are regenerated synthetically. They are NOT real academic results.
Run from this directory: python generate_sample.py
"""
import os
import random

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

SEED = 2026
SUBJECTS = ["AICA", "FLAT", "DAA", "SDP", "CG", "QAPD"]
SUBJECT_BIAS = {"AICA": 1, "FLAT": -4, "DAA": -2, "SDP": 3, "CG": 0, "QAPD": -1}
OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "PRISM_sample_class_dataset.xlsx")


def load_existing_roster():
    if not os.path.exists(OUTPUT):
        return []
    try:
        wb = load_workbook(OUTPUT, read_only=True, data_only=True)
        ws = wb[wb.sheetnames[0]]
        rows = list(ws.iter_rows(min_row=2, max_col=2, values_only=True))
        wb.close()
        roster = []
        for roll, name in rows:
            if roll is not None and name is not None and str(roll).strip() and str(name).strip():
                roster.append((str(roll).strip(), str(name).strip()))
        return roster
    except Exception:
        return []


def main():
    rng = random.Random(SEED)
    roster = load_existing_roster()
    if not roster:
        # Fallback synthetic roster only if no existing roster workbook is present.
        first = ["Aarav", "Vivaan", "Aditya", "Arjun", "Rohan", "Karan", "Ishaan", "Kabir",
                 "Ananya", "Diya", "Isha", "Kavya", "Meera", "Neha", "Priya", "Riya"]
        last = ["Sharma", "Verma", "Gupta", "Singh", "Kumar", "Mehta", "Jain", "Bansal"]
        names = set()
        while len(names) < 66:
            names.add(f"{rng.choice(first)} {rng.choice(last)}")
        roster = [(f"DEMO{i:03d}", name) for i, name in enumerate(sorted(names), 1)]
        rng.shuffle(roster)

    wb = Workbook()
    ws = wb.active
    ws.title = "Class Data"
    ws.append(["Roll No", "Name", *SUBJECTS, "Attendance"])
    for roll, name in roster:
        ability = min(93, max(24, rng.gauss(65, 17)))
        marks = [
            int(min(100, max(0, round(rng.gauss(ability + SUBJECT_BIAS[s], 10)))))
            for s in SUBJECTS
        ]
        attendance = round(min(100, max(50, rng.gauss(81 + (ability - 65) * 0.25, 10))), 1)
        ws.append([roll, name, *marks, attendance])

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for cell in ws[1]:
        cell.font = Font(name="Arial", bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", start_color="6D28D9")
        cell.alignment = Alignment(horizontal="center")
    for i, width in enumerate([22, 25, 12, 12, 12, 12, 12, 12, 15], start=1):
        ws.column_dimensions[get_column_letter(i)].width = width

    about = wb.create_sheet("About")
    about["A1"] = "SYNTHETIC DEMONSTRATION MARKS"
    about["A1"].font = Font(name="Arial", bold=True, size=12)
    about["A2"] = "The existing student names and roll numbers are preserved from the supplied roster."
    about["A3"] = "All subject marks and attendance values are randomly generated, not actual academic results."
    about["A4"] = "Marks use a 0–100 scale. Attendance is a percentage."
    about.column_dimensions["A"].width = 110

    wb.save(OUTPUT)
    print(f"Wrote {OUTPUT} with {len(roster)} students; marks and attendance are synthetic.")


if __name__ == "__main__":
    main()
