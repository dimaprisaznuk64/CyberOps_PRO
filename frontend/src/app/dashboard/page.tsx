"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { RequireAuth } from "@/components/RequireAuth";
import { RiskPill, StatusPill } from "@/components/Pills";
import { StatCard } from "@/components/StatCard";
import { get } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { DashboardStats, Health } from "@/lib/types";
import { useRealtime } from "@/lib/ws";

export default function DashboardPage() {
  const { t } = useI18n();
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
      <h2 className="page-title">{t("dashboard.title")}</h2>

      <div className="grid cols-4">
        <StatCard label={t("dashboard.assets")} value={stats?.total_assets ?? "—"} />
        <StatCard
          label={t("dashboard.unread")}
          value={stats?.unread_notifications ?? "—"}
          tone={stats?.unread_notifications ? "#ffc86b" : undefined}
        />
        <StatCard
          label={t("dashboard.highRisk")}
          value={stats?.high_risk_scans ?? "—"}
          tone={stats?.high_risk_scans ? "#ff6b7a" : undefined}
        />
        <StatCard label="WebSocket" value={connected ? "ONLINE" : "offline"} tone={connected ? "#37d29a" : "#ff6b7a"} />
      </div>

      <div className="grid cols-2">
        <div className="panel">
          <h3>{t("dashboard.systemStatus")}</h3>
          {!health && <div className="muted">{t("common.loading")}</div>}
          {health &&
            Object.entries(health.services).map(([service, status]) => (
              <div key={service} className="event-line">
                <span
                  className={`status-dot ${status === "ok" ? "ok" : "bad"}`}
                />
                <span>{service}</span>
                <span className="muted small">{status}</span>
              </div>
            ))}
        </div>

        <div className="panel">
          <h3>{t("dashboard.recentScans")}</h3>
          {(!stats || stats.recent_scans.length === 0) && (
            <div className="empty">{t("dashboard.noScans")}</div>
          )}
          <table>
            <thead>
              <tr>
                <th>{t("common.id")}</th>
                <th>{t("common.type")}</th>
                <th>{t("common.status")}</th>
                <th>{t("common.risk")}</th>
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
          <h3>{t("dashboard.realtime")}</h3>
          {events.length === 0 && <div className="muted">{t("dashboard.wsHint")}</div>}
          {events.slice(0, 20).map((ev, i) => (
            <div key={ev.at + "-" + i} className="event-line">
              <time>{new Date(ev.at).toLocaleTimeString()}</time>
              <span>{ev.type}</span>
              <span className="muted small">{JSON.stringify(ev.data)}</span>
            </div>
          ))}
        </div>

        <div className="panel">
          <h3>{t("dashboard.quickActions")}</h3>
          <div className="grid" style={{ gridTemplateColumns: "1fr 1fr", gap: 8 }}>
            <Link href="/assets">
              <button className="ghost" style={{ width: "100%" }}>
                {t("dashboard.manageAssets")}
              </button>
            </Link>
            <Link href="/scans">
              <button className="ghost" style={{ width: "100%" }}>
                {t("dashboard.createScan")}
              </button>
            </Link>
            <Link href="/findings">
              <button className="ghost" style={{ width: "100%" }}>
                {t("dashboard.viewFindings")}
              </button>
            </Link>
            <Link href="/reports">
              <button className="ghost" style={{ width: "100%" }}>
                {t("dashboard.reports")}
              </button>
            </Link>
          </div>
        </div>
      </div>
    </RequireAuth>
  );
}