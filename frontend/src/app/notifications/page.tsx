"use client";

import { useCallback, useEffect, useState } from "react";

import { RequireAuth } from "@/components/RequireAuth";
import { ChannelPill, DeliveryPill, SeverityPill } from "@/components/Pills";
import { get, patch, post } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Notification, NotificationChannel } from "@/lib/types";

export default function NotificationsPage() {
  const { t, locale } = useI18n();
  const [items, setItems] = useState<Notification[]>([]);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [channel, setChannel] = useState<NotificationChannel | "">("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const channels: Array<{ value: NotificationChannel | ""; label: string }> = [
    { value: "", label: t("notifications.allChannels") },
    { value: "web", label: "Web" },
    { value: "email", label: "Email" },
    { value: "telegram", label: "Telegram" },
  ];

  const load = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (unreadOnly) params.set("unread_only", "true");
      if (channel) params.set("channel", channel);
      const qs = params.toString() ? `?${params.toString()}` : "";
      setItems(await get<Notification[]>(`/api/v1/notifications${qs}`));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("common.error"));
    }
  }, [unreadOnly, channel, t]);

  useEffect(() => {
    load();
  }, [load]);

  const markRead = async (id: number) => {
    await patch(`/api/v1/notifications/${id}/read`, { is_read: true });
    await load();
  };

  const markAll = async () => {
    await post<number>("/api/v1/notifications/read-all");
    await load();
  };

  const retry = async (id: number) => {
    setError(null);
    setNotice(null);
    try {
      await post(`/api/v1/notifications/${id}/retry`);
      setNotice(t("notifications.retryQueued"));
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("common.error"));
    }
  };

  return (
    <RequireAuth>
      <h2 className="page-title">{t("notifications.title")}</h2>
      {error && <div className="error">{error}</div>}
      {notice && <div style={{ color: "#37d29a", margin: "6px 0" }}>{notice}</div>}

      <div className="panel" style={{ display: "flex", gap: 12, alignItems: "center" }}>
        <label style={{ display: "flex", gap: 6, alignItems: "center", margin: 0 }}>
          <input
            type="checkbox"
            checked={unreadOnly}
            onChange={(e) => setUnreadOnly(e.target.checked)}
            style={{ width: "auto" }}
          />
          <span>{t("notifications.unreadOnly")}</span>
        </label>
        <select value={channel} onChange={(e) => setChannel(e.target.value as typeof channel)}>
          {channels.map((f) => (
            <option key={f.value} value={f.value}>
              {f.label}
            </option>
          ))}
        </select>
        <button className="ghost sm" onClick={markAll}>
          {t("notifications.markAll")}
        </button>
      </div>

      <div className="panel">
        {items.length === 0 && <div className="empty">{t("notifications.none")}</div>}
        {items.map((n) => (
          <div key={n.id} className="event-line">
            <time>{new Date(n.created_at).toLocaleString(locale)}</time>
            <ChannelPill channel={n.channel} />
            {n.severity && <SeverityPill severity={n.severity} />}
            {n.channel !== "web" && <DeliveryPill status={n.status} />}
            <span>
              <b>{n.title}</b>
              {n.body && <span className="muted"> — {n.body}</span>}
              {n.error && (
                <span className="muted">
                  {t("notifications.errorPrefix")}
                  {n.error}
                </span>
              )}
            </span>
            {n.channel !== "web" && n.status === "failed" && (
              <button className="sm ghost" onClick={() => retry(n.id)}>
                {t("notifications.retry")}
              </button>
            )}
            {!n.is_read && (
              <button className="sm ghost" onClick={() => markRead(n.id)}>
                {t("notifications.markRead")}
              </button>
            )}
          </div>
        ))}
      </div>
    </RequireAuth>
  );
}
