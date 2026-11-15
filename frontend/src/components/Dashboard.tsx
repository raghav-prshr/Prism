import { useEffect, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { AlertTriangle, SlidersHorizontal } from "lucide-react";
import type { Analysis, ColumnMapping, Thresholds } from "../types";
import { CLASS_COLORS, CLASS_ORDER, PRIMARY } from "../constants";
import MappingForm from "./MappingForm";

interface Props {
  analysis: Analysis;
  busy: boolean;
  onApplyThresholds: (t: Thresholds) => void;
  onApplyMapping: (m: ColumnMapping) => void;
}

const fmt = (v: number | null | undefined, suffix = "") => (v === null || v === undefined ? "—" : `${v.toFixed(1)}${suffix}`);

export default function Dashboard({ analysis, busy, onApplyThresholds, onApplyMapping }: Props) {
  const { summary, subject_stats, distribution, thresholds, columns } = analysis;
  const [adv, setAdv] = useState(String(thresholds.advanced));
  const [att, setAtt] = useState(String(thresholds.attention));
  const [thError, setThError] = useState<string | null>(null);

  useEffect(() => {
    setAdv(String(thresholds.advanced));
    setAtt(String(thresholds.attention));
    setThError(null);
  }, [thresholds.advanced, thresholds.attention]);

  const applyThresholds = () => {
    const a = Number(adv);
    const t = Number(att);
    if (adv.trim() === "" || att.trim() === "" || !Number.isFinite(a) || !Number.isFinite(t) || !(t >= 0 && t < a && a <= 100)) {
      setThError("Use numbers where 0 ≤ Needs Attention limit < Advanced limit ≤ 100.");
      return;
    }
    setThError(null);
    onApplyThresholds({ advanced: a, attention: t });
  };

  const subjectData = subject_stats
    .filter((s) => s.average !== null)
    .map((s) => ({ subject: s.subject, average: s.average, highest: s.highest, lowest: s.lowest }));
  const pieData = CLASS_ORDER.map((name) => ({ name, value: distribution[name] ?? 0 })).filter((d) => d.value > 0);

  const kpis = [
    { label: "Total students", value: String(summary.total_students), sub: `${summary.evaluated_students} with marks` },
    { label: "Class average", value: fmt(summary.class_average, "%"), sub: `${subject_stats.length} subject(s)` },
    {
      label: "Highest percentage",
      value: fmt(summary.highest?.value, "%"),
      sub: summary.highest ? summary.highest.name || summary.highest.roll_no : "No marks available",
    },
    {
      label: "Average attendance",
      value: fmt(summary.attendance_average, "%"),
      sub: columns.attendance ? `${summary.attendance_count} student(s) with data` : "No attendance column",
    },
  ];

  return (
    <div className="stack">
      {analysis.warnings.length > 0 && (
        <section className="card warn">
          <h3>
            <AlertTriangle size={18} /> Data notes ({analysis.warnings.length})
          </h3>
          <ul>
            {analysis.warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </section>
      )}

      <div className="kpis">
        {kpis.map((k) => (
          <div className="card kpi" key={k.label}>
            <span className="muted">{k.label}</span>
            <strong>{k.value}</strong>
            <span className="muted small">{k.sub}</span>
          </div>
        ))}
      </div>

      <section className="card">
        <h3>Classification thresholds</h3>
        <p className="muted">
          Students are classified with simple percentage thresholds. This is rule-based classification, not a machine-learning prediction.
        </p>
        <div className="thresholds">
          <label className="field">
            <span>Advanced: percentage ≥</span>
            <input type="number" min={0} max={100} step="any" value={adv} onChange={(e) => setAdv(e.target.value)} />
          </label>
          <label className="field">
            <span>Average: percentage ≥ (below this = Needs Attention)</span>
            <input type="number" min={0} max={100} step="any" value={att} onChange={(e) => setAtt(e.target.value)} />
          </label>
          <button className="btn primary" onClick={applyThresholds} disabled={busy}>
            Apply
          </button>
          <button
            className="btn"
            disabled={busy}
            onClick={() => onApplyThresholds({ advanced: 75, attention: 40 })}
          >
            Reset to 75 / 40
          </button>
        </div>
        {thError && <p className="field-error">{thError}</p>}
      </section>

      <div className="charts">
        <section className="card chart">
          <h3>Subject-wise average</h3>
          {subjectData.length === 0 ? (
            <p className="empty">No valid subject marks to chart.</p>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={subjectData} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="subject" tick={{ fontSize: 12 }} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="average" name="Average" fill={PRIMARY} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </section>

        <section className="card chart">
          <h3>Classification distribution</h3>
          {pieData.length === 0 ? (
            <p className="empty">No students to classify.</p>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <PieChart>
                <Pie data={pieData} dataKey="value" nameKey="name" innerRadius={60} outerRadius={100} paddingAngle={2}>
                  {pieData.map((d) => (
                    <Cell key={d.name} fill={CLASS_COLORS[d.name]} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          )}
        </section>

        <section className="card chart wide">
          <h3>Performance comparison by subject</h3>
          {subjectData.length === 0 ? (
            <p className="empty">No valid subject marks to chart.</p>
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={subjectData} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="subject" tick={{ fontSize: 12 }} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} />
                <Tooltip />
                <Legend />
                <Bar dataKey="highest" name="Highest" fill="#059669" radius={[4, 4, 0, 0]} />
                <Bar dataKey="average" name="Average" fill={PRIMARY} radius={[4, 4, 0, 0]} />
                <Bar dataKey="lowest" name="Lowest" fill="#dc2626" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </section>
      </div>

      <section className="card">
        <details>
          <summary>
            <SlidersHorizontal size={16} /> Detected columns &amp; manual mapping
          </summary>
          <p className="muted">
            Roll no: <b>{columns.roll_no ?? "—"}</b> · Name: <b>{columns.name ?? "—"}</b> · Attendance:{" "}
            <b>{columns.attendance ?? "—"}</b> · Subjects: <b>{columns.subjects.join(", ")}</b>
            {columns.ignored.length > 0 && (
              <>
                {" "}
                · Ignored: {columns.ignored.join(", ")}
              </>
            )}
          </p>
          <MappingForm
            key={`${columns.roll_no}|${columns.name}|${columns.attendance}|${columns.subjects.join(",")}`}
            columns={analysis.available_columns}
            initial={{ roll_no: columns.roll_no, name: columns.name, attendance: columns.attendance, subjects: columns.subjects }}
            busy={busy}
            submitLabel="Re-analyse with this mapping"
            onSubmit={onApplyMapping}
          />
        </details>
      </section>
    </div>
  );
}
