"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const { login, session, ready } = useAuth();
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
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
      await login(username, password);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Помилка входу");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="panel" style={{ maxWidth: 420, margin: "40px auto" }}>
      <h3>Вхід</h3>
      {error && <div className="error">{error}</div>}
      <form onSubmit={submit}>
        <label>Username</label>
        <input value={username} onChange={(e) => setUsername(e.target.value)} autoFocus />
        <label>Password</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <div style={{ marginTop: 14 }}>
          <button type="submit" disabled={busy || !username || !password}>
            {busy ? "Вхід…" : "Увійти"}
          </button>
        </div>
      </form>
      <p className="small muted" style={{ marginTop: 14 }}>
        Немає акаунта? <a href="/register">Зареєструватися</a>
      </p>
    </div>
  );
}