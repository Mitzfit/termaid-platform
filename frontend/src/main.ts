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
  
  const dot = $("statusDot");
  if (dot) dot.className = "dot" + (live ? " live" : "");
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
    onAuthFailed: () => logout(),
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

  // "health" / "blocked" → thin wrappers over the backend's status endpoints
  // (neither is otherwise surfaced anywhere in the UI).
  if (line === "health") {
    api.health()
      .then((h) => term.out(`status=${h.status}  mode=${h.mode}  commands=${h.commands}  ai=${h.ai}`))
      .catch((err) => term.out(String(err), true));
    return;
  }
  if (line === "blocked") {
    api.blocked()
      .then((b) => {
        const entries = Object.entries(b.blocked);
        if (entries.length === 0) { term.out(`[${b.mode}] no modules blocked`); return; }
        term.out(`[${b.mode}] blocked modules:\n` + entries.map(([m, r]) => `  ${m}: ${r}`).join("\n"));
      })
      .catch((err) => term.out(String(err), true));
    return;
  }

  // "admin-users" / "admin-health" → the seeded root account's user
  // management + system health views. The API 403s non-admins cleanly.
  if (line === "admin-users") {
    api.adminUsers()
      .then((users) => {
        const lines = users.map((u) =>
          `  ${u.id}  ${u.username}${u.is_admin ? " (admin)" : ""}${u.is_active ? "" : " [disabled]"}`);
        term.out(`[admin] ${users.length} user(s):\n` + lines.join("\n"));
      })
      .catch((err) => term.out(String(err), true));
    return;
  }
  if (line === "admin-health") {
    api.adminHealth()
      .then((h) => {
        term.out(`status=${h.status}  mode=${h.mode}  commands=${h.commands}  ai=${h.ai}\n\n${h.process}\n\n${h.threads}`);
      })
      .catch((err) => term.out(String(err), true));
    return;
  }

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
