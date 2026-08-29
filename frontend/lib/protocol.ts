/** Mirror of the server protocol in backend/app/protocol.py (DESIGN.md §4). */

export type LobbyPlayer = {
  pid: string;
  name: string;
  connected: boolean;
};

export type LobbyState = {
  type: "lobby";
  room: string;
  status: "lobby" | "running";
  host: string;
  round_minutes: number;
  players: LobbyPlayer[];
};

export type ServerMessage =
  | { type: "joined"; pid: string; room: string }
  | LobbyState
  | { type: "started"; round_minutes: number }
  | { type: "error"; detail: string };

export type ClientMessage =
  | { type: "create"; name: string }
  | { type: "join"; room: string; name: string }
  | { type: "config"; round_minutes: number }
  | { type: "start" };

export const ROUND_MINUTE_CHOICES = [5, 10, 20] as const;
export const ROOM_CODE_LENGTH = 4;

export function serverUrl(): string {
  const configured = process.env.NEXT_PUBLIC_WS_URL;
  if (configured) return configured;
  if (typeof window === "undefined") return "ws://localhost:8000/ws";
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.hostname}:8000/ws`;
}
