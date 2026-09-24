"use client";

import { useEffect, useState } from "react";

import { getToken, wsUrl } from "@/lib/api";

export interface WsEvent {
  type: string;
  data: Record<string, unknown>;
  at: number;
}

export function useRealtime(): { events: WsEvent[]; connected: boolean } {
  const [events, setEvents] = useState<WsEvent[]>([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const token = getToken();
    if (!token) return;

    let ws: WebSocket | null = null;
    let closed = false;

    const connect = () => {
      ws = new WebSocket(wsUrl(`/ws?token=${encodeURIComponent(token)}`));
      ws.onopen = () => setConnected(true);
      ws.onclose = () => {
        setConnected(false);
        if (!closed) setTimeout(connect, 3000);
      };
      ws.onerror = () => ws?.close();
      ws.onmessage = (ev) => {
        try {
          const parsed = JSON.parse(ev.data as string);
          setEvents((prev) => [
            {
              type: String(parsed.type ?? "event"),
              data: parsed as Record<string, unknown>,
              at: Date.now(),
            },
            ...prev,
          ].slice(0, 100));
        } catch {
          /* ignore malformed frames */
        }
      };
    };

    connect();

    return () => {
      closed = true;
      ws?.close();
    };
  }, []);

  return { events, connected };
}