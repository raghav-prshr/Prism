import { useEffect, useMemo, useState } from "react";
import { Search } from "lucide-react";
import type { Analysis, Classification } from "../types";
import { CLASS_ORDER, CLASS_SLUG } from "../constants";

const PAGE_SIZE = 25;
const trim = (v: number | null) => (v === null ? "—" : String(Number(v.toFixed(2))));

export default function StudentsTable({ analysis }: { analysis: Analysis }) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Classification | "All">("All");
  const [page, setPage] = useState(0);
  const { students, columns, distribution, thresholds } = analysis;
  const subjects = columns.subjects;

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return students.filter(
      (s) =>
        (filter === "All" || s.classification === filter) &&
        (q === "" || s.name.toLowerCase().includes(q) || s.roll_no.toLowerCase().includes(q)),
    );
  }, [students, query, filter]);

  useEffect(() => setPage(0), [query, filter, students]);

  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const visible = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const chips: (Classification | "All")[] = ["All", ...CLASS_ORDER.filter((c) => c !== "No Data" || distribution["No Data"] > 0)];

  return (
    <section className="card">
      <div className="toolbar">
        <label className="search">
          <Search size={16} />
          <input
            type="search"
            placeholder="Search by name or roll number"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Search students"
          />
        </label>
        <div className="chips" role="group" aria-label="Filter by classification">
          {chips.map((c) => (
            <button key={c} className={`chip${filter === c ? " active" : ""}`} onClick={() => setFilter(c)}>
              {c} <span>{c === "All" ? students.length : distribution[c]}</span>
            </button>
          ))}
        </div>
      </div>

      {filtered.length === 0 ? (
        <p className="empty">No students match your search and filter.</p>
      ) : (
        <>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Roll No</th>
                  <th>Name</th>
                  {subjects.map((s) => (
                    <th key={s} className="num">
                      {s}
                    </th>
                  ))}
                  <th className="num">Average</th>
                  <th className="num">Attendance</th>
                  <th>Classification</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((s, i) => (
                  <tr key={`${s.roll_no}-${i}`}>
                    <td>{s.roll_no || "—"}</td>
                    <td>{s.name || "—"}</td>
                    {subjects.map((sub) => {
                      const v = s.marks[sub] ?? null;
                      return (
                        <td key={sub} className={`num${v !== null && v < thresholds.attention ? " low" : ""}`}>
                          {trim(v)}
                        </td>
                      );
                    })}
                    <td className="num strong">{s.average === null ? "—" : `${s.average.toFixed(1)}`}</td>
                    <td className="num">{s.attendance === null ? "—" : `${s.attendance.toFixed(1)}%`}</td>
                    <td>
                      <span className={`badge ${CLASS_SLUG[s.classification]}`}>{s.classification}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="pager">
            <span className="muted">
              Showing {page * PAGE_SIZE + 1}–{Math.min(filtered.length, (page + 1) * PAGE_SIZE)} of {filtered.length}
            </span>
            <div>
              <button className="btn" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
                Previous
              </button>
              <span className="muted pg">
                Page {page + 1} / {pages}
              </span>
              <button className="btn" disabled={page >= pages - 1} onClick={() => setPage((p) => p + 1)}>
                Next
              </button>
            </div>
          </div>
        </>
      )}
    </section>
  );
}
