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

export type Connection = "idle" | "connecting" | "open" | "closed";

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

export function useLobby(): Lobby {
  const socketRef = useRef<WebSocket | null>(null);
  const queuedRef = useRef<ClientMessage | null>(null);
  const [connection, setConnection] = useState<Connection>("idle");
  const [pid, setPid] = useState<string | null>(null);
  const [lobby, setLobby] = useState<LobbyState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastClaim, setLastClaim] = useState<{ pid: string; area_m2: number } | null>(null);
  const [outOfBounds, setOutOfBounds] = useState<Lobby["outOfBounds"]>(null);
  const pidRef = useRef<string | null>(null);

  const send = useCallback((message: ClientMessage) => {
    const socket = socketRef.current;
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify(message));
    } else {
      queuedRef.current = message;
    }
  }, []);

  const connect = useCallback(
    (first: ClientMessage) => {
      socketRef.current?.close();
      setError(null);
      setConnection("connecting");
      queuedRef.current = first;

      const socket = new WebSocket(serverUrl());
      socketRef.current = socket;

      socket.onopen = () => {
        setConnection("open");
        const queued = queuedRef.current;
        queuedRef.current = null;
        if (queued) socket.send(JSON.stringify(queued));
      };
      socket.onmessage = (event) => {
        const message = JSON.parse(event.data as string) as ServerMessage;
        if (message.type === "joined") {
          pidRef.current = message.pid;
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
        }
      };
      socket.onclose = () => {
        setConnection("closed");
        socketRef.current = null;
      };
      socket.onerror = () => setError("could not reach the game server");
    },
    [],
  );

  const sendPosition = useCallback(
    (fix: { lat: number; lng: number; acc: number; t: number }) =>
      send({ type: "pos", ...fix }),
    [send],
  );

  const leave = useCallback(() => {
    socketRef.current?.close();
    socketRef.current = null;
    setConnection("idle");
    setPid(null);
    setLobby(null);
    setError(null);
    setLastClaim(null);
    setOutOfBounds(null);
    pidRef.current = null;
  }, []);

  useEffect(() => () => socketRef.current?.close(), []);

  return {
    connection,
    pid,
    lobby,
    error,
    lastClaim,
    outOfBounds,
    isHost: lobby !== null && pid !== null && lobby.host === pid,
    createRoom: (name, color) => connect({ type: "create", name, color }),
    joinRoom: (room, name, color) =>
      connect({ type: "join", room: room.toUpperCase(), name, color }),
    setRoundMinutes: (minutes) => send({ type: "config", round_minutes: minutes }),
    setBounds: (bounds) => send({ type: "bounds", ...bounds }),
    sendPosition,
    start: () => send({ type: "start" }),
    leave,
  };
}
