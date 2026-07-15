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

export interface Health {
  status: string;
  mode: string;
  commands: number;
  ai: boolean;
}

export interface Blocked {
  mode: string;
  blocked: Record<string, string>;
}

export interface AdminUser {
  id: number;
  username: string;
  email: string | null;
  is_admin: boolean;
  is_active: boolean;
  created_at: string;
  last_login: string | null;
}

export interface AdminHealth extends Health {
  process: string;
  threads: string;
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
