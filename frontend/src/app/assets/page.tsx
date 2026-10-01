"use client";

import { useCallback, useEffect, useState } from "react";

import { RequireAuth } from "@/components/RequireAuth";
import { RiskPill } from "@/components/Pills";
import { del, get, patch, post } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import type { Asset, AssetKind } from "@/lib/types";

const EMPTY = { name: "", host: "", kind: "ip" as AssetKind, docker_container: "", description: "" };

type SortBy = "risk" | "name" | "id";

/** Ризик за кожним активом: null (не сканували) йде в кінець, решта — за спаданням. */
function byRisk(a: Asset, b: Asset): number {
  return (b.risk_score ?? -1) - (a.risk_score ?? -1);
}

function sortAssets(assets: Asset[], sortBy: SortBy): Asset[] {
  const sorted = [...assets];
  if (sortBy === "risk") sorted.sort(byRisk);
  else if (sortBy === "name") sorted.sort((a, b) => a.name.localeCompare(b.name));
  else sorted.sort((a, b) => a.id - b.id);
  return sorted;
}

function formatDate(value: string | null | undefined, locale: string): string {
  if (!value) return "—";
  return new Date(value).toLocaleString(locale, { dateStyle: "short", timeStyle: "short" });
}

export default function AssetsPage() {
  const { session } = useAuth();
  const { t, locale } = useI18n();
  const [assets, setAssets] = useState<Asset[]>([]);
  const [form, setForm] = useState(EMPTY);
  const [editId, setEditId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [sortBy, setSortBy] = useState<SortBy>("risk");
  const canManage = session?.role === "admin" || session?.role === "analyst";

  const load = useCallback(async () => {
    try {
      setAssets(await get<Asset[]>("/api/v1/assets"));
    } catch (e) {
      setError(e instanceof Error ? e.message : t("common.error"));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const payload = {
        name: form.name,
        host: form.host,
        kind: form.kind,
        docker_container: form.docker_container || null,
        description: form.description || null,
      };
      if (editId !== null) {
        await patch(`/api/v1/assets/${editId}`, payload);
      } else {
        await post("/api/v1/assets", payload);
      }
      setForm(EMPTY);
      setEditId(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: number) => {
    if (!window.confirm(t("assets.confirmDelete"))) return;
    await del(`/api/v1/assets/${id}`);
    await load();
  };

  const startEdit = (a: Asset) => {
    setEditId(a.id);
    setForm({
      name: a.name,
      host: a.host,
      kind: a.kind,
      docker_container: a.docker_container ?? "",
      description: a.description ?? "",
    });
  };

  return (
    <RequireAuth>
      <h2 className="page-title">{t("assets.title")}</h2>

      <div className="panel">
        <h3>{editId !== null ? t("assets.edit", { id: editId }) : t("assets.new")}</h3>
        {error && <div className="error">{error}</div>}
        <form onSubmit={submit}>
          <div className="form-row">
            <div>
              <label>{t("assets.name")}</label>
              <input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                required
              />
            </div>
            <div>
              <label>{t("assets.host")}</label>
              <input
                value={form.host}
                onChange={(e) => setForm({ ...form, host: e.target.value })}
                placeholder={t("assets.hostPlaceholder")}
                required
              />
            </div>
            <div>
              <label>{t("assets.kind")}</label>
              <select
                value={form.kind}
                onChange={(e) => setForm({ ...form, kind: e.target.value as AssetKind })}
              >
                <option value="ip">ip</option>
                <option value="domain">domain</option>
                <option value="hostname">hostname</option>
                <option value="docker">docker</option>
              </select>
            </div>
            <div>
              <label>{t("assets.docker")}</label>
              <input
                value={form.docker_container}
                onChange={(e) =>
                  setForm({ ...form, docker_container: e.target.value })
                }
              />
            </div>
          </div>
          <div className="form-row">
            <div>
              <label>{t("assets.description")}</label>
              <input
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
              />
            </div>
          </div>
          <button type="submit" disabled={busy || !form.name || !form.host}>
            {editId !== null ? t("assets.saveChanges") : t("assets.create")}
          </button>
          {editId !== null && (
            <button
              type="button"
              className="ghost"
              style={{ marginLeft: 8 }}
              onClick={() => {
                setEditId(null);
                setForm(EMPTY);
              }}
            >
              {t("common.cancel")}
            </button>
          )}
        </form>
      </div>

      <div className="panel">
        <h3>{t("assets.list", { count: assets.length })}</h3>
        <div className="form-row">
          <div style={{ flex: "0 0 220px" }}>
            <label>{t("assets.sort")}</label>
            <select value={sortBy} onChange={(e) => setSortBy(e.target.value as SortBy)}>
              <option value="risk">{t("assets.sortRisk")}</option>
              <option value="name">{t("assets.sortName")}</option>
              <option value="id">{t("assets.sortId")}</option>
            </select>
          </div>
        </div>
        {assets.length === 0 && <div className="empty">{t("assets.none")}</div>}
        <table>
          <thead>
            <tr>
              <th>{t("common.id")}</th>
              <th>{t("assets.colName")}</th>
              <th>{t("assets.host")}</th>
              <th>{t("assets.kind")}</th>
              <th>{t("assets.colDocker")}</th>
              <th>{t("common.risk")}</th>
              <th>{t("assets.colHistory")}</th>
              <th>{t("assets.colScans")}</th>
              <th>{t("assets.colActions")}</th>
            </tr>
          </thead>
          <tbody>
            {sortAssets(assets, sortBy).map((a) => (
              <tr key={a.id}>
                <td>{a.id}</td>
                <td>{a.name}</td>
                <td>{a.host}</td>
                <td>
                  <span className="pill neutral">{a.kind}</span>
                </td>
                <td className="muted small">{a.docker_container ?? "—"}</td>
                <td>
                  {a.risk_score === null || a.risk_score === undefined ? (
                    <span className="pill neutral">{t("assets.notScanned")}</span>
                  ) : (
                    <>
                      <RiskPill risk={a.risk_level} />{" "}
                      <span className="small muted">{a.risk_score}/100</span>
                    </>
                  )}
                </td>
                <td className="small muted">
                  {a.max_risk_score !== null && a.max_risk_score !== undefined && (
                    <div>
                      {t("assets.max", {
                        score: a.max_risk_score,
                        level: a.max_risk_level ?? "",
                      })}
                    </div>
                  )}
                  <div>{t("assets.last", { date: formatDate(a.last_scan_at, locale) })}</div>
                </td>
                <td className="small">{a.scans_count ?? 0}</td>
                <td>
                  {canManage && (
                    <button className="sm ghost" onClick={() => startEdit(a)}>
                      {t("common.edit")}
                    </button>
                  )}{" "}
                  {canManage && (
                    <button className="sm danger" onClick={() => remove(a.id)}>
                      {t("common.delete")}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </RequireAuth>
  );
}