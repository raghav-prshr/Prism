import { useCallback, useState } from "react";
import {
  AlertCircle, CheckCircle2, Download, LayoutDashboard, Loader2, Triangle, UploadCloud, Users, X,
} from "lucide-react";
import { ApiError, analyzeFile, exportWorkbook } from "./api";
import { MAX_UPLOAD_BYTES } from "./constants";
import type { Analysis, ColumnMapping, Thresholds } from "./types";
import UploadPanel from "./components/UploadPanel";
import MappingForm from "./components/MappingForm";
import Dashboard from "./components/Dashboard";
import StudentsTable from "./components/StudentsTable";

type View = "upload" | "dashboard" | "students";

const DEFAULT_THRESHOLDS: Thresholds = { advanced: 75, attention: 40 };
const TITLES: Record<View, string> = {
  upload: "Upload dataset",
  dashboard: "Class dashboard",
  students: "Student records",
};

function toApiError(e: unknown): ApiError {
  if (e instanceof ApiError) return e;
  return new ApiError({ code: "UNKNOWN", message: e instanceof Error ? e.message : "Something went wrong." });
}

export default function App() {
  const [view, setView] = useState<View>("upload");
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [source, setSource] = useState<File | null>(null); // file behind the current analysis
  const [pending, setPending] = useState<File | null>(null); // file whose upload needs a manual mapping
  const [mapping, setMapping] = useState<ColumnMapping | null>(null);
  const [thresholds, setThresholds] = useState<Thresholds>(DEFAULT_THRESHOLDS);
  const [busy, setBusy] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const run = useCallback(
    async (file: File, m: ColumnMapping | null, t: Thresholds, message: string, opensDashboard: boolean) => {
      setBusy(true);
      setError(null);
      setNotice(null);
      try {
        const result = await analyzeFile(file, t, m);
        setAnalysis(result);
        setSource(file);
        setPending(null);
        setMapping(m);
        setThresholds(result.thresholds);
        setNotice(message.replace("{n}", String(result.summary.total_students)));
        if (opensDashboard) setView("dashboard");
      } catch (e) {
        setError(toApiError(e));
      } finally {
        setBusy(false);
      }
    },
    [],
  );

  const handleFile = (file: File) => {
    if (!/\.(csv|xls|xlsx)$/i.test(file.name)) {
      setNotice(null);
      setError(new ApiError({ code: "CLIENT_VALIDATION", message: "Unsupported file type. Please upload a .csv, .xls or .xlsx file." }));
      return;
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      setNotice(null);
      setError(new ApiError({ code: "CLIENT_VALIDATION", message: "The file is larger than the 15 MB limit." }));
      return;
    }
    setPending(file);
    void run(file, null, thresholds, `Uploaded ${file.name}: {n} student(s) analysed.`, true);
  };

  const applyThresholds = (t: Thresholds) => {
    if (source) void run(source, mapping, t, "Thresholds updated.", false);
  };

  const applyMapping = (m: ColumnMapping) => {
    const file = pending ?? source;
    if (file) void run(file, m, thresholds, "Column mapping applied: {n} student(s) analysed.", true);
  };

  const download = async () => {
    if (!source) return;
    setExporting(true);
    setError(null);
    try {
      const blob = await exportWorkbook(source, thresholds, mapping);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `PRISM_${source.name.replace(/\.[^.]+$/, "").replace(/[^\w-]+/g, "_")}_processed.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(toApiError(e));
    } finally {
      setExporting(false);
    }
  };

  const needsMapping = error?.code === "COLUMN_DETECTION_FAILED" && error.columns && pending;
  const nav: { id: View; label: string; icon: typeof Users; disabled: boolean }[] = [
    { id: "upload", label: "Upload", icon: UploadCloud, disabled: false },
    { id: "dashboard", label: "Dashboard", icon: LayoutDashboard, disabled: !analysis },
    { id: "students", label: "Students", icon: Users, disabled: !analysis },
  ];

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="brand">
          <span className="logo">
            <img
              src="/hawk-logo.svg"
              alt="PRISM Hawk"
              className="hawk-logo"
            />
          </span>
          <div>
            <strong>PRISM</strong>
            <small>Performance Recognition &amp; Insight System for Monitoring</small>
          </div>
        </div>
        <nav>
          {nav.map(({ id, label, icon: Icon, disabled }) => (
            <button key={id} className={`nav-item${view === id ? " active" : ""}`} disabled={disabled} onClick={() => setView(id)}>
              <Icon size={18} /> {label}
            </button>
          ))}
        </nav>
        <p className="privacy">Uploads are processed per request and are not saved as permanent records.</p>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <h1>{TITLES[view]}</h1>
            {analysis && view !== "upload" && <span className="muted">{analysis.filename}</span>}
          </div>
          {analysis && (
            <button className="btn primary" onClick={() => void download()} disabled={exporting || busy}>
              {exporting ? <Loader2 className="spin" size={16} /> : <Download size={16} />} Download Excel
            </button>
          )}
        </header>

        {error && (
          <div className="banner error" role="alert">
            <AlertCircle size={18} />
            <span>{error.message}</span>
            <button className="icon-btn" aria-label="Dismiss" onClick={() => setError(null)}>
              <X size={16} />
            </button>
          </div>
        )}
        {notice && !error && (
          <div className="banner success" role="status">
            <CheckCircle2 size={18} />
            <span>{notice}</span>
            <button className="icon-btn" aria-label="Dismiss" onClick={() => setNotice(null)}>
              <X size={16} />
            </button>
          </div>
        )}

        {view === "upload" && (
          <div className="stack">
            <UploadPanel busy={busy} onFile={handleFile} />
            {needsMapping && error?.columns && pending && (
              <section className="card">
                <h3>Map your columns</h3>
                <p className="muted">
                  Automatic detection did not work for <b>{pending.name}</b>. Choose which columns hold the roll number, name,
                  attendance and subject marks.
                </p>
                <MappingForm
                  columns={error.columns}
                  initial={{
                    roll_no: error.detected?.roll_no ?? null,
                    name: error.detected?.name ?? null,
                    attendance: error.detected?.attendance ?? null,
                    subjects: error.detected?.subjects ?? [],
                  }}
                  busy={busy}
                  submitLabel="Analyse with this mapping"
                  onSubmit={applyMapping}
                />
              </section>
            )}
            {analysis && (
              <section className="card">
                <p>
                  Currently loaded: <b>{analysis.filename}</b> ({analysis.summary.total_students} students).{" "}
                  <button className="link" onClick={() => setView("dashboard")}>
                    Open dashboard
                  </button>
                </p>
              </section>
            )}
          </div>
        )}

        {view === "dashboard" && analysis && (
          <Dashboard analysis={analysis} busy={busy} onApplyThresholds={applyThresholds} onApplyMapping={applyMapping} />
        )}
        {view === "students" && analysis && <StudentsTable analysis={analysis} />}

        {!analysis && view !== "upload" && (
          <div className="card empty">Upload a dataset first to see analytics.</div>
        )}
      </main>
    </div>
  );
}
