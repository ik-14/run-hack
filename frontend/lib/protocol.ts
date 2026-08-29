/** Mirror of the server protocol in backend/app/protocol.py (DESIGN.md §4). */

/** A trail vertex, as [lat, lng]. */
export type Point = [number, number];

export type LobbyPlayer = {
  pid: string;
  name: string;
  color: string;
  connected: boolean;
  lat: number | null;
  lng: number | null;
  trail: Point[];
  /** Claimed ground: one closed ring of [lat, lng] per owned area. */
  territory: Point[][];
  area_m2: number;
  outside: boolean;
  disqualified: boolean;
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
  | {
      type: "pos";
      pid: string;
      lat: number;
      lng: number;
      extend: boolean;
    }
  | { type: "claim"; pid: string; area_m2: number }
  /** grace_left_s is null once the runner is back inside the play area. */
  | { type: "oob"; pid: string; grace_left_s: number | null; disqualified: boolean }
  | { type: "error"; detail: string };

export type ClientMessage =
  | { type: "create"; name: string; color: string }
  | { type: "join"; room: string; name: string; color: string }
  | { type: "rejoin"; room: string; pid: string }
  | { type: "leave" }
  | { type: "config"; round_minutes: number }
  | ({ type: "bounds" } & Bounds)
  | { type: "start" }
  | { type: "pos"; lat: number; lng: number; acc: number; t: number };

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
