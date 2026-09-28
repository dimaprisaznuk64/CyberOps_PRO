"use client";

import { useCallback, useEffect, useState } from "react";

import { RequireAuth } from "@/components/RequireAuth";
import { RiskPill } from "@/components/Pills";
import { del, get, patch, post } from "@/lib/api";
import { useAuth } from "@/lib/auth";
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

function formatDate(value?: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleString("uk-UA", { dateStyle: "short", timeStyle: "short" });
}

export default function AssetsPage() {
  const { session } = useAuth();
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
      setError(e instanceof Error ? e.message : "Помилка");
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
      setError(err instanceof Error ? err.message : "Помилка");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: number) => {
    if (!window.confirm("Видалити актив?")) return;
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
      <h2 className="page-title">Assets</h2>

      <div className="panel">
        <h3>{editId !== null ? `Редагувати #${editId}` : "Новий актив"}</h3>
        {error && <div className="error">{error}</div>}
        <form onSubmit={submit}>
          <div className="form-row">
            <div>
              <label>Назва</label>
              <input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                required
              />
            </div>
            <div>
              <label>Host</label>
              <input
                value={form.host}
                onChange={(e) => setForm({ ...form, host: e.target.value })}
                placeholder="192.168.1.100 / example.com / vulnerable-api"
                required
              />
            </div>
            <div>
              <label>Тип</label>
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
              <label>Docker container (optional)</label>
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
              <label>Опис</label>
              <input
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
              />
            </div>
          </div>
          <button type="submit" disabled={busy || !form.name || !form.host}>
            {editId !== null ? "Зберегти зміни" : "Створити"}
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
              Скасувати
            </button>
          )}
        </form>
      </div>

      <div className="panel">
        <h3>Список ({assets.length})</h3>
        <div className="form-row">
          <div style={{ flex: "0 0 220px" }}>
            <label>Сортування</label>
            <select value={sortBy} onChange={(e) => setSortBy(e.target.value as SortBy)}>
              <option value="risk">за ризиком</option>
              <option value="name">за назвою</option>
              <option value="id">за ID</option>
            </select>
          </div>
        </div>
        {assets.length === 0 && <div className="empty">Немає активів</div>}
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Назва</th>
              <th>Host</th>
              <th>Тип</th>
              <th>Docker</th>
              <th>Ризик</th>
              <th>Історія</th>
              <th>Скани</th>
              <th>Дії</th>
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
                    <span className="pill neutral">не скановано</span>
                  ) : (
                    <>
                      <RiskPill risk={a.risk_level} />{" "}
                      <span className="small muted">{a.risk_score}/100</span>
                    </>
                  )}
                </td>
                <td className="small muted">
                  {a.max_risk_score !== null && a.max_risk_score !== undefined && (
                    <div>макс {a.max_risk_score} ({a.max_risk_level})</div>
                  )}
                  <div>останній: {formatDate(a.last_scan_at)}</div>
                </td>
                <td className="small">{a.scans_count ?? 0}</td>
                <td>
                  {canManage && (
                    <button className="sm ghost" onClick={() => startEdit(a)}>
                      Edit
                    </button>
                  )}{" "}
                  {canManage && (
                    <button className="sm danger" onClick={() => remove(a.id)}>
                      Del
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