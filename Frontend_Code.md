# Agent 08 — Frontend / UI: OWNED SOURCE CODE

Hand edits back as .ts/.html/.css text.

## `frontend/src/types.ts`

```ts
// types.ts — shared contracts between the backend and the UI.
// These mirror backend/schemas.py and the WebSocket protocol in main.py.

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface CommandResult {
  ok: boolean;
  module?: string | null;
  command?: string | null;
  output: string;
  ms: number;
}

export interface ModuleMeta {
  version: string;
  description: string;
  commands: string[];
  category: "safe" | "ai" | "system" | "dangerous" | "uncategorised";
}

export interface HistoryItem {
  id: number;
  command: string;
  module: string | null;
  ok: boolean;
  duration_ms: number;
  created_at: string;
}

// ---- WebSocket protocol ----
export type ClientMessage =
  | { type: "exec"; payload: string }
  | { type: "chat"; payload: string };

export type ServerMessage =
  | { type: "banner"; text: string }
  | ({ type: "result" } & CommandResult)
  | { type: "chat_delta"; text: string }
  | { type: "chat_done" };

```

## `frontend/src/api.ts`

```ts
// api.ts — typed REST client. Handles auth + token storage + auto-refresh.

import type { TokenPair, CommandResult, ModuleMeta, HistoryItem } from "./types";

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

async function tryRefresh(): Promise<boolean> {
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
};

```

## `frontend/src/ws.ts`

```ts
// ws.ts — typed WebSocket client. Auto-reconnects, surfaces streaming chat.

import type { ClientMessage, ServerMessage } from "./types";
import { tokens } from "./api";

export interface TerminalHandlers {
  onBanner: (text: string) => void;
  onResult: (msg: Extract<ServerMessage, { type: "result" }>) => void;
  onChatDelta: (text: string) => void;
  onChatDone: () => void;
  onStatus: (connected: boolean) => void;
}

export class TerminalSocket {
  private ws: WebSocket | null = null;
  private reconnectTimer: number | null = null;

  constructor(private handlers: TerminalHandlers) {}

  connect(): void {
    const token = tokens.access;
    if (!token) return;
    const base = import.meta.env.VITE_API_BASE ?? location.origin;
    const url = new URL("/ws/terminal", base);
    url.protocol = url.protocol.replace("http", "ws");
    url.searchParams.set("token", token);

    this.ws = new WebSocket(url.toString());
    this.ws.onopen = () => this.handlers.onStatus(true);
    this.ws.onclose = () => {
      this.handlers.onStatus(false);
      this.scheduleReconnect();
    };
    this.ws.onerror = () => this.ws?.close();
    this.ws.onmessage = (ev) => this.dispatch(JSON.parse(ev.data) as ServerMessage);
  }

  private dispatch(msg: ServerMessage): void {
    switch (msg.type) {
      case "banner": this.handlers.onBanner(msg.text); break;
      case "result": this.handlers.onResult(msg); break;
      case "chat_delta": this.handlers.onChatDelta(msg.text); break;
      case "chat_done": this.handlers.onChatDone(); break;
    }
  }

  private send(msg: ClientMessage): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg));
    } else {
      this.connect();
    }
  }

  exec(line: string): void { this.send({ type: "exec", payload: line }); }
  chat(prompt: string): void { this.send({ type: "chat", payload: prompt }); }

  private scheduleReconnect(): void {
    if (this.reconnectTimer !== null) return;
    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, 1500);
  }

  close(): void { this.ws?.close(); }
}

```

## `frontend/src/native.ts`

```ts
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

```

## `frontend/src/terminal.ts`

```ts
// terminal.ts — minimal DOM terminal renderer (no framework).

export class Terminal {
  private el: HTMLElement;
  private streamingLine: HTMLElement | null = null;

  constructor(container: HTMLElement) {
    this.el = container;
  }

  private line(cls: string, text: string): HTMLElement {
    const div = document.createElement("div");
    div.className = cls;
    div.textContent = text;
    this.el.appendChild(div);
    this.el.scrollTop = this.el.scrollHeight;
    return div;
  }

  echo(text: string): void { this.line("cmd-echo", text); }
  out(text: string, isError = false): void { this.line(isError ? "out err" : "out", text); }
  meta(text: string): void { this.line("meta", text); }
  banner(text: string): void { this.line("banner", text); }
  clear(): void { this.el.innerHTML = ""; }

  // streaming AI: append tokens into one growing line
  beginStream(): void {
    this.streamingLine = this.line("out stream", "");
  }
  appendStream(text: string): void {
    if (!this.streamingLine) this.beginStream();
    this.streamingLine!.textContent += text;
    this.el.scrollTop = this.el.scrollHeight;
  }
  endStream(): void { this.streamingLine = null; }
}

```

## `frontend/src/main.ts`

```ts
// main.ts — app wiring: login → terminal → websocket (exec + streaming chat).

import { api, tokens } from "./api";
import { TerminalSocket } from "./ws";
import { Terminal } from "./terminal";
import { nativeScan, formatScan, nativeWalk, formatWalk, isTauri } from "./native";
import "./style.css";

const $ = <T extends HTMLElement = HTMLElement>(id: string) =>
  document.getElementById(id) as T;

let term: Terminal;
let socket: TerminalSocket;
const cmdHistory: string[] = [];
let histIdx = 0;

function setStatus(text: string, live: boolean) {
  const el = $("status");
  el.textContent = text;
  el.className = "status" + (live ? " live" : "");
}

function enterApp() {
  $("login").classList.add("hidden");
  $("app").classList.remove("hidden");

  term = new Terminal($("terminal"));
  socket = new TerminalSocket({
    onBanner: (t) => term.banner(t),
    onResult: (m) => {
      if (m.output) term.out(m.output, !m.ok);
      term.meta(`${m.module ?? "?"} · ${m.ms}ms`);
    },
    onChatDelta: (t) => term.appendStream(t),
    onChatDone: () => term.endStream(),
    onStatus: (c) => setStatus(c ? "● live" : "○ reconnecting…", c),
  });
  socket.connect();
  $("cmd").focus();
}

function handleInput() {
  const input = $<HTMLInputElement>("cmd");
  const line = input.value.trim();
  if (!line) return;
  term.echo(line);
  cmdHistory.push(line);
  histIdx = cmdHistory.length;
  input.value = "";

  if (line === "clear") { term.clear(); return; }

  // "scan <host> [start] [end]" → native bridge (in-process on Tauri, /api/scan in browser)
  if (line.startsWith("scan ")) {
    const [, host, s, e] = line.split(/\s+/);
    term.meta(isTauri() ? "scanning natively (Rust, in-process)…" : "scanning via backend…");
    nativeScan(host, s ? Number(s) : 1, e ? Number(e) : 1024)
      .then((r) => { const f = formatScan(r); term.out(f.output); term.meta(`scan · ${r.ms}ms`); })
      .catch((err) => term.out(String(err), true));
    return;
  }

  // "walk <path> [topN]" → native fast directory walk (Tauri in-process / backend)
  if (line.startsWith("walk ")) {
    const [, path, n] = line.split(/\s+/);
    term.meta(isTauri() ? "walking natively (Rust, in-process)…" : "walking via backend…");
    nativeWalk(path, n ? Number(n) : 10)
      .then((r) => { const f = formatWalk(r); term.out(f.output); term.meta(`walk · ${r.ms}ms`); })
      .catch((err) => term.out(String(err), true));
    return;
  }

  // "?" or "ask " prefix → stream an AI chat; otherwise run a module command.
  if (line.startsWith("?") || line.startsWith("ask ")) {
    const prompt = line.replace(/^(\?|ask )/, "").trim();
    term.beginStream();
    socket.chat(prompt);
  } else {
    socket.exec(line);
  }
}

// ---- auth handlers ----
async function doLogin() {
  try {
    await api.login(
      $<HTMLInputElement>("username").value.trim(),
      $<HTMLInputElement>("password").value,
    );
    enterApp();
  } catch {
    authMsg("login failed — check credentials", true);
  }
}

async function doRegister() {
  const u = $<HTMLInputElement>("username").value.trim();
  const p = $<HTMLInputElement>("password").value;
  if (u.length < 2 || p.length < 4) return authMsg("username ≥2, password ≥4", true);
  try {
    await api.register(u, p);
    authMsg("account created — logging in…", false);
    await doLogin();
  } catch (e) {
    authMsg(String(e).includes("409") ? "username taken" : "registration failed", true);
  }
}

function authMsg(text: string, err: boolean) {
  const el = $("authMsg");
  el.textContent = text;
  el.className = "msg " + (err ? "error" : "ok");
}

function logout() {
  tokens.clear();
  socket?.close();
  location.reload();
}

// ---- events ----
$("loginBtn").onclick = doLogin;
$("registerBtn").onclick = doRegister;
$("logoutBtn").onclick = logout;
$("password").addEventListener("keydown", (e) => { if ((e as KeyboardEvent).key === "Enter") doLogin(); });

$("cmd").addEventListener("keydown", (ev) => {
  const e = ev as KeyboardEvent;
  const input = $<HTMLInputElement>("cmd");
  if (e.key === "Enter") handleInput();
  else if (e.key === "ArrowUp") { if (histIdx > 0) input.value = cmdHistory[--histIdx]; e.preventDefault(); }
  else if (e.key === "ArrowDown") {
    if (histIdx < cmdHistory.length - 1) input.value = cmdHistory[++histIdx];
    else { histIdx = cmdHistory.length; input.value = ""; }
    e.preventDefault();
  }
});

if (tokens.access) enterApp();

```

## `frontend/src/vite-env.d.ts`

```ts
/// <reference types="vite/client" />
// Minimal fallback so type-checking works even before `npm install`.
interface ImportMeta {
  readonly env: {
    readonly VITE_API_BASE?: string;
    readonly [key: string]: string | undefined;
  };
}

```

## `frontend/index.html`

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
  <meta name="theme-color" content="#0b0e14" />
  <title>TermAId</title>
</head>
<body>
  <div id="login" class="panel">
    <h1>Term<span class="accent">AId</span></h1>
    <p class="sub">cross-platform AI terminal</p>
    <input id="username" placeholder="username" autocomplete="username" />
    <input id="password" type="password" placeholder="password" autocomplete="current-password" />
    <div class="row">
      <button id="loginBtn">login</button>
      <button id="registerBtn" class="ghost">register</button>
    </div>
    <div id="authMsg" class="msg"></div>
  </div>

  <div id="app" class="hidden">
    <header>
      <span class="dot"></span>
      <span class="title">TermAId</span>
      <span id="status" class="status">connecting…</span>
      <button id="logoutBtn" class="ghost small">logout</button>
    </header>
    <div id="terminal" class="terminal"></div>
    <div class="inputline">
      <span class="prompt">›</span>
      <input id="cmd" autocomplete="off" spellcheck="false"
             placeholder="calc.hex 255   ·   ? explain TCP handshake   ·   clear" />
    </div>
  </div>

  <script type="module" src="/src/main.ts"></script>
</body>
</html>

```

## `frontend/src/style.css`

```css
:root {
  --bg: #0b0e14;
  --panel: #11151f;
  --fg: #c9d1d9;
  --dim: #6b7280;
  --accent: #39d353;
  --accent2: #58a6ff;
  --err: #f85149;
  --border: #1f2630;
  --mono: "JetBrains Mono", "SF Mono", "Fira Code", Consolas, monospace;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  height: 100vh;
  background:
    radial-gradient(1200px 600px at 80% -10%, rgba(57,211,83,0.06), transparent),
    var(--bg);
  color: var(--fg);
  font-family: var(--mono);
  display: flex;
  align-items: center;
  justify-content: center;
}

.hidden { display: none !important; }

/* ---- login ---- */
.panel {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 2rem 2.25rem;
  width: 340px;
  box-shadow: 0 20px 60px rgba(0,0,0,0.5);
}
.panel h1 { margin: 0; font-size: 1.9rem; letter-spacing: -1px; }
.accent { color: var(--accent); }
.ver { color: var(--dim); font-size: 0.9rem; font-weight: 400; }
.sub { color: var(--dim); margin: 0.3rem 0 1.4rem; font-size: 0.82rem; }
.panel input {
  width: 100%;
  background: #0b0e14;
  border: 1px solid var(--border);
  color: var(--fg);
  padding: 0.7rem 0.8rem;
  border-radius: 8px;
  margin-bottom: 0.7rem;
  font-family: var(--mono);
  outline: none;
}
.panel input:focus { border-color: var(--accent2); }
.row { display: flex; gap: 0.6rem; margin-top: 0.4rem; }
button {
  flex: 1;
  background: var(--accent);
  color: #07210f;
  border: none;
  padding: 0.65rem;
  border-radius: 8px;
  font-family: var(--mono);
  font-weight: 700;
  cursor: pointer;
  transition: filter 0.15s;
}
button:hover { filter: brightness(1.1); }
button.ghost { background: transparent; color: var(--fg); border: 1px solid var(--border); font-weight: 500; }
button.small { flex: none; padding: 0.3rem 0.7rem; font-size: 0.75rem; }
.msg { margin-top: 0.8rem; font-size: 0.8rem; min-height: 1rem; }
.msg.error { color: var(--err); }
.msg.ok { color: var(--accent); }

/* ---- app ---- */
#app {
  width: min(960px, 94vw);
  height: min(680px, 88vh);
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 14px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 20px 60px rgba(0,0,0,0.5);
}
header {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.7rem 1rem;
  border-bottom: 1px solid var(--border);
  background: #0d111a;
}
.dot { width: 11px; height: 11px; border-radius: 50%; background: var(--err);
       box-shadow: 18px 0 0 #f0b429, 36px 0 0 var(--accent); margin-right: 28px; }
.title { font-weight: 700; }
.status { color: var(--dim); font-size: 0.78rem; margin-left: auto; }
.status.live { color: var(--accent); }

.terminal {
  flex: 1;
  overflow-y: auto;
  padding: 1rem 1.1rem;
  font-size: 0.86rem;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
}
.terminal .cmd-echo { color: var(--accent2); }
.terminal .cmd-echo::before { content: "› "; color: var(--dim); }
.terminal .out { color: var(--fg); }
.terminal .out.err { color: var(--err); }
.terminal .meta { color: var(--dim); font-size: 0.72rem; }
.terminal .banner { color: var(--accent); }

.inputline {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.6rem 1.1rem;
  border-top: 1px solid var(--border);
  background: #0d111a;
}
.prompt { color: var(--accent); font-weight: 700; }
#cmd {
  flex: 1;
  background: transparent;
  border: none;
  color: var(--fg);
  font-family: var(--mono);
  font-size: 0.9rem;
  outline: none;
}

/* scrollbar */
.terminal::-webkit-scrollbar { width: 9px; }
.terminal::-webkit-scrollbar-thumb { background: #232b36; border-radius: 6px; }

/* streaming AI output */
.terminal .out.stream { color: #d2a8ff; }

```

## `frontend/vite.config.ts`

```ts
import { defineConfig } from "vite";

// Dev server proxies API + WS to the FastAPI backend on :8000, so the
// frontend runs on :5173 with hot-reload and no CORS headaches.
export default defineConfig({
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
      "/ws": { target: "ws://localhost:8000", ws: true },
    },
  },
  build: { outDir: "dist", emptyOutDir: true },
});

```

## `frontend/tsconfig.json`

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "skipLibCheck": true,
    "isolatedModules": true,
    "noEmit": true
  },
  "include": ["src"]
}

```

## `frontend/package.json`

```json
{
  "name": "termaid-frontend",
  "private": true,
  "version": "2.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  },
  "devDependencies": {
    "typescript": "^5.7.2",
    "vite": "^6.0.5"
  }
}

```
