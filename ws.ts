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
