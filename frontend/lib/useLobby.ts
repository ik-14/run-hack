"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  ClientMessage,
  LobbyState,
  ServerMessage,
  serverUrl,
} from "@/lib/protocol";

export type Connection = "idle" | "connecting" | "open" | "closed";

export type Lobby = {
  connection: Connection;
  pid: string | null;
  lobby: LobbyState | null;
  error: string | null;
  isHost: boolean;
  createRoom: (name: string, color: string) => void;
  joinRoom: (room: string, name: string, color: string) => void;
  setRoundMinutes: (minutes: number) => void;
  start: () => void;
  leave: () => void;
};

export function useLobby(): Lobby {
  const socketRef = useRef<WebSocket | null>(null);
  const queuedRef = useRef<ClientMessage | null>(null);
  const [connection, setConnection] = useState<Connection>("idle");
  const [pid, setPid] = useState<string | null>(null);
  const [lobby, setLobby] = useState<LobbyState | null>(null);
  const [error, setError] = useState<string | null>(null);

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
          setPid(message.pid);
        } else if (message.type === "lobby") {
          setLobby(message);
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

  const leave = useCallback(() => {
    socketRef.current?.close();
    socketRef.current = null;
    setConnection("idle");
    setPid(null);
    setLobby(null);
    setError(null);
  }, []);

  useEffect(() => () => socketRef.current?.close(), []);

  return {
    connection,
    pid,
    lobby,
    error,
    isHost: lobby !== null && pid !== null && lobby.host === pid,
    createRoom: (name, color) => connect({ type: "create", name, color }),
    joinRoom: (room, name, color) =>
      connect({ type: "join", room: room.toUpperCase(), name, color }),
    setRoundMinutes: (minutes) => send({ type: "config", round_minutes: minutes }),
    start: () => send({ type: "start" }),
    leave,
  };
}
