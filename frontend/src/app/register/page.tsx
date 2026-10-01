"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";

export default function RegisterPage() {
  const { register, session, ready } = useAuth();
  const { t } = useI18n();
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [email, setEmail] = useState("");
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
      await register(username, password, email || null);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("register.error"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="panel" style={{ maxWidth: 420, margin: "40px auto" }}>
      <h3>{t("register.title")}</h3>
      {error && <div className="error">{error}</div>}
      <form onSubmit={submit}>
        <label>{t("register.username")}</label>
        <input value={username} onChange={(e) => setUsername(e.target.value)} autoFocus />
        <label>{t("register.password")}</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <label>{t("register.email")}</label>
        <input value={email} onChange={(e) => setEmail(e.target.value)} />
        <div style={{ marginTop: 14 }}>
          <button
            type="submit"
            disabled={busy || username.length < 3 || password.length < 8}
          >
            {busy ? t("register.busy") : t("register.submit")}
          </button>
        </div>
      </form>
      <p className="small muted" style={{ marginTop: 14 }}>
        {t("register.note")}
      </p>
      <p className="small muted" style={{ marginTop: 8 }}>
        {t("register.haveAccount")} <a href="/login">{t("register.loginLink")}</a>
      </p>
    </div>
  );
}