// api.ts — typed REST client. Handles auth + token storage + auto-refresh.

import type { TokenPair, CommandResult, ModuleMeta, HistoryItem, Health, Blocked, AdminUser, AdminHealth } from "./types";

const BASE = import.meta.env.VITE_API_BASE ?? "";

const store = {
  get access() { return localStorage.getItem("termaid_access"); },
  get refresh() { return localStorage.getItem("termaid_refresh"); },
  set(pair: TokenPair) {
    localStorage.setItem("termaid_access", pair.access_token);
    localStorage.setItem("termaid_refresh", pair.refresh_token);
  },
  clear() {
    localStorage.removeItem("termaid_access");
    localStorage.removeItem("termaid_refresh");
  },
};

export const tokens = store;

async function request<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  const headers = new Headers(init.headers);
  if (store.access) headers.set("Authorization", `Bearer ${store.access}`);
  const res = await fetch(`${BASE}${path}`, { ...init, headers });

  if (res.status === 401 && retry && store.refresh) {
    const refreshed = await tryRefresh();
    if (refreshed) return request<T>(path, init, false);
  }
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  return res.json() as Promise<T>;
}

export async function tryRefresh(): Promise<boolean> {
  try {
    const res = await fetch(`${BASE}/api/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: store.refresh }),
    });
    if (!res.ok) return false;
    store.set(await res.json());
    return true;
  } catch {
    return false;
  }
}

export const api = {
  async register(username: string, password: string, email?: string): Promise<void> {
    const res = await fetch(`${BASE}/api/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password, email }),
    });
    if (!res.ok) throw new Error(await res.text());
  },

  async login(username: string, password: string): Promise<TokenPair> {
    const body = new URLSearchParams({ username, password });
    const res = await fetch(`${BASE}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
    });
    if (!res.ok) throw new Error("login failed");
    const pair: TokenPair = await res.json();
    store.set(pair);
    return pair;
  },

  exec: (command: string) =>
    request<CommandResult>("/api/exec", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ command }),
    }),

  commands: () => request<{ count: number; commands: string[] }>("/api/commands"),
  modules: () => request<Record<string, ModuleMeta>>("/api/modules"),
  history: (limit = 50) => request<HistoryItem[]>(`/api/history?limit=${limit}`),
  health: () => request<Health>("/api/health"),
  blocked: () => request<Blocked>("/api/blocked"),

  // Admin-only (is_admin) — the API 403s cleanly for non-admins, so there's
  // no separate client-side gating needed here.
  adminUsers: () => request<AdminUser[]>("/api/admin/users"),
  adminHealth: () => request<AdminHealth>("/api/admin/health"),
};
