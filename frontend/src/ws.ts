// ws.ts — typed WebSocket client. Auto-reconnects, surfaces streaming chat.

import type { ClientMessage, ServerMessage } from "./types";
import { tokens, tryRefresh } from "./api";

// Backend closes the WS with this code when the token is missing/invalid/expired
// (backend/main.py's ws_terminal) — distinct from a plain network drop, which
// gets a normal close code and should just be retried as-is.
const WS_AUTH_FAILED = 4401;

export interface TerminalHandlers {
  onBanner: (text: string) => void;
  onResult: (msg: Extract<ServerMessage, { type: "result" }>) => void;
  onChatDelta: (text: string) => void;
  onChatDone: () => void;
  onStatus: (connected: boolean) => void;
  // Called when the access token is expired/invalid AND refreshing it also
  // failed (or there was no refresh token to try) — the caller should log
  // out and show the login screen again instead of retrying forever.
  onAuthFailed: () => void;
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
    this.ws.onclose = (ev) => {
      this.handlers.onStatus(false);
      if (ev.code === WS_AUTH_FAILED) {
        this.handleAuthFailure();
      } else {
        this.scheduleReconnect();
      }
    };
    this.ws.onerror = () => this.ws?.close();
    this.ws.onmessage = (ev) => this.dispatch(JSON.parse(ev.data) as ServerMessage);
  }

  private async handleAuthFailure(): Promise<void> {
    // The access token that's in the URL was already rejected — refreshing
    // gets a new one before we reconnect, instead of retrying with the same
    // dead token forever (which just silently loops instead of ever showing
    // the login screen again).
    if (await tryRefresh()) {
      this.connect();
    } else {
      this.handlers.onAuthFailed();
    }
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
