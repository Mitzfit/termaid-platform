// native.ts — bridge to native capabilities.
//
// In the Tauri app (desktop/mobile) we call the in-process Rust command via
// `invoke` — this is the offline path, no backend round-trip, works on phones
// where there's no Python. In a plain browser we fall back to the backend's
// /api/scan (local mode only). Same call site, right transport automatically.

import type { CommandResult } from "./types";

interface TauriGlobal {
  core: { invoke: <T>(cmd: string, args?: Record<string, unknown>) => Promise<T> };
}
declare global {
  interface Window {
    __TAURI__?: TauriGlobal;
    __TAURI_INTERNALS__?: unknown;
  }
}

export function isTauri(): boolean {
  return typeof window !== "undefined" &&
    (window.__TAURI__ !== undefined || window.__TAURI_INTERNALS__ !== undefined);
}

export interface ScanResult {
  host: string;
  open: { port: number; service: string }[];
  scanned: number;
  ms: number;
}

const BASE = import.meta.env.VITE_API_BASE ?? "";

export async function nativeScan(
  host: string, start = 1, end = 1024, timeoutMs = 300,
): Promise<ScanResult> {
  if (isTauri() && window.__TAURI__) {
    // In-process Rust — the offline-mobile path.
    return window.__TAURI__.core.invoke<ScanResult>("native_scan", {
      host, start, end, timeoutMs,
    });
  }
  // Browser: go through the backend (server gates this to local mode).
  const token = localStorage.getItem("termaid_access");
  const res = await fetch(`${BASE}/api/scan`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ host, start, end, timeout_ms: timeoutMs }),
  });
  if (!res.ok) throw new Error(`scan failed: ${res.status}`);
  return res.json();
}

/** Render a scan result the same way the backend terminal does. */
export function formatScan(r: ScanResult): CommandResult {
  if (r.open.length === 0) {
    return { ok: true, module: "scan", command: "scan.ports",
             output: `${r.host}: no open ports in ${r.scanned} scanned (${r.ms}ms)`, ms: r.ms };
  }
  const lines = [`${r.host} — ${r.open.length} open of ${r.scanned} scanned (${r.ms}ms):`];
  for (const p of r.open) lines.push(`  ${String(p.port).padStart(5)}/tcp  ${p.service}`);
  return { ok: true, module: "scan", command: "scan.ports", output: lines.join("\n"), ms: r.ms };
}

export interface WalkResult {
  root: string;
  files: number;
  dirs: number;
  bytes: number;
  largest: { path: string; bytes: number }[];
  ms: number;
}

export async function nativeWalk(path: string, topN = 10): Promise<WalkResult> {
  if (isTauri() && window.__TAURI__) {
    return window.__TAURI__.core.invoke<WalkResult>("native_walk", { path, topN });
  }
  // Browser path goes through the backend command runner (local mode gates it).
  const token = localStorage.getItem("termaid_access");
  const res = await fetch(`${BASE}/api/exec`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ command: `fs.walk ${path} ${topN}` }),
  });
  if (!res.ok) throw new Error(`walk failed: ${res.status}`);
  // /api/exec returns a CommandResult; the structured form is only via Tauri.
  const r = await res.json();
  throw new Error(r.output ?? "walk requires the native binary");
}

function human(n: number): string {
  let f = n;
  for (const u of ["B", "KB", "MB", "GB", "TB"]) {
    if (f < 1024 || u === "TB") return u === "B" ? `${Math.round(f)}B` : `${f.toFixed(1)}${u}`;
    f /= 1024;
  }
  return `${f.toFixed(1)}TB`;
}

export function formatWalk(r: WalkResult): CommandResult {
  const lines = [`${r.root} — ${r.files} files, ${r.dirs} dirs, ${human(r.bytes)} (${r.ms}ms)`];
  if (r.largest.length) {
    lines.push("largest:");
    for (const f of r.largest) lines.push(`  ${human(f.bytes).padStart(9)}  ${f.path}`);
  }
  return { ok: true, module: "fs", command: "fs.walk", output: lines.join("\n"), ms: r.ms };
}
