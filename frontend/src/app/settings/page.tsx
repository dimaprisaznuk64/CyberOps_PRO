"use client";

import { useCallback, useEffect, useState } from "react";

import { RequireAuth } from "@/components/RequireAuth";
import { get, patch, post } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { NotificationChannel, NotificationPreferences, NotifySeverity } from "@/lib/types";

const SEVERITIES: NotifySeverity[] = ["info", "low", "medium", "high", "critical"];

const SEVERITY_HINT: Record<NotifySeverity, string> = {
  info: "усі сповіщення",
  low: "від низького ризику",
  medium: "від середнього ризику",
  high: "лише високий і критичний",
  critical: "лише критичний",
};

export default function SettingsPage() {
  const { session, logout } = useAuth();
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [prefs, setPrefs] = useState<NotificationPreferences | null>(null);
  const [email, setEmail] = useState("");
  const [chatId, setChatId] = useState("");
  const [notifyEmail, setNotifyEmail] = useState(true);
  const [notifyTelegram, setNotifyTelegram] = useState(true);
  const [minSeverity, setMinSeverity] = useState<NotifySeverity>("high");
  const [testing, setTesting] = useState<NotificationChannel | null>(null);

  const loadPrefs = useCallback(async () => {
    try {
      const data = await get<NotificationPreferences>("/api/v1/notifications/preferences");
      setPrefs(data);
      setEmail(data.email ?? "");
      setChatId(data.telegram_chat_id ?? "");
      setNotifyEmail(data.notify_email);
      setNotifyTelegram(data.notify_telegram);
      setMinSeverity(data.notify_min_severity);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Помилка");
    }
  }, []);

  useEffect(() => {
    loadPrefs();
  }, [loadPrefs]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await post("/api/v1/auth/change-password", {
        old_password: oldPassword,
        new_password: newPassword,
      });
      setMessage("Пароль змінено");
      setOldPassword("");
      setNewPassword("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Помилка");
    } finally {
      setBusy(false);
    }
  };

  const savePrefs = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setMessage(null);
    try {
      const data = await patch<NotificationPreferences>(
        "/api/v1/notifications/preferences",
        {
          email: email.trim() || null,
          telegram_chat_id: chatId.trim() || null,
          notify_email: notifyEmail,
          notify_telegram: notifyTelegram,
          notify_min_severity: minSeverity,
        },
      );
      setPrefs(data);
      setMessage("Налаштування сповіщень збережено");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Помилка");
    }
  };

  const sendTest = async (channel: NotificationChannel) => {
    setError(null);
    setMessage(null);
    setTesting(channel);
    try {
      await post("/api/v1/notifications/test", { channel });
      setMessage(`Тестове повідомлення надіслано в ${channel.toUpperCase()}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Помилка");
    } finally {
      setTesting(null);
    }
  };

  return (
    <RequireAuth>
      <h2 className="page-title">Settings</h2>
      {error && <div className="error">{error}</div>}

      <div className="grid cols-2">
        <div className="panel">
          <h3>Профіль</h3>
          <table>
            <tbody>
              <tr>
                <td>Користувач</td>
                <td>{session?.username}</td>
              </tr>
              <tr>
                <td>Роль</td>
                <td>
                  <span className="pill neutral">{session?.role}</span>
                </td>
              </tr>
            </tbody>
          </table>
          <button className="ghost" onClick={logout} style={{ marginTop: 12 }}>
            Вийти
          </button>
        </div>

        <div className="panel">
          <h3>Зміна пароля</h3>
          {message && <div style={{ color: "#37d29a", margin: "6px 0" }}>{message}</div>}
          {error && <div className="error">{error}</div>}
          <form onSubmit={submit}>
            <label>Поточний пароль</label>
            <input
              type="password"
              value={oldPassword}
              onChange={(e) => setOldPassword(e.target.value)}
              required
            />
            <label>Новий пароль (мін. 8)</label>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
            />
            <div style={{ marginTop: 14 }}>
              <button type="submit" disabled={busy || newPassword.length < 8}>
                {busy ? "Зберігаємо…" : "Змінити пароль"}
              </button>
            </div>
          </form>
        </div>

        <div className="panel">
          <h3>Канали сповіщень</h3>
          {message && <div style={{ color: "#37d29a", margin: "6px 0" }}>{message}</div>}
          {!prefs ? (
            <div className="empty">Завантаження…</div>
          ) : (
            <form onSubmit={savePrefs}>
              <label>Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="sec@example.com"
              />
              <label>Telegram chat id</label>
              <input
                value={chatId}
                onChange={(e) => setChatId(e.target.value)}
                placeholder="-1001234567890"
              />
              <label>Мінімальний рівень</label>
              <select
                value={minSeverity}
                onChange={(e) => setMinSeverity(e.target.value as NotifySeverity)}
              >
                {SEVERITIES.map((s) => (
                  <option key={s} value={s}>
                    {s} — {SEVERITY_HINT[s]}
                  </option>
                ))}
              </select>

              <div style={{ display: "flex", gap: 16, marginTop: 12, flexWrap: "wrap" }}>
                <label style={{ display: "flex", gap: 6, alignItems: "center", margin: 0 }}>
                  <input
                    type="checkbox"
                    checked={notifyEmail}
                    onChange={(e) => setNotifyEmail(e.target.checked)}
                    style={{ width: "auto" }}
                  />
                  <span>Email {prefs.email_available ? "" : "(вимкнено на сервері)"}</span>
                </label>
                <label style={{ display: "flex", gap: 6, alignItems: "center", margin: 0 }}>
                  <input
                    type="checkbox"
                    checked={notifyTelegram}
                    onChange={(e) => setNotifyTelegram(e.target.checked)}
                    style={{ width: "auto" }}
                  />
                  <span>Telegram {prefs.telegram_available ? "" : "(вимкнено на сервері)"}</span>
                </label>
              </div>

              <p className="muted" style={{ marginBottom: 0 }}>
                Дієвий поріг: <b>{prefs.effective_min_severity}</b>. Серверний поріг{" "}
                <b>{prefs.server_min_severity}</b> — нижче нього не надсилаємо, тож ваш вибір
                спрацює лише якщо він суворіший.
              </p>

              <div style={{ marginTop: 14, display: "flex", gap: 8 }}>
                <button type="submit">Зберегти</button>
                <button
                  type="button"
                  className="ghost"
                  disabled={!prefs.email_available || !email.trim() || testing !== null}
                  onClick={() => sendTest("email")}
                >
                  {testing === "email" ? "Надсилаємо…" : "Тест Email"}
                </button>
                <button
                  type="button"
                  className="ghost"
                  disabled={!prefs.telegram_available || !chatId.trim() || testing !== null}
                  onClick={() => sendTest("telegram")}
                >
                  {testing === "telegram" ? "Надсилаємо…" : "Тест Telegram"}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </RequireAuth>
  );
}
