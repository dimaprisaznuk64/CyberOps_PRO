"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { RequireAuth } from "@/components/RequireAuth";
import { RiskPill, StatusPill } from "@/components/Pills";
import { get, post } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import type { Asset, Scan, ScanType } from "@/lib/types";

export default function ScansPage() {
  const { session } = useAuth();
  const { t, locale } = useI18n();
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
      setError(e instanceof Error ? e.message : t("common.error"));
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
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <RequireAuth>
      <h2 className="page-title">{t("scans.title")}</h2>

      {canCreate && (
        <div className="panel">
          <h3>{t("scans.new")}</h3>
          {error && <div className="error">{error}</div>}
          <form onSubmit={submit}>
            <div className="form-row">
              <div>
                <label>{t("scans.asset")}</label>
                <select
                  value={assetId}
                  onChange={(e) => setAssetId(e.target.value)}
                  required
                >
                  <option value="">{t("common.select")}</option>
                  {assets.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name} ({a.host})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label>{t("scans.type")}</label>
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
                <label>{t("scans.ports")}</label>
                <input
                  value={ports}
                  onChange={(e) => setPorts(e.target.value)}
                  placeholder={t("scans.portsPlaceholder")}
                />
              </div>
            </div>
            <button type="submit" disabled={busy || !assetId}>
              {busy ? t("scans.submitting") : t("scans.submit")}
            </button>
          </form>
        </div>
      )}

      <div className="panel">
        <h3>{t("scans.history", { count: scans.length })}</h3>
        {scans.length === 0 && <div className="empty">{t("scans.none")}</div>}
        <table>
          <thead>
            <tr>
              <th>{t("common.id")}</th>
              <th>{t("common.type")}</th>
              <th>{t("common.status")}</th>
              <th>{t("common.risk")}</th>
              <th>{t("scans.colStart")}</th>
              <th>{t("scans.colFinish")}</th>
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
                  {s.started_at ? new Date(s.started_at).toLocaleString(locale) : "—"}
                </td>
                <td className="small muted">
                  {s.finished_at ? new Date(s.finished_at).toLocaleString(locale) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </RequireAuth>
  );
}