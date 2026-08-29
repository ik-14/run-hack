"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  Bounds,
  ClientMessage,
  LobbyState,
  Point,
  ServerMessage,
  serverUrl,
} from "@/lib/protocol";

export type Connection = "idle" | "connecting" | "open" | "reconnecting" | "closed";

export type Lobby = {
  connection: Connection;
  pid: string | null;
  lobby: LobbyState | null;
  error: string | null;
  /** The most recent loop closure, for the claim banner. */
  lastClaim: { pid: string; area_m2: number } | null;
  /** Set while you are outside the play area, counting down to disqualification. */
  outOfBounds: { graceLeftS: number; disqualified: boolean } | null;
  isHost: boolean;
  createRoom: (name: string, color: string) => void;
  joinRoom: (room: string, name: string, color: string) => void;
  setRoundMinutes: (minutes: number) => void;
  setBounds: (bounds: Bounds) => void;
  sendPosition: (fix: { lat: number; lng: number; acc: number; t: number }) => void;
  start: () => void;
  leave: () => void;
};

type PositionUpdate = Extract<ServerMessage, { type: "pos" }>;

/** Where the pid is kept so a reload (or a browser killing the tab) can rejoin. */
const SESSION_KEY = "runner-io-session";
const FIRST_RETRY_MS = 500;
const MAX_RETRY_MS = 8000;

function applyPosition(lobby: LobbyState, update: PositionUpdate): LobbyState {
  return {
    ...lobby,
    players: lobby.players.map((player) =>
      player.pid === update.pid
        ? {
            ...player,
            lat: update.lat,
            lng: update.lng,
            trail: update.extend
              ? [...player.trail, [update.lat, update.lng] as Point]
              : player.trail,
          }
        : player,
    ),
  };
}

function storedSession(): { room: string; pid: string } | null {
  if (typeof sessionStorage === "undefined") return null;
  const raw = sessionStorage.getItem(SESSION_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as { room?: unknown; pid?: unknown };
    if (typeof parsed.room !== "string" || typeof parsed.pid !== "string") return null;
    return { room: parsed.room, pid: parsed.pid };
  } catch {
    return null;
  }
}

export function useLobby(): Lobby {
  const socketRef = useRef<WebSocket | null>(null);
  /** The create/join/rejoin message that opens a connection, resent on every retry. */
  const entryRef = useRef<ClientMessage | null>(null);
  const retryRef = useRef<number>(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const aliveRef = useRef(true);
  const [connection, setConnection] = useState<Connection>("idle");
  const [pid, setPid] = useState<string | null>(null);
  const [lobby, setLobby] = useState<LobbyState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastClaim, setLastClaim] = useState<{ pid: string; area_m2: number } | null>(null);
  const [outOfBounds, setOutOfBounds] = useState<Lobby["outOfBounds"]>(null);
  const pidRef = useRef<string | null>(null);
  const roomRef = useRef<string | null>(null);
  const openRef = useRef<(entry: ClientMessage) => void>(() => {});

  const forget = useCallback(() => {
    entryRef.current = null;
    pidRef.current = null;
    roomRef.current = null;
    sessionStorage.removeItem(SESSION_KEY);
  }, []);

  const send = useCallback((message: ClientMessage) => {
    const socket = socketRef.current;
    if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify(message));
  }, []);

  const open = useCallback(
    (entry: ClientMessage) => {
      if (timerRef.current) clearTimeout(timerRef.current);
      socketRef.current?.close();
      entryRef.current = entry;
      setError(null);
      setConnection(entry.type === "rejoin" ? "reconnecting" : "connecting");

      const socket = new WebSocket(serverUrl());
      socketRef.current = socket;

      socket.onopen = () => {
        retryRef.current = 0;
        setConnection("open");
        socket.send(JSON.stringify(entry));
      };
      socket.onmessage = (event) => {
        const message = JSON.parse(event.data as string) as ServerMessage;
        if (message.type === "joined") {
          pidRef.current = message.pid;
          roomRef.current = message.room;
          sessionStorage.setItem(
            SESSION_KEY,
            JSON.stringify({ room: message.room, pid: message.pid }),
          );
          setPid(message.pid);
        } else if (message.type === "lobby") {
          setLobby(message);
        } else if (message.type === "pos") {
          setLobby((prev) => (prev ? applyPosition(prev, message) : prev));
        } else if (message.type === "claim") {
          setLastClaim({ pid: message.pid, area_m2: message.area_m2 });
        } else if (message.type === "oob") {
          if (message.pid !== pidRef.current) return;
          if (message.grace_left_s === null && !message.disqualified) {
            setOutOfBounds(null);
            return;
          }
          setOutOfBounds({
            graceLeftS: message.grace_left_s ?? 0,
            disqualified: message.disqualified,
          });
          // Buzz the phone: the runner is looking at the pavement, not the screen.
          navigator.vibrate?.(message.disqualified ? [400, 100, 400] : 300);
        } else if (message.type === "error") {
          setError(message.detail);
          // The room is gone or the pid was dropped: stop retrying and start over.
          if (entryRef.current?.type === "rejoin") {
            forget();
            setLobby(null);
            setPid(null);
            setConnection("idle");
            socket.close();
          }
        }
      };
      socket.onclose = () => {
        // A socket we already replaced must not schedule retries of its own.
        if (socketRef.current !== socket) return;
        socketRef.current = null;
        const room = roomRef.current;
        const player = pidRef.current;
        if (!aliveRef.current || room === null || player === null) {
          if (aliveRef.current && entryRef.current !== null) setConnection("closed");
          return;
        }
        setConnection("reconnecting");
        const wait = Math.min(FIRST_RETRY_MS * 2 ** retryRef.current, MAX_RETRY_MS);
        retryRef.current += 1;
        timerRef.current = setTimeout(
          () => openRef.current({ type: "rejoin", room, pid: player }),
          wait,
        );
      };
      socket.onerror = () => setError("could not reach the game server");
    },
    [forget],
  );

  openRef.current = open;

  const sendPosition = useCallback(
    (fix: { lat: number; lng: number; acc: number; t: number }) =>
      send({ type: "pos", ...fix }),
    [send],
  );

  const leave = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    send({ type: "leave" });
    socketRef.current?.close();
    socketRef.current = null;
    forget();
    retryRef.current = 0;
    setConnection("idle");
    setPid(null);
    setLobby(null);
    setError(null);
    setLastClaim(null);
    setOutOfBounds(null);
  }, [forget, send]);

  // Resume the round after a reload, and the moment an unlocked phone comes back.
  useEffect(() => {
    aliveRef.current = true;
    const resume = () => {
      if (document.visibilityState !== "visible") return;
      if (socketRef.current?.readyState === WebSocket.OPEN) return;
      const session = storedSession();
      if (!session) return;
      pidRef.current = session.pid;
      roomRef.current = session.room;
      retryRef.current = 0;
      openRef.current({ type: "rejoin", room: session.room, pid: session.pid });
    };
    resume();
    document.addEventListener("visibilitychange", resume);
    window.addEventListener("online", resume);
    return () => {
      aliveRef.current = false;
      document.removeEventListener("visibilitychange", resume);
      window.removeEventListener("online", resume);
      if (timerRef.current) clearTimeout(timerRef.current);
      socketRef.current?.close();
    };
  }, []);

  return {
    connection,
    pid,
    lobby,
    error,
    lastClaim,
    outOfBounds,
    isHost: lobby !== null && pid !== null && lobby.host === pid,
    createRoom: (name, color) => open({ type: "create", name, color }),
    joinRoom: (room, name, color) =>
      open({ type: "join", room: room.toUpperCase(), name, color }),
    setRoundMinutes: (minutes) => send({ type: "config", round_minutes: minutes }),
    setBounds: (bounds) => send({ type: "bounds", ...bounds }),
    sendPosition,
    start: () => send({ type: "start" }),
    leave,
  };
}
