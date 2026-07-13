/* app.js — TermAId Web client (vanilla JS, no build step). */

const API = ""; // same origin
let token = localStorage.getItem("termaid_access");
let ws = null;
const history = [];
let histIdx = -1;

const $ = (id) => document.getElementById(id);

/* ---------------- auth ---------------- */
async function login() {
  const u = $("username").value.trim();
  const p = $("password").value;
  const body = new URLSearchParams({ username: u, password: p });
  const r = await fetch(`${API}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!r.ok) return authMsg("login failed — check credentials", true);
  const data = await r.json();
  token = data.access_token;
  localStorage.setItem("termaid_access", token);
  localStorage.setItem("termaid_refresh", data.refresh_token);
  enterApp();
}

async function register() {
  const u = $("username").value.trim();
  const p = $("password").value;
  if (u.length < 2 || p.length < 4) return authMsg("username ≥2, password ≥4 chars", true);
  const r = await fetch(`${API}/api/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: u, password: p }),
  });
  if (r.status === 409) return authMsg("username already taken", true);
  if (!r.ok) return authMsg("registration failed", true);
  authMsg("account created — logging you in…", false);
  await login();
}

function authMsg(text, isErr) {
  const el = $("authMsg");
  el.textContent = text;
  el.className = "msg " + (isErr ? "error" : "ok");
}

function logout() {
  localStorage.removeItem("termaid_access");
  localStorage.removeItem("termaid_refresh");
  if (ws) ws.close();
  location.reload();
}

/* ---------------- app ---------------- */
function enterApp() {
  $("login").classList.add("hidden");
  $("app").classList.remove("hidden");
  connectWs();
  $("cmd").focus();
}

function connectWs() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws/terminal?token=${token}`);

  ws.onopen = () => setStatus("● live", true);
  ws.onclose = () => setStatus("○ disconnected", false);
  ws.onerror = () => setStatus("○ error", false);

  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    if (m.type === "banner") {
      print(m.text, "banner");
    } else if (m.type === "result") {
      if (m.output) print(m.output, m.ok ? "out" : "out err");
      print(`${m.module || "?"} · ${m.ms}ms`, "meta");
    }
  };
}

function setStatus(text, live) {
  const el = $("status");
  el.textContent = text;
  el.className = "status" + (live ? " live" : "");
}

function send() {
  const input = $("cmd");
  const line = input.value.trim();
  if (!line) return;
  echo(line);
  history.push(line);
  histIdx = history.length;

  if (line === "clear") { $("terminal").innerHTML = ""; input.value = ""; return; }
  if (line === "help") { showHelp(); input.value = ""; return; }

  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(line);
  } else {
    print("not connected — reconnecting…", "out err");
    connectWs();
  }
  input.value = "";
}

async function showHelp() {
  const r = await fetch(`${API}/api/commands`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!r.ok) return print("could not load command list", "out err");
  const data = await r.json();
  print(`${data.count} commands available. A few to try:`, "banner");
  const sample = data.commands.filter((c) =>
    /^(calc|text|regex|diff|qr|password|json|base)/.test(c)).slice(0, 24);
  print(sample.join("   "), "out");
  print("type any  module.command  with its arguments.", "meta");
}

/* ---------------- terminal rendering ---------------- */
function print(text, cls) {
  const div = document.createElement("div");
  div.className = cls || "out";
  div.textContent = text;
  const t = $("terminal");
  t.appendChild(div);
  t.scrollTop = t.scrollHeight;
}
function echo(text) {
  const div = document.createElement("div");
  div.className = "cmd-echo";
  div.textContent = text;
  $("terminal").appendChild(div);
}

/* ---------------- events ---------------- */
$("loginBtn").onclick = login;
$("registerBtn").onclick = register;
$("logoutBtn").onclick = logout;
$("password").addEventListener("keydown", (e) => { if (e.key === "Enter") login(); });

$("cmd").addEventListener("keydown", (e) => {
  if (e.key === "Enter") send();
  else if (e.key === "ArrowUp") {
    if (histIdx > 0) { histIdx--; $("cmd").value = history[histIdx]; }
    e.preventDefault();
  } else if (e.key === "ArrowDown") {
    if (histIdx < history.length - 1) { histIdx++; $("cmd").value = history[histIdx]; }
    else { histIdx = history.length; $("cmd").value = ""; }
    e.preventDefault();
  }
});

// auto-enter if we already have a token
if (token) enterApp();
