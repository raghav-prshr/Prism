import { useState } from "react";
import type { ChangeEvent, DragEvent } from "react";
import { FileSpreadsheet, Loader2, UploadCloud } from "lucide-react";

interface Props {
  busy: boolean;
  onFile: (file: File) => void;
}

export default function UploadPanel({ busy, onFile }: Props) {
  const [dragging, setDragging] = useState(false);

  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) onFile(file);
    e.target.value = ""; // allow re-selecting the same file
  };

  const handleDrop = (e: DragEvent<HTMLLabelElement>) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file && !busy) onFile(file);
  };

  return (
    <section className="card">
      <label
        className={`dropzone${dragging ? " dragging" : ""}${busy ? " busy" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
      >
        <input type="file" accept=".csv,.xls,.xlsx" onChange={handleChange} disabled={busy} />
        {busy ? <Loader2 className="spin" size={36} /> : <UploadCloud size={36} />}
        <strong>{busy ? "Processing your dataset…" : "Drop a file here, or click to browse"}</strong>
        <span className="muted">CSV, XLS or XLSX · up to 15 MB · processed per request, not saved permanently</span>
      </label>

      <div className="hint">
        <FileSpreadsheet size={18} />
        <div>
          <strong>Expected layout</strong>
          <p className="muted">
            One row per student. Include a roll number column (e.g. <code>Roll No</code>), a <code>Name</code> column,
            optional <code>Attendance</code>, and one numeric column per subject with marks from 0 to 100. Subject names
            and the number of subjects can be anything. If columns are not recognised you will be asked to map them.
          </p>
        </div>
      </div>
    </section>
  );
}
