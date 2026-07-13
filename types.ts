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
