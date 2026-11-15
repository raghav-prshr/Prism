# PRISM – Performance Recognition & Insight System for Monitoring

PRISM is a dataset-driven student performance analytics platform. A teacher uploads a CSV, XLS or XLSX file of
student marks; the backend detects the columns, cleans the data, calculates performance and returns JSON; the React
dashboard shows KPIs, charts and a searchable student table, and the teacher can download a formatted Excel workbook.

* Nothing is hardcoded: every number on screen comes from the file currently uploaded.
* Uploads are processed per request and are not saved as permanent application records. The web framework may temporarily buffer multipart uploads. No database is used and no credentials are needed.
* Classification is **threshold-based (rule-based)**. It is not machine learning and makes no predictions.

---

## 1. Architecture

```
Browser (React + Vite + TypeScript, Recharts)
   │  multipart/form-data  (file, thresholds, optional column mapping)
   ▼
FastAPI  ──  app/main.py        routes, CORS, size limit, error → JSON
             app/processing.py  read → detect columns → clean → calculate → classify   (pandas / NumPy)
             app/exporter.py    builds the .xlsx workbook                              (openpyxl)
```

The API is **stateless**. When the teacher changes thresholds, remaps columns or downloads the workbook, the browser
re-sends the file it still holds in memory, and the server recalculates. PRISM does not retain a permanent copy of the upload.

```
Prism/
├── README.md  .gitignore
├── backend/   requirements.txt  .env.example  .python-version
│   ├── app/   __init__.py  main.py  processing.py  exporter.py
│   └── tests/ test_processing.py
├── frontend/  package.json  index.html  vite.config.ts  tsconfig.json  vercel.json  .env.example
│   └── src/   main.tsx  App.tsx  api.ts  types.ts  constants.ts  styles.css  vite-env.d.ts
│              components/ UploadPanel  MappingForm  Dashboard  StudentsTable
└── sample-data/  PRISM_sample_class_dataset.xlsx  generate_sample.py
```

## 2. Installation on Fedora Linux

```bash
sudo dnf install -y python3 python3-pip nodejs npm git unzip
unzip Prism.zip && cd Prism
python3 --version   # 3.10–3.13 recommended
node --version      # 18 or newer
```

> If your Fedora ships a very new Python (e.g. 3.14) and `pip install` fails building pandas/numpy, install an
> older interpreter (`sudo dnf install python3.12`) and create the virtual environment with `python3.12 -m venv .venv`.

## 3. Backend setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # optional; defaults already allow http://localhost:5173
uvicorn app.main:app --reload --port 8000
```

Check it: <http://localhost:8000/api/health> returns `{"status":"ok"}`; interactive API docs are at `/docs`.
`.env` is not auto-loaded by uvicorn – to use it locally run `set -a; source .env; set +a` first, or export the variables.

Run the backend tests (no server needed):

```bash
cd backend && python -m unittest discover -s tests -v
```

## 4. Frontend setup

```bash
cd frontend
cp .env.example .env            # VITE_API_URL=http://localhost:8000
npm install
npm run dev                     # http://localhost:5173
npm run build                   # type-checks (tsc) and builds to dist/
```

## 5. How the API works

| Method | Path           | Purpose                                                        |
|--------|----------------|----------------------------------------------------------------|
| GET    | `/api/health`  | Liveness check                                                 |
| POST   | `/api/analyze` | Upload a file, receive analytics as JSON                       |
| POST   | `/api/export`  | Same inputs, returns a real `.xlsx` workbook                   |

Both POST endpoints take `multipart/form-data`:

| Field                 | Required | Default | Meaning                                                                    |
|-----------------------|----------|---------|----------------------------------------------------------------------------|
| `file`                | yes      |         | `.csv`, `.xls` or `.xlsx`, max 15 MB                                       |
| `advanced_threshold`  | no       | 75      | percentage ≥ this → **Advanced**                                           |
| `attention_threshold` | no       | 40      | percentage ≥ this → **Average**; below → **Needs Attention**               |
| `mapping`             | no       |         | JSON `{"roll_no":"…","name":"…","attendance":"…"|null,"subjects":["…"]}`   |

```bash
curl -F "file=@sample-data/PRISM_sample_class_dataset.xlsx" -F advanced_threshold=80 \
     http://localhost:8000/api/analyze | python3 -m json.tool | head -40
curl -F "file=@sample-data/PRISM_sample_class_dataset.xlsx" http://localhost:8000/api/export -o out.xlsx
```

`/api/analyze` returns `filename`, `thresholds`, `columns` (what was detected / ignored), `available_columns`,
`students[]` (marks per subject, average, percentage, attendance, classification), `subject_stats[]`
(average / highest / lowest per subject), `summary` (total students, class average, highest and lowest percentage,
attendance average), `distribution` and `warnings[]`.

Errors use `{"detail": {"code": "...", "message": "..."}}`. When automatic detection fails the response is HTTP 422 with
code `COLUMN_DETECTION_FAILED` plus `columns` and `detected`; the frontend then shows the manual mapping form.
Other codes: `UNSUPPORTED_FILE_TYPE`, `FILE_TOO_LARGE`, `EMPTY_FILE`, `UNREADABLE_FILE`, `NO_DATA_ROWS`,
`INVALID_THRESHOLDS`, `INVALID_MAPPING`, `INTERNAL_ERROR`.

### Data rules

* **Detection:** Roll No / Roll Number / Student ID / Registration Number…, Name / Student Name / Full Name…,
  Attendance / Attendance % / Attendance Percentage…; every other column that is mostly numeric becomes a subject.
  Serial-number, total, average, percentage, rank, grade, etc. columns are ignored.
* **Cleaning:** a title row above the header is skipped; duplicate headers are renamed (`Maths`, `Maths (2)`);
  blank/`AB`/`NA` marks are treated as missing; text or values outside 0–100 are invalid and ignored (reported in
  *Data notes*); `85%` and Excel percentage cells (0.85) are understood for attendance; rows with neither roll number
  nor name and exact duplicate rows are dropped; repeated roll numbers are kept but flagged.
* **Calculation:** marks are assumed to be out of 100. A student's average is the mean of their valid subjects (so
  percentage = average). Students with no valid marks are classified **No Data**.
* **Export:** sheet *Student Performance* (roll no, name, every subject, attendance, average, percentage,
  classification) and sheet *Summary* (class stats, thresholds, distribution, subject stats). Values are written as
  numbers; text that starts with `=` is stored as text, so a malicious cell cannot become a formula.

## 6. How to upload a dataset

1. Open the app and go to **Upload**.
2. Drop a `.csv`, `.xls` or `.xlsx` file (try `sample-data/PRISM_sample_class_dataset.xlsx`).
3. The dashboard opens. Use **Classification thresholds** to change the limits and press *Apply*.
4. Open **Students** to search by name/roll number and filter by classification.
5. Press **Download Excel** for the processed workbook.
6. If columns were not recognised, choose them in the *Map your columns* form. You can also review or change the
   mapping later under *Detected columns & manual mapping* on the dashboard.

The sample file contains **synthetic** data (66 randomly generated students). It is for demonstration only and is not
real academic results. Regenerate it with `python sample-data/generate_sample.py`.

## 7. Deploy the backend on Render

1. Push the project to GitHub. In Render choose **New → Web Service** and select the repository.
2. **Root Directory:** `backend`  ·  **Runtime:** Python
3. **Build Command:** `pip install -r requirements.txt`
4. **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. **Environment variables:** `PYTHON_VERSION=3.12.3` (matches `backend/.python-version`) and
   `CORS_ORIGINS=https://your-prism-app.vercel.app` (set after the frontend is deployed).
6. Deploy and open `https://YOUR-RENDER-BACKEND-URL/api/health`.

Free instances sleep when idle, so the first request after a pause can take up to a minute.

## 8. Deploy the frontend on Vercel

1. In Vercel choose **Add New → Project** and import the repository.
2. **Root Directory:** `frontend`. Vercel detects Vite; `vercel.json` already sets the build command (`npm run build`)
   and output directory (`dist`).
3. **Environment variable:** `VITE_API_URL=https://YOUR-RENDER-BACKEND-URL` (no trailing slash).
4. Deploy, then copy the Vercel URL into Render's `CORS_ORIGINS` and restart the Render service.

## 9. Environment variables

| Where    | Variable          | Example                                   | Notes                                                           |
|----------|-------------------|-------------------------------------------|-----------------------------------------------------------------|
| Backend  | `CORS_ORIGINS`    | `https://your-prism-app.vercel.app`       | Comma-separated, no trailing slash. Default: localhost:5173     |
| Backend  | `CORS_ORIGIN_REGEX` | `https://your-prism-app-.*\.vercel\.app` | Optional, for Vercel preview URLs                               |
| Backend  | `PYTHON_VERSION`  | `3.12.3`                                  | Render only                                                     |
| Frontend | `VITE_API_URL`    | `https://YOUR-RENDER-BACKEND-URL`         | Baked in at build time; rebuild after changing it               |

No database credentials, API keys or secrets are used anywhere. Any existing PostgreSQL database is never touched.

---

## Testing status (honest report)

The project was built and checked in a sandbox **without internet access**, which limited what could be run.

**Verified**

* Python syntax of every backend file (`py_compile`).
* 13 backend unit tests pass (`backend/tests`): CSV (comma/semicolon/BOM/Latin-1) and XLSX parsing, auto-detection,
  title rows, duplicate headers, missing/invalid marks, fraction attendance, duplicate rows, threshold boundaries and
  changes, manual mapping and its errors, empty/oversized/unsupported/corrupt files, JSON without NaN, the 66-student
  sample dataset, XLSX export (structure, values, formatting, round-trip, formula-injection safety).
* The handler logic in `main.py` (analyze, export, error codes, CORS origin parsing) was exercised through small
  stand-ins for FastAPI, because FastAPI could not be installed offline.
* TypeScript sources type-check cleanly against hand-written minimal type stubs, and every field in `types.ts` matches
  the JSON the backend really returns.

**Not verified here – please run these once on your machine**

* `pip install -r requirements.txt` and a live `uvicorn` server (real FastAPI routing, multipart parsing, CORS headers).
* **Legacy `.xls` reading** (needs `xlrd`, which was not installable here). The code path is implemented but untested.
* `npm install`, `npm run build` and the Vite bundle, because React, Recharts and Lucide could not be downloaded, so the
  type-check above used stubs rather than the real library typings.
* Visual rendering and responsiveness in a browser.
* No `package-lock.json` is included (it needs network access); `npm install` generates one.
* Tested with pandas 3.0 / NumPy 2.5 / openpyxl 3.1; `requirements.txt` allows pandas 2.2+ but 2.x was not run.

Suggested first run: backend tests → start backend → `npm install && npm run build` → upload the sample file.

## Limitations of this MVP

* Marks are assumed to be out of 100; other scales are flagged as invalid.
* Only the first sheet of a workbook is read.
* Because PRISM does not persist uploaded datasets or analysis history, refreshing the page clears the dashboard.
* Very large files are limited by the host's memory (Render's free tier has 512 MB).
