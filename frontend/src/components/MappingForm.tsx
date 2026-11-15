import { useState } from "react";
import type { ColumnMapping } from "../types";

interface Props {
  columns: string[];
  initial: ColumnMapping;
  busy: boolean;
  submitLabel: string;
  onSubmit: (mapping: ColumnMapping) => void;
}

export default function MappingForm({ columns, initial, busy, submitLabel, onSubmit }: Props) {
  const [roll, setRoll] = useState(initial.roll_no ?? "");
  const [name, setName] = useState(initial.name ?? "");
  const [attendance, setAttendance] = useState(initial.attendance ?? "");
  const [subjects, setSubjects] = useState<string[]>(initial.subjects);
  const [problem, setProblem] = useState<string | null>(null);

  const used = new Set([roll, name, attendance].filter(Boolean));

  const toggle = (col: string) =>
    setSubjects((cur) => (cur.includes(col) ? cur.filter((c) => c !== col) : [...cur, col]));

  const pickSingle = (setter: (v: string) => void) => (value: string) => {
    setter(value);
    if (value) setSubjects((cur) => cur.filter((c) => c !== value));
  };

  const submit = () => {
    const chosen = subjects.filter((s) => !used.has(s));
    if (!roll && !name) return setProblem("Choose a roll number column or a name column.");
    if (chosen.length === 0) return setProblem("Select at least one subject column.");
    if ([roll, name, attendance].filter(Boolean).length !== used.size) return setProblem("Each column can only be used once.");
    setProblem(null);
    onSubmit({ roll_no: roll || null, name: name || null, attendance: attendance || null, subjects: chosen });
  };

  const select = (label: string, value: string, setter: (v: string) => void) => (
    <label className="field">
      <span>{label}</span>
      <select value={value} onChange={(e) => pickSingle(setter)(e.target.value)}>
        <option value="">— none —</option>
        {columns.map((c) => (
          <option key={c} value={c}>
            {c}
          </option>
        ))}
      </select>
    </label>
  );

  return (
    <div className="mapping">
      <div className="grid-3">
        {select("Roll number / ID", roll, setRoll)}
        {select("Student name", name, setName)}
        {select("Attendance (optional)", attendance, setAttendance)}
      </div>
      <fieldset className="subjects">
        <legend>Subject columns (marks out of 100)</legend>
        <div className="checks">
          {columns.map((c) => (
            <label key={c} className={`check${used.has(c) ? " disabled" : ""}`}>
              <input type="checkbox" disabled={used.has(c)} checked={subjects.includes(c) && !used.has(c)} onChange={() => toggle(c)} />
              {c}
            </label>
          ))}
        </div>
      </fieldset>
      {problem && <p className="field-error">{problem}</p>}
      <button className="btn primary" onClick={submit} disabled={busy}>
        {submitLabel}
      </button>
    </div>
  );
}
