"use client";

import { useCallback, useEffect, useState } from "react";

import { RequireAuth } from "@/components/RequireAuth";
import { SeverityPill } from "@/components/Pills";
import { get, patch, post } from "@/lib/api";
import type { Notification } from "@/lib/types";

export default function NotificationsPage() {
  const [items, setItems] = useState<Notification[]>([]);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const qs = unreadOnly ? "?unread_only=true" : "";
      setItems(await get<Notification[]>(`/api/v1/notifications${qs}`));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Помилка");
    }
  }, [unreadOnly]);

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

  return (
    <RequireAuth>
      <h2 className="page-title">Notifications</h2>
      {error && <div className="error">{error}</div>}

      <div className="panel" style={{ display: "flex", gap: 12, alignItems: "center" }}>
        <label style={{ display: "flex", gap: 6, alignItems: "center", margin: 0 }}>
          <input
            type="checkbox"
            checked={unreadOnly}
            onChange={(e) => setUnreadOnly(e.target.checked)}
            style={{ width: "auto" }}
          />
          <span>Tільки непрочитані</span>
        </label>
        <button className="ghost sm" onClick={markAll}>
          Прочитати всі
        </button>
      </div>

      <div className="panel">
        {items.length === 0 && <div className="empty">Немає сповіщень</div>}
        {items.map((n) => (
          <div key={n.id} className="event-line">
            <time>{new Date(n.created_at).toLocaleString()}</time>
            {n.severity && <SeverityPill severity={n.severity} />}
            <span>
              <b>{n.title}</b>
              {n.body && <span className="muted"> — {n.body}</span>}
            </span>
            {!n.is_read && (
              <button className="sm ghost" onClick={() => markRead(n.id)}>
                Прочитано
              </button>
            )}
          </div>
        ))}
      </div>
    </RequireAuth>
  );
}