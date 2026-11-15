"""Run from the backend folder:  python -m unittest discover -s tests -v"""
import io
import os
import unittest

from openpyxl import Workbook, load_workbook

from app import processing as P
from app.exporter import build_workbook

SAMPLE = os.path.join(os.path.dirname(__file__), "..", "..", "sample-data", "PRISM_sample_class_dataset.xlsx")


def make_xlsx(rows):
    wb = Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


CSV = (b"Roll Number,Student Name,Maths,Physics,Attendance %\n"
       b"1,Asha,90,80,95%\n2,Ben,50,60,80%\n3,Cara,20,30,60%\n")


class CsvTests(unittest.TestCase):
    def test_basic_csv(self):
        r = P.analyze_dataset(CSV, "class.csv")
        self.assertEqual(r["columns"]["subjects"], ["Maths", "Physics"])
        self.assertEqual(r["columns"]["roll_no"], "Roll Number")
        self.assertEqual(r["columns"]["attendance"], "Attendance %")
        self.assertEqual(r["summary"]["total_students"], 3)
        self.assertEqual([s["percentage"] for s in r["students"]], [85.0, 55.0, 25.0])
        self.assertEqual([s["classification"] for s in r["students"]], ["Advanced", "Average", "Needs Attention"])
        self.assertEqual(r["summary"]["class_average"], 55.0)
        self.assertEqual(r["summary"]["attendance_average"], 78.33)
        self.assertEqual(r["summary"]["highest"]["name"], "Asha")
        self.assertEqual(r["summary"]["lowest"]["name"], "Cara")
        self.assertEqual(r["subject_stats"][0], {"subject": "Maths", "average": 53.33, "highest": 90.0, "lowest": 20.0, "count": 3})

    def test_semicolon_and_bom_and_latin1(self):
        data = "\ufeffRoll No;Name;Maths\n1;José;70\n".encode("utf-8")
        self.assertEqual(P.analyze_dataset(data, "a.csv")["students"][0]["name"], "José")
        data = "Roll No;Name;Maths\n1;Jos\xe9;70\n".encode("latin-1")
        self.assertEqual(P.analyze_dataset(data, "a.csv")["students"][0]["name"], "José")

    def test_threshold_boundaries_and_change(self):
        csv = b"Roll No,Name,M\n1,A,75\n2,B,40\n3,C,39.99\n"
        r = P.analyze_dataset(csv, "t.csv")
        self.assertEqual([s["classification"] for s in r["students"]], ["Advanced", "Average", "Needs Attention"])
        r = P.analyze_dataset(csv, "t.csv", advanced=80, attention=50)
        self.assertEqual([s["classification"] for s in r["students"]], ["Average", "Needs Attention", "Needs Attention"])
        self.assertEqual(r["distribution"]["Needs Attention"], 2)

    def test_invalid_thresholds(self):
        for a, b in [(40, 75), (75, 75), (101, 40), (75, -1), ("x", 40)]:
            with self.assertRaises(P.ProcessingError) as cm:
                P.analyze_dataset(CSV, "c.csv", a, b)
            self.assertEqual(cm.exception.code, "INVALID_THRESHOLDS")


class MessyDataTests(unittest.TestCase):
    def test_messy(self):
        rows = [["Class 12-A Marks"], [],
                ["Roll No", "Name", "Maths", "Maths", "Science", "Total", "Attendance"],
                [1, "Asha", 90, 80, "AB", 170, 0.95],
                [2, "Ben", "abc", 150, 70, 220, 0.5],
                [3, "Cara", None, None, None, None, None],
                [None, None, None, None, None, None, None],
                [2, "Dup Roll", 10, 10, 10, 30, 0.9],
                [4, "Asha2", 90, 80, 60, 230, 0.8],
                [4, "Asha2", 90, 80, 60, 230, 0.8],
                [None, None, 1, 2, 3, 6, None]]
        r = P.analyze_dataset(make_xlsx(rows), "m.xlsx")
        w = " | ".join(r["warnings"])
        self.assertIn("Skipped 1 row(s) above the header row", w)
        self.assertIn("Duplicate column name 'Maths'", w)
        self.assertIn("invalid mark", w)
        self.assertIn("exact duplicate", w)
        self.assertIn("appear more than once", w)
        self.assertIn("no roll number and no name", w)
        self.assertEqual(r["columns"]["subjects"], ["Maths", "Maths (2)", "Science"])
        self.assertIn("Total", r["columns"]["ignored"])
        by_name = {s["name"]: s for s in r["students"]}
        self.assertEqual(by_name["Asha"]["marks"]["Science"], None)        # "AB" -> missing
        self.assertEqual(by_name["Asha"]["average"], 85.0)                 # avg of available
        self.assertEqual(by_name["Asha"]["attendance"], 95.0)              # fraction -> %
        self.assertEqual(by_name["Ben"]["marks"]["Maths"], None)           # "abc" invalid
        self.assertEqual(by_name["Ben"]["marks"]["Maths (2)"], None)       # 150 out of range
        self.assertEqual(by_name["Ben"]["average"], 70.0)
        self.assertEqual(by_name["Cara"]["classification"], "No Data")
        self.assertEqual(r["distribution"]["No Data"], 1)
        self.assertEqual(len([s for s in r["students"] if s["name"] == "Asha2"]), 1)

    def test_no_nan_in_json(self):
        import json
        rows = [["Roll No", "Name", "M1", "M2"], [1, "A", None, None], [2, "B", 50, None]]
        r = P.analyze_dataset(make_xlsx(rows), "n.xlsx")
        json.dumps(r, allow_nan=False)  # raises on NaN/Infinity

    def test_numeric_roll_numbers_have_no_decimal(self):
        rows = [["Roll No", "Name", "M"], [101.0, "A", 50], [102, "B", 60]]
        r = P.analyze_dataset(make_xlsx(rows), "n.xlsx")
        self.assertEqual([s["roll_no"] for s in r["students"]], ["101", "102"])


class MappingAndErrorTests(unittest.TestCase):
    CSV = b"Reg,Pupil,Algebra,Geometry\nA1,Zed,60,70\nA2,Yan,80,90\n"

    def test_detection_failure_then_manual_mapping(self):
        with self.assertRaises(P.ProcessingError) as cm:
            P.analyze_dataset(self.CSV, "x.csv")
        e = cm.exception
        self.assertEqual((e.code, e.status), ("COLUMN_DETECTION_FAILED", 422))
        self.assertEqual(e.to_detail()["columns"], ["Reg", "Pupil", "Algebra", "Geometry"])
        mapping = P.parse_mapping('{"roll_no":"Reg","name":"Pupil","attendance":null,"subjects":["Algebra","Geometry"]}')
        r = P.analyze_dataset(self.CSV, "x.csv", mapping=mapping)
        self.assertEqual(r["students"][0]["name"], "Zed")
        self.assertEqual(r["students"][1]["percentage"], 85.0)
        self.assertIsNone(r["summary"]["attendance_average"])

    def test_bad_mappings(self):
        bad = [{"roll_no": "Nope", "name": None, "attendance": None, "subjects": ["Algebra"]},
               {"roll_no": "Reg", "name": None, "attendance": None, "subjects": ["Reg"]},
               {"roll_no": "Reg", "name": None, "attendance": None, "subjects": []},
               {"roll_no": None, "name": None, "attendance": None, "subjects": ["Algebra"]}]
        for m in bad:
            with self.assertRaises(P.ProcessingError) as cm:
                P.analyze_dataset(self.CSV, "x.csv", mapping=m)
            self.assertEqual(cm.exception.code, "INVALID_MAPPING")
        with self.assertRaises(P.ProcessingError):
            P.parse_mapping("{not json")

    def test_file_errors(self):
        cases = [(b"", "a.csv", "EMPTY_FILE"), (b"x", "a.txt", "UNSUPPORTED_FILE_TYPE"),
                 (b"not a zip", "a.xlsx", "UNREADABLE_FILE"), (b"Roll No,Name,M\n", "a.csv", "NO_DATA_ROWS"),
                 (b"a" * (P.MAX_UPLOAD_BYTES + 1), "a.csv", "FILE_TOO_LARGE")]
        for content, name, code in cases:
            with self.assertRaises(P.ProcessingError) as cm:
                P.analyze_dataset(content, name)
            self.assertEqual(cm.exception.code, code, name)


class SampleAndExportTests(unittest.TestCase):
    def test_sample_dataset_and_export(self):
        with open(SAMPLE, "rb") as f:
            content = f.read()
        r = P.analyze_dataset(content, "PRISM_sample_class_dataset.xlsx")
        self.assertEqual(r["summary"]["total_students"], 66)
        self.assertEqual(r["columns"]["subjects"], ["AICA", "FLAT", "DAA", "SDP", "CG", "QAPD"])
        self.assertEqual(r["columns"]["attendance"], "Attendance")
        self.assertEqual(r["warnings"], [])
        for k in ("Advanced", "Average", "Needs Attention"):
            self.assertGreater(r["distribution"][k], 0, k)
        for s in r["students"]:
            self.assertTrue(50 <= s["attendance"] <= 100)
            self.assertTrue(all(0 <= v <= 100 for v in s["marks"].values()))

        xlsx = build_workbook(r)
        self.assertTrue(xlsx.startswith(b"PK"))  # genuine zip-based XLSX
        wb = load_workbook(io.BytesIO(xlsx))
        self.assertEqual(wb.sheetnames, ["Student Performance", "Summary"])
        ws = wb["Student Performance"]
        self.assertEqual([c.value for c in ws[1]],
                         ["Roll No", "Name", "AICA", "FLAT", "DAA", "SDP", "CG", "QAPD",
                          "Attendance (%)", "Average", "Percentage (%)", "Classification"])
        self.assertEqual(ws.max_row, 67)
        first = r["students"][0]
        self.assertEqual(ws.cell(2, 1).value, first["roll_no"])
        self.assertEqual(ws.cell(2, 2).value, first["name"])
        self.assertEqual(ws.cell(2, 10).value, first["average"])
        self.assertEqual(ws.cell(2, 12).value, first["classification"])
        self.assertEqual(ws.freeze_panes, "C2")

    def test_export_roundtrip_through_analyzer(self):
        r = P.analyze_dataset(CSV, "c.csv")
        again = P.analyze_dataset(build_workbook(r), "out.xlsx")  # first sheet is re-readable
        self.assertEqual([s["percentage"] for s in again["students"]], [85.0, 55.0, 25.0])

    def test_formula_injection_is_stored_as_text(self):
        csv = b"Roll No,Name,M\n1,=HYPERLINK(\"http://x\"),50\n"
        r = P.analyze_dataset(csv, "i.csv")
        ws = load_workbook(io.BytesIO(build_workbook(r)))["Student Performance"]
        self.assertEqual(ws.cell(2, 2).data_type, "s")
        self.assertTrue(str(ws.cell(2, 2).value).startswith("=HYPERLINK"))


if __name__ == "__main__":
    unittest.main()
