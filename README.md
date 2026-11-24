# PRISM
### Performance Recognition & Insight System for Monitoring

**A student performance analytics platform that turns academic datasets into actionable insights.**

PRISM helps teachers analyse student performance by uploading CSV or Excel datasets. It automatically detects relevant columns, processes academic records, calculates performance metrics and classifies students using configurable thresholds.

[**Live Demo**](https://prism-iota-lime.vercel.app/) · [**GitHub Repository**](https://github.com/raghav-prshr/Prism)

---

## Overview

Teachers often receive academic records in different spreadsheet formats. Analysing these records manually takes time and makes it difficult to identify students who need additional attention.

PRISM simplifies this process by converting uploaded academic datasets into an interactive dashboard with student-level and subject-level insights.

## Features

- **Flexible Dataset Upload:** Supports CSV, XLS and XLSX files.
- **Automatic Column Detection:** Identifies student names, roll numbers, attendance and subject marks.
- **Data Cleaning:** Handles missing values, duplicate records, invalid marks and inconsistent column headers.
- **Manual Column Mapping:** Allows teachers to map columns when automatic detection fails.
- **Performance Classification:** Classifies students as Advanced, Average, Needs Attention or No Data.
- **Configurable Thresholds:** Teachers can adjust classification criteria.
- **Interactive Dashboard:** Displays class statistics, subject averages and classification distribution.
- **Student Records:** Search and filter students by their performance classification.
- **Excel Export:** Downloads processed student records and class summaries in an Excel workbook.

## Technology Stack

| Component | Technologies |
|---|---|
| Frontend | React, TypeScript, Vite |
| UI & Charts | CSS, Recharts, Lucide React |
| Backend | Python, FastAPI |
| Data Processing | Pandas, NumPy |
| Excel Processing | OpenPyXL, xlrd |
| Deployment | Vercel, Render |

## System Architecture

```text
        TEACHER
           |
           v
    Upload CSV / Excel
           |
           v
   REACT FRONTEND
           |
           | Multipart Form Data
           v
      FASTAPI BACKEND
           |
           v
     DATA PROCESSING
           |
     +-----+------+
     |            |
     v            v
 Column         Data
 Detection     Cleaning
     |            |
     +-----+------+
           |
           v
   PERFORMANCE CALCULATION
           |
           v
   RULE-BASED CLASSIFICATION
           |
           v
      JSON RESPONSE
           |
           v
   REACT DASHBOARD
           |
     +-----+------+
     |            |
     v            v
  Analytics    Excel Export
  & Records
```

## How It Works

### 1. Dataset Upload

The teacher uploads a CSV, XLS or XLSX file containing student academic records.

### 2. Column Detection

The backend identifies relevant columns using predefined aliases and fuzzy matching.

It recognises common variations such as:
- Roll No, Roll Number, Student ID
- Name, Student Name, Full Name
- Attendance, Attendance Percentage

Numeric columns are evaluated to identify potential subject marks.

### 3. Data Cleaning

Pandas processes the uploaded dataset.

The system handles:
- Missing and invalid marks.
- Duplicate column names.
- Empty student records.
- Duplicate rows.
- Invalid values outside the 0–100 marks range.

Data quality warnings are returned to the dashboard.

### 4. Performance Calculation

PRISM calculates each student's average using their available valid subject marks.

**Formula:**

```text
Student Average =
Sum of Valid Subject Marks
--------------------------
Number of Valid Subjects
```

Since marks are assumed to be out of 100:

```text
Percentage = Student Average
```

### 5. Performance Classification

PRISM uses configurable, threshold-based classification.

Default thresholds:

| Classification | Condition |
|---|---|
| Advanced | Percentage ≥ 75 |
| Average | Percentage ≥ 40 and below 75 |
| Needs Attention | Percentage below 40 |
| No Data | No valid subject marks |

These thresholds can be changed by the teacher.

**Note:** Classification uses rule-based logic, not machine learning.

### 6. Dashboard & Export

The frontend displays class statistics, subject-wise performance, classification distribution and searchable student records.

Teachers can also download a formatted Excel workbook containing two sheets:

- Student Performance
- Summary

## Project Structure

```text
Prism/
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── processing.py
│   │   └── exporter.py
│   ├── tests/
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── App.tsx
│   │   ├── api.ts
│   │   ├── types.ts
│   │   └── styles.css
│   ├── package.json
│   └── vercel.json
│
├── sample-data/
│   ├── PRISM_sample_class_dataset.xlsx
│   └── generate_sample.py
│
├── .gitignore
├── LICENSE
└── README.md
```

## Getting Started

### Prerequisites

- Python 3.12 recommended
- Node.js 18 or newer
- npm
- Git

### 1. Clone the Repository

```bash
git clone https://github.com/raghav-prshr/Prism.git
cd Prism
```

### 2. Start the Backend

```bash
cd backend

python -m venv .venv
```

Activate the virtual environment.

**Linux / macOS:**

```bash
source .venv/bin/activate
```

**Windows:**

```bash
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Start the FastAPI server:

```bash
uvicorn app.main:app --reload --port 8000
```

Backend API: `http://localhost:8000`

API documentation: `http://localhost:8000/docs`

### 3. Start the Frontend

Open another terminal:

```bash
cd Prism/frontend
```

Create the local environment file:

```bash
cp .env.example .env
```

Install dependencies and start the application:

```bash
npm install
npm run dev
```

Frontend: `http://localhost:5173`

For Windows PowerShell, copy `.env.example` to `.env` using:

```powershell
Copy-Item .env.example .env
```

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/health` | Backend health check |
| POST | `/api/analyze` | Analyses uploaded datasets |
| POST | `/api/export` | Generates an Excel workbook |

The analysis and export endpoints accept multipart form data.

Supported parameters include:

- `file`: Uploaded dataset.
- `advanced_threshold`: Advanced classification limit.
- `attention_threshold`: Needs Attention classification limit.
- `mapping`: Optional manual column mapping in JSON format.

Maximum upload size: 15 MB.

## Testing

Backend unit tests are included in `backend/tests`.

Run them using:

```bash
cd backend
python -m unittest discover -s tests -v
```

Build the frontend using:

```bash
cd frontend
npm run build
```

## Deployment

PRISM uses separate deployment services:

- **Frontend:** Vercel
- **Backend:** Render

The frontend communicates with the backend through the `VITE_API_URL` environment variable.

The backend uses `CORS_ORIGINS` to configure permitted frontend origins.

See the environment examples in the respective directories before deploying.

## Data Handling & Privacy

- Uploaded datasets are processed in memory for each request.
- PRISM does not maintain a database or permanent upload history.
- The backend does not require API keys or database credentials.
- The frontend retains the current uploaded file in browser memory while the analysis is active.
- Refreshing the application clears the current dashboard session.

The hosting provider may temporarily buffer incoming requests.

## Current Limitations

- Marks are assumed to be on a 0–100 scale.
- Only the first worksheet of an Excel workbook is processed.
- Uploaded datasets and analysis history are not permanently stored.
- Large datasets are subject to available hosting memory and processing capacity.

## License

This project is licensed under the [MIT License](LICENSE).

---

**PRISM – Performance Recognition & Insight System for Monitoring**