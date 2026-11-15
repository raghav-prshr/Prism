"""PRISM dataset processing.

Pure pandas/numpy logic with no web-framework imports, so it can be unit tested
on its own. Uploaded bytes are processed in memory and never written to disk.
"""
from __future__ import annotations

import csv
import io
import json
import math
import os
import re
from collections import Counter
from typing import Any, Optional

import numpy as np
import pandas as pd

MAX_UPLOAD_BYTES = 15 * 1024 * 1024
SUPPORTED_EXTENSIONS = (".csv", ".xls", ".xlsx")
MAX_MARKS = 100.0  # MVP assumption: every subject is marked out of 100
DEFAULT_ADVANCED = 75.0
DEFAULT_ATTENTION = 40.0

ADVANCED = "Advanced"
AVERAGE = "Average"
NEEDS_ATTENTION = "Needs Attention"
NO_DATA = "No Data"
CLASSIFICATIONS = (ADVANCED, AVERAGE, NEEDS_ATTENTION, NO_DATA)

# Cell contents treated as "no value" (e.g. absent students) rather than invalid.
MISSING_TOKENS = {"", "nan", "none", "null", "na", "n/a", "nil", "-", "--", "ab", "absent", "abs"}

ID_ALIASES = {
    "rollno", "rollnumber", "rollnum", "roll", "studentid", "registrationnumber",
    "registrationno", "regno", "regnumber", "enrollmentnumber", "enrollmentno",
    "enrolmentnumber", "enrolmentno", "studentnumber", "sid", "id",
}
NAME_ALIASES = {"name", "studentname", "fullname", "nameofstudent", "nameofthestudent", "student"}
ATTENDANCE_ALIASES = {
    "attendance", "attendancepercentage", "attendancepercent", "attendancepct",
    "attendancerate", "att", "attpercentage",
}
# Columns that are never subject marks (serial numbers, totals, derived values...).
IGNORED_ALIASES = {
    "sno", "srno", "slno", "serialno", "serialnumber", "sr", "total", "grandtotal",
    "average", "avg", "percentage", "percent", "rank", "result", "grade", "cgpa",
    "sgpa", "gpa", "remarks", "remark", "status", "classification", "section",
    "class", "division", "gender", "email", "phone", "mobile",
}


class ProcessingError(Exception):
    """A user-facing error with a machine-readable code."""

    def __init__(self, code: str, message: str, status: int = 400, extra: Optional[dict] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.extra = extra or {}

    def to_detail(self) -> dict:
        return {"code": self.code, "message": self.message, **self.extra}


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #
def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def _num(value: Any) -> Optional[float]:
    """Return a JSON-safe rounded float, or None for missing / non-finite values."""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return round(f, 2)


def _blank_mask(series: pd.Series) -> pd.Series:
    text = series.astype(str).str.strip().str.lower()
    return series.isna() | text.isin(MISSING_TOKENS)


def _to_numeric(series: pd.Series) -> pd.Series:
    text = series.astype(str).str.strip().str.replace("%", "", regex=False)
    return pd.to_numeric(text, errors="coerce")


def _clean_text(series: pd.Series) -> pd.Series:
    def convert(v: Any) -> str:
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return ""
        if isinstance(v, float) and v.is_integer():
            return str(int(v))
        text = str(v).strip()
        return "" if text.lower() in ("nan", "none", "nat") else text

    return series.map(convert)


def _is_text_cell(v: Any) -> bool:
    if not isinstance(v, str) or not v.strip():
        return False
    try:
        float(v.strip().replace("%", ""))
        return False
    except ValueError:
        return True


# --------------------------------------------------------------------------- #
# Reading uploads
# --------------------------------------------------------------------------- #
def _read_csv(content: bytes) -> pd.DataFrame:
    text = None
    for enc in ("utf-8-sig", "cp1252"):
        try:
            text = content.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        text = content.decode("latin-1")

    first_line = next((ln for ln in text.splitlines() if ln.strip()), "")
    delimiter = max((",", ";", "\t", "|"), key=lambda d: first_line.count(d))
    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    width = max((len(r) for r in rows), default=0)
    if width == 0:
        raise ProcessingError("EMPTY_FILE", "The uploaded file is empty.")
    cleaned = []
    for r in rows:
        cells = [(c.strip() if c.strip() != "" else None) for c in r]
        cleaned.append(cells + [None] * (width - len(cells)))
    return pd.DataFrame(cleaned, dtype=object)


def read_table(content: bytes, filename: str) -> tuple[pd.DataFrame, list[str]]:
    """Read CSV/XLS/XLSX bytes into a clean DataFrame with unique string headers."""
    warnings: list[str] = []
    ext = os.path.splitext(filename or "")[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ProcessingError(
            "UNSUPPORTED_FILE_TYPE",
            f"Unsupported file type '{ext or 'unknown'}'. Please upload a .csv, .xls or .xlsx file.",
            415,
        )
    if not content:
        raise ProcessingError("EMPTY_FILE", "The uploaded file is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise ProcessingError("FILE_TOO_LARGE", "The file is larger than the 15 MB limit.", 413)

    try:
        if ext == ".csv":
            raw = _read_csv(content)
        elif ext == ".xlsx":
            raw = pd.read_excel(io.BytesIO(content), sheet_name=0, header=None, dtype=object, engine="openpyxl")
        else:
            raw = pd.read_excel(io.BytesIO(content), sheet_name=0, header=None, dtype=object, engine="xlrd")
    except ProcessingError:
        raise
    except ImportError:
        raise ProcessingError(
            "MISSING_DEPENDENCY", "The server is missing the library needed to read this file type.", 500
        )
    except Exception:
        raise ProcessingError(
            "UNREADABLE_FILE",
            f"The file could not be read as a valid {ext[1:].upper()} file. It may be corrupted, "
            "password-protected, or have the wrong extension.",
        )

    raw = raw.dropna(how="all").dropna(axis=1, how="all").reset_index(drop=True)
    if raw.empty:
        raise ProcessingError("EMPTY_FILE", "The file does not contain any data.")

    # The header is the row (within the first 10) with the most text-like cells.
    # This skips title rows above the real header.
    best_row, best_score = 0, -1
    for i in range(min(10, len(raw))):
        score = sum(_is_text_cell(v) for v in raw.iloc[i].tolist())
        if score > best_score:
            best_row, best_score = i, score
    if best_row > 0:
        warnings.append(f"Skipped {best_row} row(s) above the header row.")

    header = raw.iloc[best_row].tolist()
    body = raw.iloc[best_row + 1:].reset_index(drop=True)
    if body.empty:
        raise ProcessingError("NO_DATA_ROWS", "The file has a header row but no student rows.")

    names: list[str] = []
    seen: Counter = Counter()
    for i, h in enumerate(header):
        if h is None or (isinstance(h, float) and math.isnan(h)) or str(h).strip() == "":
            base = f"Column {i + 1}"
        elif isinstance(h, float) and h.is_integer():
            base = str(int(h))
        else:
            base = str(h).strip()
        seen[base.lower()] += 1
        name = base if seen[base.lower()] == 1 else f"{base} ({seen[base.lower()]})"
        if seen[base.lower()] > 1:
            warnings.append(f"Duplicate column name '{base}' was renamed to '{name}'.")
        names.append(name)
    body.columns = names
    return body, warnings


# --------------------------------------------------------------------------- #
# Column detection and mapping
# --------------------------------------------------------------------------- #
def detect_columns(df: pd.DataFrame) -> dict:
    cols = list(df.columns)
    norms = {c: _norm(c) for c in cols}
    taken: set = set()

    def pick(aliases: set, fuzzy) -> Optional[str]:
        for c in cols:
            if c not in taken and norms[c] in aliases:
                taken.add(c)
                return c
        for c in cols:
            if c not in taken and fuzzy(norms[c]):
                taken.add(c)
                return c
        return None

    roll = pick(ID_ALIASES, lambda n: n.startswith(("roll", "regist", "enrol")))
    name = pick(NAME_ALIASES, lambda n: n.endswith("name"))
    attendance = pick(ATTENDANCE_ALIASES, lambda n: "attend" in n)

    subjects: list[str] = []
    ignored: list[str] = []
    for c in cols:
        if c in taken:
            continue
        n = norms[c]
        if n in IGNORED_ALIASES or n.startswith(("total", "grand")):
            ignored.append(c)
            continue
        non_empty = int((~_blank_mask(df[c])).sum())
        numeric = int(_to_numeric(df[c]).notna().sum())
        if non_empty > 0 and numeric / non_empty >= 0.6:
            subjects.append(c)
        else:
            ignored.append(c)
    return {"roll_no": roll, "name": name, "attendance": attendance, "subjects": subjects, "ignored": ignored}


def parse_mapping(raw: Optional[str]) -> Optional[dict]:
    if raw is None or not str(raw).strip():
        return None
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        raise ProcessingError("INVALID_MAPPING", "The column mapping is not valid JSON.")
    if not isinstance(data, dict):
        raise ProcessingError("INVALID_MAPPING", "The column mapping must be an object.")
    out: dict = {}
    for key in ("roll_no", "name", "attendance"):
        v = data.get(key)
        if v is not None and not isinstance(v, str):
            raise ProcessingError("INVALID_MAPPING", f"Mapping field '{key}' must be a column name or empty.")
        out[key] = v or None
    subs = data.get("subjects", [])
    if not isinstance(subs, list) or not all(isinstance(s, str) for s in subs):
        raise ProcessingError("INVALID_MAPPING", "Mapping field 'subjects' must be a list of column names.")
    out["subjects"] = subs
    return out


def _apply_mapping(df: pd.DataFrame, mapping: dict) -> dict:
    chosen = [mapping[k] for k in ("roll_no", "name", "attendance") if mapping.get(k)] + list(mapping["subjects"])
    unknown = [c for c in chosen if c not in set(df.columns)]
    if unknown:
        raise ProcessingError("INVALID_MAPPING", f"Mapped column(s) not found in the file: {', '.join(unknown)}.")
    repeated = [c for c, n in Counter(chosen).items() if n > 1]
    if repeated:
        raise ProcessingError("INVALID_MAPPING", f"Each column can only be used once. Repeated: {', '.join(repeated)}.")
    if not mapping["subjects"]:
        raise ProcessingError("INVALID_MAPPING", "Select at least one subject column.")
    if not mapping.get("roll_no") and not mapping.get("name"):
        raise ProcessingError("INVALID_MAPPING", "Select a roll number column or a student name column.")
    return {
        "roll_no": mapping.get("roll_no"),
        "name": mapping.get("name"),
        "attendance": mapping.get("attendance"),
        "subjects": list(mapping["subjects"]),
        "ignored": [c for c in df.columns if c not in chosen],
    }


# --------------------------------------------------------------------------- #
# Cleaning and classification
# --------------------------------------------------------------------------- #
def validate_thresholds(advanced: Any, attention: Any) -> tuple[float, float]:
    try:
        adv, att = float(advanced), float(attention)
    except (TypeError, ValueError):
        raise ProcessingError("INVALID_THRESHOLDS", "Thresholds must be numbers.")
    if not (math.isfinite(adv) and math.isfinite(att)) or not (0 <= att < adv <= 100):
        raise ProcessingError(
            "INVALID_THRESHOLDS",
            "Thresholds must satisfy: 0 ≤ Needs Attention limit < Advanced limit ≤ 100.",
        )
    return adv, att


def classify(percentage: Optional[float], advanced: float, attention: float) -> str:
    if percentage is None:
        return NO_DATA
    if percentage >= advanced:
        return ADVANCED
    if percentage >= attention:
        return AVERAGE
    return NEEDS_ATTENTION


def _clean_marks(series: pd.Series) -> tuple[pd.Series, int]:
    """Numeric marks in 0..MAX_MARKS. Returns (clean series, count of invalid entries)."""
    blank = _blank_mask(series)
    numeric = _to_numeric(series)
    invalid = ~blank & (numeric.isna() | (numeric < 0) | (numeric > MAX_MARKS))
    cleaned = numeric.where(~blank & ~invalid)
    return cleaned.astype(float), int(invalid.sum())


def _clean_attendance(series: pd.Series) -> tuple[pd.Series, int]:
    blank = _blank_mask(series)
    numeric = _to_numeric(series).where(~blank)
    present = numeric.dropna()
    if len(present) and present.max() <= 1.0:  # Excel percentage cells arrive as fractions
        numeric = numeric * 100
    invalid = ~blank & (numeric.isna() | (numeric < 0) | (numeric > 100))
    return numeric.where(~blank & ~invalid).astype(float), int(invalid.sum())


# --------------------------------------------------------------------------- #
# Main entry point
# --------------------------------------------------------------------------- #
def analyze_dataset(
    content: bytes,
    filename: str,
    advanced: Any = DEFAULT_ADVANCED,
    attention: Any = DEFAULT_ATTENTION,
    mapping: Optional[dict] = None,
) -> dict:
    adv, att = validate_thresholds(advanced, attention)
    df, warnings = read_table(content, filename)
    available = list(df.columns)

    if mapping is None:
        cols = detect_columns(df)
        problems = []
        if not cols["roll_no"] and not cols["name"]:
            problems.append("a roll number or student name column")
        if not cols["subjects"]:
            problems.append("any numeric subject-marks columns")
        if problems:
            raise ProcessingError(
                "COLUMN_DETECTION_FAILED",
                "PRISM could not detect " + " or ".join(problems) + ". Rename your headers "
                "(for example 'Roll No', 'Name', 'Attendance') or map the columns manually.",
                422,
                {"columns": available, "detected": cols},
            )
    else:
        cols = _apply_mapping(df, mapping)

    subjects: list[str] = cols["subjects"]
    n_rows = len(df)
    ids = _clean_text(df[cols["roll_no"]]) if cols["roll_no"] else pd.Series([""] * n_rows, index=df.index)
    names = _clean_text(df[cols["name"]]) if cols["name"] else pd.Series([""] * n_rows, index=df.index)

    keep = (ids != "") | (names != "")
    if int((~keep).sum()):
        warnings.append(f"Skipped {int((~keep).sum())} row(s) that had no roll number and no name.")
    df, ids, names = df[keep], ids[keep], names[keep]
    if df.empty:
        raise ProcessingError("NO_STUDENT_ROWS", "No student rows were found in the selected columns.")

    marks = pd.DataFrame(index=df.index)
    for s in subjects:
        marks[s], invalid = _clean_marks(df[s])
        if invalid:
            warnings.append(
                f"Subject '{s}': {invalid} invalid mark(s) (non-numeric or outside 0–100) were ignored."
            )

    attendance = pd.Series(np.nan, index=df.index, dtype=float)
    if cols["attendance"]:
        attendance, bad = _clean_attendance(df[cols["attendance"]])
        if bad:
            warnings.append(f"Attendance: {bad} invalid value(s) (non-numeric or outside 0–100) were ignored.")

    work = pd.concat([ids.rename("__roll"), names.rename("__name"), marks, attendance.rename("__att")], axis=1)
    dup = work.duplicated(keep="first")
    if int(dup.sum()):
        warnings.append(f"Removed {int(dup.sum())} exact duplicate row(s).")
        work = work[~dup]
        marks, attendance = marks.loc[work.index], attendance.loc[work.index]
    rolls = work.loc[work["__roll"] != "", "__roll"]
    repeated_rolls = rolls[rolls.duplicated()].unique().tolist()
    if repeated_rolls:
        shown = ", ".join(repeated_rolls[:5]) + ("…" if len(repeated_rolls) > 5 else "")
        warnings.append(f"{len(repeated_rolls)} roll number(s) appear more than once: {shown}.")

    avg = marks.mean(axis=1)  # NaN when a student has no valid marks at all
    pct_series = (avg / MAX_MARKS * 100).round(2)
    marks_arr = marks.to_numpy(dtype=float)
    missing_counts = marks.isna().sum(axis=1).tolist()
    if sum(1 for m in missing_counts if m):
        warnings.append(
            f"{sum(1 for m in missing_counts if m)} student(s) have missing marks; "
            "their averages use the available subjects only."
        )

    students = []
    for i, idx in enumerate(work.index):
        pct = _num(pct_series.at[idx])
        students.append(
            {
                "roll_no": work.at[idx, "__roll"],
                "name": work.at[idx, "__name"],
                "marks": {s: _num(marks_arr[i, j]) for j, s in enumerate(subjects)},
                "average": _num(avg.at[idx]),
                "percentage": pct,
                "attendance": _num(attendance.at[idx]),
                "classification": classify(pct, adv, att),
                "missing_subjects": int(missing_counts[i]),
            }
        )

    subject_stats = []
    for s in subjects:
        valid = marks[s].dropna()
        if valid.empty:
            warnings.append(f"Subject '{s}' has no valid marks.")
        subject_stats.append(
            {
                "subject": s,
                "average": _num(valid.mean()) if len(valid) else None,
                "highest": _num(valid.max()) if len(valid) else None,
                "lowest": _num(valid.min()) if len(valid) else None,
                "count": int(len(valid)),
            }
        )

    evaluated = [s for s in students if s["percentage"] is not None]
    att_valid = [s["attendance"] for s in students if s["attendance"] is not None]

    def extreme(fn) -> Optional[dict]:
        if not evaluated:
            return None
        s = fn(evaluated, key=lambda x: x["percentage"])
        return {"value": s["percentage"], "name": s["name"], "roll_no": s["roll_no"]}

    summary = {
        "total_students": len(students),
        "evaluated_students": len(evaluated),
        "class_average": _num(np.mean([s["percentage"] for s in evaluated])) if evaluated else None,
        "highest": extreme(max),
        "lowest": extreme(min),
        "attendance_average": _num(np.mean(att_valid)) if att_valid else None,
        "attendance_count": len(att_valid),
    }
    counts = Counter(s["classification"] for s in students)
    distribution = {c: int(counts.get(c, 0)) for c in CLASSIFICATIONS}

    return {
        "filename": filename,
        "max_marks": MAX_MARKS,
        "thresholds": {"advanced": adv, "attention": att},
        "columns": {
            "roll_no": cols["roll_no"],
            "name": cols["name"],
            "attendance": cols["attendance"],
            "subjects": subjects,
            "ignored": cols["ignored"],
        },
        "available_columns": available,
        "students": students,
        "subject_stats": subject_stats,
        "summary": summary,
        "distribution": distribution,
        "warnings": warnings,
    }
