"use client";

import { useState } from "react";

import { RequireAuth } from "@/components/RequireAuth";
import { post } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function SettingsPage() {
  const { session, logout } = useAuth();
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

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

  return (
    <RequireAuth>
      <h2 className="page-title">Settings</h2>

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
      </div>
    </RequireAuth>
  );
}