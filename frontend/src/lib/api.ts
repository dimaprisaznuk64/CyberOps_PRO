const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "cyberops.access";
const REFRESH_KEY = "cyberops.refresh";

export function apiUrl(path: string): string {
  const base = API_URL.replace(/\/$/, "");
  return base + path;
}

export function wsUrl(path: string): string {
  const base = apiUrl(path);
  if (base.startsWith("https")) return "wss" + base.slice(5);
  if (base.startsWith("http")) return "ws" + base.slice(4);
  return base;
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setTokens(access: string, refresh: string): void {
  window.localStorage.setItem(TOKEN_KEY, access);
  window.localStorage.setItem(REFRESH_KEY, refresh);
}

export function clearTokens(): void {
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(REFRESH_KEY);
}

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function api<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const resp = await fetch(apiUrl(path), {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (resp.status === 204) return undefined as T;

  let data: unknown = null;
  const ct = resp.headers.get("content-type") ?? "";
  if (ct.includes("json")) {
    try {
      data = await resp.json();
    } catch {
      data = null;
    }
  }

  if (!resp.ok) {
    if (resp.status === 401 && typeof window !== "undefined") {
      clearTokens();
      window.location.href = "/login";
    }
    const detail =
      data && typeof data === "object" && "detail" in data
        ? String((data as Record<string, unknown>).detail)
        : `HTTP ${resp.status}`;
    throw new ApiError(resp.status, detail);
  }

  return data as T;
}

export const get = <T>(path: string) => api<T>("GET", path);
export const post = <T>(path: string, body?: unknown) => api<T>("POST", path, body);
export const patch = <T>(path: string, body?: unknown) => api<T>("PATCH", path, body);
export const del = (path: string) => api<null>("DELETE", path);

/**
 * Завантажує файл із захищеного ендпоинта.
 *
 * Звичайний <a href> не підійде: запит пішов би без Authorization-заголовка,
 * тож gateway відповів би 401. Тому тягнемо blob і віддаємо його браузеру
 * через тимчасовий object URL.
 */
export async function download(path: string, filename: string): Promise<void> {
  const token = getToken();
  const resp = await fetch(apiUrl(path), {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!resp.ok) {
    throw new ApiError(resp.status, `HTTP ${resp.status}`);
  }
  const url = URL.createObjectURL(await resp.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}