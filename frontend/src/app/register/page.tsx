"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/lib/auth";

export default function RegisterPage() {
  const { register, session, ready } = useAuth();
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("user");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (ready && session) router.replace("/dashboard");
  }, [ready, session, router]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await register(username, password, email || null, role);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Помилка реєстрації");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="panel" style={{ maxWidth: 420, margin: "40px auto" }}>
      <h3>Реєстрація</h3>
      {error && <div className="error">{error}</div>}
      <form onSubmit={submit}>
        <label>Username (мін. 3)</label>
        <input value={username} onChange={(e) => setUsername(e.target.value)} autoFocus />
        <label>Password (мін. 8)</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <label>Email (необовʼязково)</label>
        <input value={email} onChange={(e) => setEmail(e.target.value)} />
        <label>Роль</label>
        <select value={role} onChange={(e) => setRole(e.target.value)}>
          <option value="user">user</option>
          <option value="analyst">analyst</option>
          <option value="admin">admin</option>
        </select>
        <div style={{ marginTop: 14 }}>
          <button
            type="submit"
            disabled={busy || username.length < 3 || password.length < 8}
          >
            {busy ? "Реєстрація…" : "Створити акаунт"}
          </button>
        </div>
      </form>
      <p className="small muted" style={{ marginTop: 14 }}>
        Вже є акаунт? <a href="/login">Увійти</a>
      </p>
    </div>
  );
}