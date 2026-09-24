"use client";

import { useCallback, useEffect, useState } from "react";

import { AIExplain } from "@/components/AIExplain";
import { RequireAuth } from "@/components/RequireAuth";
import { SeverityPill } from "@/components/Pills";
import { get } from "@/lib/api";
import type { Finding } from "@/lib/types";

const SEVERITIES = ["info", "low", "medium", "high", "critical"];

export default function FindingsPage() {
  const [findings, setFindings] = useState<Finding[]>([]);
  const [severity, setSeverity] = useState("");
  const [scanId, setScanId] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (severity) params.set("severity", severity);
      if (scanId) params.set("scan_id", scanId);
      const qs = params.toString();
      setFindings(await get<Finding[]>(`/api/v1/findings${qs ? `?${qs}` : ""}`));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Помилка");
    }
  }, [severity, scanId]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <RequireAuth>
      <h2 className="page-title">Findings</h2>

      <div className="panel">
        <div className="form-row" style={{ marginBottom: 0 }}>
          <div>
            <label>Серйозність</label>
            <select value={severity} onChange={(e) => setSeverity(e.target.value)}>
              <option value="">всі</option>
              {SEVERITIES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label>Scan ID</label>
            <input
              value={scanId}
              onChange={(e) => setScanId(e.target.value)}
              placeholder="filter by scan"
            />
          </div>
        </div>
      </div>

      {error && <div className="error">{error}</div>}

      <div className="panel">
        <h3>Знахідки ({findings.length})</h3>
        {findings.length === 0 && <div className="empty">Немає знахідок</div>}
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Scan</th>
              <th>Серйозність</th>
              <th>Назва</th>
              <th>CVE</th>
              <th>AI</th>
            </tr>
          </thead>
          <tbody>
            {findings.map((f) => (
              <tr key={f.id}>
                <td>{f.id}</td>
                <td>
                  <a href={`/scans/${f.scan_id}`}>#{f.scan_id}</a>
                </td>
                <td>
                  <SeverityPill severity={f.severity} />
                </td>
                <td>
                  <b>{f.title}</b>
                  {f.description && <div className="small muted">{f.description}</div>}
                  {f.recommendation && (
                    <div className="small muted">🛠 {f.recommendation}</div>
                  )}
                </td>
                <td className="small">{f.cve ?? "—"}</td>
                <td>
                  <AIExplain findingId={f.id} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </RequireAuth>
  );
}