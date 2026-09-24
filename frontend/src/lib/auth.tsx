"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { clearTokens, getToken, post, setTokens } from "@/lib/api";

interface Session {
  username: string;
  role: string;
  exp: number;
}

interface AuthState {
  session: Session | null;
  ready: boolean;
  login: (username: string, password: string) => Promise<Session>;
  register: (username: string, password: string, email: string | null, role: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

function decodeToken(token: string): Session | null {
  try {
    const payload = token.split(".")[1];
    const json = JSON.parse(atob(payload.replace(/-/g, "+").replace(/_/g, "/")));
    return {
      username: String(json.username ?? "?"),
      role: String(json.role ?? "user"),
      exp: Number(json.exp ?? 0),
    };
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      setReady(true);
      return;
    }
    const decoded = decodeToken(token);
    if (!decoded) {
      clearTokens();
      setReady(true);
      return;
    }
    if (decoded.exp * 1000 < Date.now()) {
      clearTokens();
      setReady(true);
      return;
    }
    setSession(decoded);
    setReady(true);
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const tokens = await post<{ access_token: string; refresh_token: string }>(
      "/api/v1/auth/login",
      { username, password }
    );
    setTokens(tokens.access_token, tokens.refresh_token);
    const session = decodeToken(tokens.access_token) ?? {
      username,
      role: "user",
      exp: 0,
    };
    setSession(session);
    return session;
  }, []);

  const register = useCallback(
    async (username: string, password: string, email: string | null, role: string) => {
      await post("/api/v1/auth/register", { username, password, email, role });
      await login(username, password);
    },
    [login]
  );

  const logout = useCallback(() => {
    clearTokens();
    setSession(null);
    window.location.href = "/login";
  }, []);

  const value = useMemo(
    () => ({ session, ready, login, register, logout }),
    [session, ready, login, register, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}