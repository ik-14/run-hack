"""Runner.io game server.

Phase 0 (DESIGN.md §7): players create or join a room over a WebSocket and see each
other in the lobby. Position, trail and territory handling come next.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from app.lobby import LobbyError, Player, Room, RoomRegistry
from app.protocol import (
    PALETTE,
    ROUND_MINUTE_CHOICES,
    Bounds,
    ClientMessage,
    Config,
    Create,
    Join,
    Start,
    parse_client_message,
)

logger = logging.getLogger(__name__)

app = FastAPI(title="Runner.io")
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://.*",
    allow_methods=["*"],
    allow_headers=["*"],
)

rooms = RoomRegistry()


class ConnectionManager:
    """Tracks the live sockets per room so lobby changes can be pushed out."""

    def __init__(self) -> None:
        self._sockets: dict[str, dict[str, WebSocket]] = {}

    def add(self, code: str, pid: str, socket: WebSocket) -> None:
        self._sockets.setdefault(code, {})[pid] = socket

    def remove(self, code: str, pid: str) -> None:
        sockets = self._sockets.get(code)
        if sockets is None:
            return
        sockets.pop(pid, None)
        if not sockets:
            del self._sockets[code]

    async def broadcast(self, code: str, message: dict[str, Any]) -> None:
        for pid, socket in list(self._sockets.get(code, {}).items()):
            try:
                await socket.send_json(message)
            except (RuntimeError, WebSocketDisconnect):
                self.remove(code, pid)


connections = ConnectionManager()


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/config")
async def config() -> dict[str, Any]:
    return {"round_minute_choices": list(ROUND_MINUTE_CHOICES), "palette": list(PALETTE)}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    room: Room | None = None
    player: Player | None = None
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                message = parse_client_message(raw)
            except ValidationError as exc:
                await _send_error(websocket, _first_error(exc))
                continue

            if room is None or player is None:
                room, player = await _handle_entry(websocket, message)
                continue

            await _handle_lobby_message(websocket, room, player, message)
    except WebSocketDisconnect:
        pass
    finally:
        if room is not None and player is not None:
            connections.remove(room.code, player.pid)
            remaining = rooms.leave(room.code, player.pid)
            if remaining is not None:
                await connections.broadcast(remaining.code, remaining.snapshot())


async def _handle_entry(
    websocket: WebSocket, message: ClientMessage
) -> tuple[Room | None, Player | None]:
    if isinstance(message, Create):
        room, player = rooms.create(message.name, message.color)
    elif isinstance(message, Join):
        try:
            room, player = rooms.join(message.room, message.name, message.color)
        except LobbyError as exc:
            await _send_error(websocket, str(exc))
            return None, None
    else:
        await _send_error(websocket, "join a room before sending anything else")
        return None, None

    connections.add(room.code, player.pid, websocket)
    await websocket.send_json(
        {"type": "joined", "pid": player.pid, "room": room.code, "color": player.color}
    )
    await connections.broadcast(room.code, room.snapshot())
    return room, player


async def _handle_lobby_message(
    websocket: WebSocket, room: Room, player: Player, message: ClientMessage
) -> None:
    try:
        if isinstance(message, Config):
            updated = rooms.set_round_minutes(room.code, player.pid, message.round_minutes)
            await connections.broadcast(room.code, updated.snapshot())
        elif isinstance(message, Bounds):
            updated = rooms.set_bounds(room.code, player.pid, message)
            await connections.broadcast(room.code, updated.snapshot())
        elif isinstance(message, Start):
            updated = rooms.start(room.code, player.pid)
            await connections.broadcast(room.code, updated.snapshot())
            await connections.broadcast(
                room.code, {"type": "started", "round_minutes": updated.round_minutes}
            )
        else:
            await _send_error(websocket, "you are already in a room")
    except LobbyError as exc:
        await _send_error(websocket, str(exc))


async def _send_error(websocket: WebSocket, detail: str) -> None:
    await websocket.send_json({"type": "error", "detail": detail})


def _first_error(exc: ValidationError) -> str:
    errors = exc.errors()
    return errors[0]["msg"] if errors else "malformed message"
