"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { RequireAuth } from "@/components/RequireAuth";
import { RiskPill, StatusPill } from "@/components/Pills";
import { get, post } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Asset, Scan, ScanType } from "@/lib/types";

export default function ScansPage() {
  const { session } = useAuth();
  const canCreate = session?.role === "admin" || session?.role === "analyst";
  const [scans, setScans] = useState<Scan[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [assetId, setAssetId] = useState("");
  const [scanType, setScanType] = useState<ScanType>("tcp");
  const [ports, setPorts] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setScans(await get<Scan[]>("/api/v1/scans"));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Помилка");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (canCreate) {
      get<Asset[]>("/api/v1/assets")
        .then(setAssets)
        .catch(() => undefined);
    }
  }, [canCreate]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await post("/api/v1/scans", {
        asset_id: Number(assetId),
        scan_type: scanType,
        ports: ports || null,
      });
      setPorts("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Помилка");
    } finally {
      setBusy(false);
    }
  };

  return (
    <RequireAuth>
      <h2 className="page-title">Scans</h2>

      {canCreate && (
        <div className="panel">
          <h3>Нове сканування</h3>
          {error && <div className="error">{error}</div>}
          <form onSubmit={submit}>
            <div className="form-row">
              <div>
                <label>Актив (ціль)</label>
                <select
                  value={assetId}
                  onChange={(e) => setAssetId(e.target.value)}
                  required
                >
                  <option value="">— виберіть —</option>
                  {assets.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name} ({a.host})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label>Тип сканування</label>
                <select
                  value={scanType}
                  onChange={(e) => setScanType(e.target.value as ScanType)}
                >
                  <option value="tcp">tcp</option>
                  <option value="ping">ping</option>
                  <option value="quick">quick</option>
                </select>
              </div>
              <div>
                <label>Порти (optional)</label>
                <input
                  value={ports}
                  onChange={(e) => setPorts(e.target.value)}
                  placeholder="22,80,443  або 1-1000"
                />
              </div>
            </div>
            <button type="submit" disabled={busy || !assetId}>
              {busy ? "Запуск…" : "Запустити сканування"}
            </button>
          </form>
        </div>
      )}

      <div className="panel">
        <h3>Історія ({scans.length})</h3>
        {scans.length === 0 && <div className="empty">Немає сканувань</div>}
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Тип</th>
              <th>Статус</th>
              <th>Ризик</th>
              <th>Старт</th>
              <th>Фініш</th>
            </tr>
          </thead>
          <tbody>
            {scans.map((s) => (
              <tr key={s.id}>
                <td>
                  <Link href={`/scans/${s.id}`}>#{s.id}</Link>
                </td>
                <td>{s.scan_type}</td>
                <td>
                  <StatusPill status={s.status} />
                </td>
                <td>
                  <RiskPill risk={s.risk_level} />
                </td>
                <td className="small muted">
                  {s.started_at ? new Date(s.started_at).toLocaleString() : "—"}
                </td>
                <td className="small muted">
                  {s.finished_at ? new Date(s.finished_at).toLocaleString() : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </RequireAuth>
  );
}