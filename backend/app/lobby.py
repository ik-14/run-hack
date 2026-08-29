"""In-memory room registry.

Rooms live only in this process (DESIGN.md §3) — a room disappears once the last
player leaves.
"""

from __future__ import annotations

import random
import string
import uuid
from dataclasses import dataclass, field
from typing import Literal

from app.protocol import ROUND_MINUTE_CHOICES

ROOM_CODE_LENGTH = 4
ROOM_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ"
MAX_PLAYERS = 8
DEFAULT_ROUND_MINUTES = 10

RoomStatus = Literal["lobby", "running"]


class LobbyError(Exception):
    """A client asked for something the lobby cannot do."""


@dataclass
class Player:
    pid: str
    name: str
    connected: bool = True


@dataclass
class Room:
    code: str
    host_pid: str
    round_minutes: int = DEFAULT_ROUND_MINUTES
    status: RoomStatus = "lobby"
    players: dict[str, Player] = field(default_factory=dict[str, Player])

    def snapshot(self) -> dict[str, object]:
        return {
            "type": "lobby",
            "room": self.code,
            "status": self.status,
            "host": self.host_pid,
            "round_minutes": self.round_minutes,
            "players": [
                {"pid": p.pid, "name": p.name, "connected": p.connected}
                for p in self.players.values()
            ],
        }


class RoomRegistry:
    def __init__(self, rng: random.Random | None = None) -> None:
        self._rooms: dict[str, Room] = {}
        self._rng = rng or random.Random()

    def clear(self) -> None:
        self._rooms.clear()

    def get(self, code: str) -> Room:
        room = self._rooms.get(code.upper())
        if room is None:
            raise LobbyError(f"no room called {code.upper()}")
        return room

    def create(self, name: str) -> tuple[Room, Player]:
        code = self._new_code()
        host = Player(pid=_new_pid(), name=name)
        room = Room(code=code, host_pid=host.pid, players={host.pid: host})
        self._rooms[code] = room
        return room, host

    def join(self, code: str, name: str) -> tuple[Room, Player]:
        room = self.get(code)
        if room.status != "lobby":
            raise LobbyError("that round has already started")
        if len(room.players) >= MAX_PLAYERS:
            raise LobbyError(f"room {room.code} is full")
        player = Player(pid=_new_pid(), name=self._unique_name(room, name))
        room.players[player.pid] = player
        return room, player

    def leave(self, code: str, pid: str) -> Room | None:
        """Remove a player, returning the room or None if it is now empty."""
        room = self.get(code)
        room.players.pop(pid, None)
        if not room.players:
            del self._rooms[room.code]
            return None
        if room.host_pid == pid:
            room.host_pid = next(iter(room.players))
        return room

    def set_round_minutes(self, code: str, pid: str, minutes: int) -> Room:
        room = self._host_room(code, pid)
        if minutes not in ROUND_MINUTE_CHOICES:
            raise LobbyError(f"round length must be one of {list(ROUND_MINUTE_CHOICES)}")
        room.round_minutes = minutes
        return room

    def start(self, code: str, pid: str) -> Room:
        room = self._host_room(code, pid)
        if room.status != "lobby":
            raise LobbyError("the round is already running")
        room.status = "running"
        return room

    def _host_room(self, code: str, pid: str) -> Room:
        room = self.get(code)
        if room.host_pid != pid:
            raise LobbyError("only the host can do that")
        return room

    def _new_code(self) -> str:
        while True:
            code = "".join(self._rng.choices(ROOM_CODE_ALPHABET, k=ROOM_CODE_LENGTH))
            if code not in self._rooms:
                return code

    def _unique_name(self, room: Room, name: str) -> str:
        taken = {p.name for p in room.players.values()}
        if name not in taken:
            return name
        for suffix in string.digits[2:]:
            candidate = f"{name} {suffix}"
            if candidate not in taken:
                return candidate
        return f"{name} {uuid.uuid4().hex[:2]}"


def _new_pid() -> str:
    return uuid.uuid4().hex[:8]
