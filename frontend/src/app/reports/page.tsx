"use client";

import { useCallback, useEffect, useState } from "react";

import { RequireAuth } from "@/components/RequireAuth";
import { apiUrl, get, getToken, post } from "@/lib/api";
import type { Asset, Report, ReportDetail, Scan } from "@/lib/types";

const FORMATS = ["csv", "html", "pdf"];

export default function ReportsPage() {
  const [reports, setReports] = useState<Report[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [scans, setScans] = useState<Scan[]>([]);
  const [title, setTitle] = useState("");
  const [reportType, setReportType] = useState("scan");
  const [scanId, setScanId] = useState("");
  const [assetId, setAssetId] = useState("");
  const [detail, setDetail] = useState<ReportDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setReports(await get<Report[]>("/api/v1/reports"));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Помилка");
    }
  }, []);

  useEffect(() => {
    load();
    get<Asset[]>("/api/v1/assets")
      .then(setAssets)
      .catch(() => undefined);
    get<Scan[]>("/api/v1/scans")
      .then(setScans)
      .catch(() => undefined);
  }, [load]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await post("/api/v1/reports", {
        title,
        report_type: reportType,
        scan_id: reportType === "scan" ? Number(scanId) || null : null,
        asset_id: reportType === "asset" ? Number(assetId) || null : null,
      });
      setTitle("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Помилка");
    }
  };

  const download = async (id: number, format: string) => {
    const token = getToken();
    const resp = await fetch(apiUrl(`/api/v1/reports/${id}/export?format=${format}`), {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!resp.ok) {
      setError(`Export failed: HTTP ${resp.status}`);
      return;
    }
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `report_${id}.${format}`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const openDetail = async (id: number) => {
    try {
      setDetail(await get<ReportDetail>(`/api/v1/reports/${id}`));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Помилка");
    }
  };

  return (
    <RequireAuth>
      <h2 className="page-title">Reports</h2>

      <div className="panel">
        <h3>Новий звіт</h3>
        {error && <div className="error">{error}</div>}
        <form onSubmit={submit}>
          <div className="form-row">
            <div>
              <label>Назва</label>
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                required
              />
            </div>
            <div>
              <label>Тип</label>
              <select
                value={reportType}
                onChange={(e) => setReportType(e.target.value)}
              >
                <option value="scan">scan</option>
                <option value="asset">asset</option>
              </select>
            </div>
            {reportType === "scan" && (
              <div>
                <label>Scan</label>
                <select value={scanId} onChange={(e) => setScanId(e.target.value)}>
                  <option value="">— виберіть —</option>
                  {scans.map((s) => (
                    <option key={s.id} value={s.id}>
                      #{s.id} ({s.scan_type}, {s.status})
                    </option>
                  ))}
                </select>
              </div>
            )}
            {reportType === "asset" && (
              <div>
                <label>Asset</label>
                <select value={assetId} onChange={(e) => setAssetId(e.target.value)}>
                  <option value="">— виберіть —</option>
                  {assets.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name} ({a.host})
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>
          <button type="submit" disabled={!title}>
            Згенерувати
          </button>
        </form>
      </div>

      <div className="panel">
        <h3>Звіти ({reports.length})</h3>
        {reports.length === 0 && <div className="empty">Немає звітів</div>}
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Назва</th>
              <th>Тип</th>
              <th>Створено</th>
              <th>Експорт</th>
              <th>Деталі</th>
            </tr>
          </thead>
          <tbody>
            {reports.map((r) => (
              <tr key={r.id}>
                <td>{r.id}</td>
                <td>{r.title}</td>
                <td>
                  <span className="pill neutral">{r.report_type}</span>
                </td>
                <td className="small muted">
                  {new Date(r.created_at).toLocaleString()}
                </td>
                <td>
                  {FORMATS.map((f) => (
                    <button key={f} className="sm ghost" onClick={() => download(r.id, f)}>
                      {f}
                    </button>
                  ))}
                </td>
                <td>
                  <button className="sm ghost" onClick={() => openDetail(r.id)}>
                    View
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {detail && (
        <div className="panel">
          <h3>
            Деталі #{detail.id}: {detail.title}
          </h3>
          <pre className="small">{JSON.stringify(detail.content, null, 2)}</pre>
          <button className="sm ghost" onClick={() => setDetail(null)}>
            Закрити
          </button>
        </div>
      )}
    </RequireAuth>
  );
}