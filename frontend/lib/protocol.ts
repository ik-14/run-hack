/** Mirror of the server protocol in backend/app/protocol.py (DESIGN.md §4). */

export type LobbyPlayer = {
  pid: string;
  name: string;
  color: string;
  connected: boolean;
};

export type Bounds = {
  south: number;
  west: number;
  north: number;
  east: number;
};

export type LobbyState = {
  type: "lobby";
  room: string;
  status: "lobby" | "running";
  host: string;
  round_minutes: number;
  bounds: Bounds | null;
  players: LobbyPlayer[];
};

export type ServerMessage =
  | { type: "joined"; pid: string; room: string; color: string }
  | LobbyState
  | { type: "started"; round_minutes: number }
  | { type: "error"; detail: string };

export type ClientMessage =
  | { type: "create"; name: string; color: string }
  | { type: "join"; room: string; name: string; color: string }
  | { type: "config"; round_minutes: number }
  | ({ type: "bounds" } & Bounds)
  | { type: "start" };

export const ROUND_MINUTE_CHOICES = [5, 10, 20] as const;
export const ROOM_CODE_LENGTH = 4;

/** Must stay in step with PALETTE in backend/app/protocol.py. */
export const PALETTE = [
  "#84cc16",
  "#f97316",
  "#06b6d4",
  "#ec4899",
  "#a855f7",
  "#eab308",
  "#ef4444",
  "#22d3ee",
] as const;

export function serverUrl(): string {
  const configured = process.env.NEXT_PUBLIC_WS_URL;
  if (configured) return configured;
  if (typeof window === "undefined") return "ws://localhost:8000/ws";
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.hostname}:8000/ws`;
}
