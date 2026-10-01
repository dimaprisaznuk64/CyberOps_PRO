"use client";

import { useCallback, useEffect, useState } from "react";

import { AIExplain } from "@/components/AIExplain";
import { RequireAuth } from "@/components/RequireAuth";
import { SeverityPill } from "@/components/Pills";
import { get } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Finding } from "@/lib/types";

const SEVERITIES = ["info", "low", "medium", "high", "critical"];

export default function FindingsPage() {
  const { t } = useI18n();
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
      setError(e instanceof Error ? e.message : t("common.error"));
    }
  }, [severity, scanId, t]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <RequireAuth>
      <h2 className="page-title">{t("findings.title")}</h2>

      <div className="panel">
        <div className="form-row" style={{ marginBottom: 0 }}>
          <div>
            <label>{t("findings.severity")}</label>
            <select value={severity} onChange={(e) => setSeverity(e.target.value)}>
              <option value="">{t("common.all")}</option>
              {SEVERITIES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label>{t("findings.scanId")}</label>
            <input
              value={scanId}
              onChange={(e) => setScanId(e.target.value)}
              placeholder={t("findings.scanPlaceholder")}
            />
          </div>
        </div>
      </div>

      {error && <div className="error">{error}</div>}

      <div className="panel">
        <h3>{t("findings.list", { count: findings.length })}</h3>
        {findings.length === 0 && <div className="empty">{t("findings.none")}</div>}
        <table>
          <thead>
            <tr>
              <th>{t("common.id")}</th>
              <th>{t("findings.colScan")}</th>
              <th>{t("findings.severity")}</th>
              <th>{t("findings.colTitle")}</th>
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