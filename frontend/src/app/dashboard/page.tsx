"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { RequireAuth } from "@/components/RequireAuth";
import { RiskPill, StatusPill } from "@/components/Pills";
import { StatCard } from "@/components/StatCard";
import { get } from "@/lib/api";
import type { DashboardStats, Health } from "@/lib/types";
import { useRealtime } from "@/lib/ws";

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const { events, connected } = useRealtime();

  const load = async () => {
    const [s, h] = await Promise.allSettled([
      get<DashboardStats>("/api/v1/dashboard"),
      get<Health>("/health"),
    ]);
    if (s.status === "fulfilled") setStats(s.value);
    if (h.status === "fulfilled") setHealth(h.value);
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <RequireAuth>
      <h2 className="page-title">Dashboard</h2>

      <div className="grid cols-4">
        <StatCard label="Активи" value={stats?.total_assets ?? "—"} />
        <StatCard
          label="Непрочитані сповіщення"
          value={stats?.unread_notifications ?? "—"}
          tone={stats?.unread_notifications ? "#ffc86b" : undefined}
        />
        <StatCard
          label="Скани з високим ризиком"
          value={stats?.high_risk_scans ?? "—"}
          tone={stats?.high_risk_scans ? "#ff6b7a" : undefined}
        />
        <StatCard label="WebSocket" value={connected ? "ONLINE" : "offline"} tone={connected ? "#37d29a" : "#ff6b7a"} />
      </div>

      <div className="grid cols-2">
        <div className="panel">
          <h3>Статус системи</h3>
          {!health && <div className="muted">Завантаження…</div>}
          {health?.services.map((s) => (
            <div key={s.service} className="event-line">
              <span
                className={`status-dot ${s.status === "200" ? "ok" : "bad"}`}
              />
              <span>{s.service}</span>
              <span className="muted small">{s.method}</span>
              <span className="muted small">{s.status}</span>
            </div>
          ))}
        </div>

        <div className="panel">
          <h3>Останні сканування</h3>
          {(!stats || stats.recent_scans.length === 0) && (
            <div className="empty">Поки немає сканувань</div>
          )}
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Тип</th>
                <th>Статус</th>
                <th>Ризик</th>
              </tr>
            </thead>
            <tbody>
              {stats?.recent_scans.map((s) => (
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
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="grid cols-2">
        <div className="panel">
          <h3>Активність у реальному часі</h3>
          {events.length === 0 && <div className="muted">Підключіться до WS — події зʼявляться тут</div>}
          {events.slice(0, 20).map((ev, i) => (
            <div key={ev.at + "-" + i} className="event-line">
              <time>{new Date(ev.at).toLocaleTimeString()}</time>
              <span>{ev.type}</span>
              <span className="muted small">{JSON.stringify(ev.data)}</span>
            </div>
          ))}
        </div>

        <div className="panel">
          <h3>Швидкі дії</h3>
          <div className="grid" style={{ gridTemplateColumns: "1fr 1fr", gap: 8 }}>
            <Link href="/assets">
              <button className="ghost" style={{ width: "100%" }}>
                Керувати assets
              </button>
            </Link>
            <Link href="/scans">
              <button className="ghost" style={{ width: "100%" }}>
                Створити сканування
              </button>
            </Link>
            <Link href="/findings">
              <button className="ghost" style={{ width: "100%" }}>
                Переглянути findings
              </button>
            </Link>
            <Link href="/reports">
              <button className="ghost" style={{ width: "100%" }}>
                Звіти
              </button>
            </Link>
          </div>
        </div>
      </div>
    </RequireAuth>
  );
}