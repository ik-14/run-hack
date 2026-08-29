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

from app.geo import bounds_size_metres, distance_metres
from app.protocol import PALETTE, ROUND_MINUTE_CHOICES, Bounds, Pos

ROOM_CODE_LENGTH = 4
ROOM_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ"
MAX_PLAYERS = len(PALETTE)
DEFAULT_ROUND_MINUTES = 10
MIN_PLAY_AREA_SIDE_M = 50.0
MAX_PLAY_AREA_SIDE_M = 5000.0
# A fix has to move this far before it earns a new trail vertex, which keeps GPS jitter
# from turning a standing runner into a scribble.
MIN_TRAIL_STEP_M = 5.0
# Faster than a sprinter: treat anything above this as a GPS glitch (DESIGN.md §6).
MAX_SPEED_MPS = 12.0
# Phones can report fixes back to back, so the speed check assumes at least this gap.
MIN_FIX_GAP_S = 2.0

RoomStatus = Literal["lobby", "running"]


class LobbyError(Exception):
    """A client asked for something the lobby cannot do."""


@dataclass
class Player:
    pid: str
    name: str
    color: str
    connected: bool = True
    lat: float | None = None
    lng: float | None = None
    # Device clock (ms) of the last accepted fix, used for the speed sanity check.
    seen_at: float | None = None
    # The live streak, as [lat, lng] vertices, since the round started.
    trail: list[tuple[float, float]] = field(default_factory=list[tuple[float, float]])

    def state(self) -> dict[str, object]:
        return {
            "pid": self.pid,
            "name": self.name,
            "color": self.color,
            "connected": self.connected,
            "lat": self.lat,
            "lng": self.lng,
            "trail": [list(point) for point in self.trail],
        }


@dataclass
class Room:
    code: str
    host_pid: str
    round_minutes: int = DEFAULT_ROUND_MINUTES
    status: RoomStatus = "lobby"
    bounds: Bounds | None = None
    players: dict[str, Player] = field(default_factory=dict[str, Player])

    def snapshot(self) -> dict[str, object]:
        return {
            "type": "lobby",
            "room": self.code,
            "status": self.status,
            "host": self.host_pid,
            "round_minutes": self.round_minutes,
            "bounds": None if self.bounds is None else self.bounds.model_dump(exclude={"type"}),
            "players": [p.state() for p in self.players.values()],
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

    def create(self, name: str, color: str | None = None) -> tuple[Room, Player]:
        code = self._new_code()
        room = Room(code=code, host_pid="")
        host = Player(pid=_new_pid(), name=name, color=_pick_color(room, color))
        room.host_pid = host.pid
        room.players[host.pid] = host
        self._rooms[code] = room
        return room, host

    def join(self, code: str, name: str, color: str | None = None) -> tuple[Room, Player]:
        room = self.get(code)
        if room.status != "lobby":
            raise LobbyError("that round has already started")
        if len(room.players) >= MAX_PLAYERS:
            raise LobbyError(f"room {room.code} is full")
        player = Player(
            pid=_new_pid(),
            name=self._unique_name(room, name),
            color=_pick_color(room, color),
        )
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

    def set_bounds(self, code: str, pid: str, bounds: Bounds) -> Room:
        room = self._host_room(code, pid)
        width_m, height_m = bounds_size_metres(bounds)
        smallest, largest = min(width_m, height_m), max(width_m, height_m)
        if smallest < MIN_PLAY_AREA_SIDE_M:
            raise LobbyError(f"the play area must be at least {MIN_PLAY_AREA_SIDE_M:.0f} m across")
        if largest > MAX_PLAY_AREA_SIDE_M:
            raise LobbyError(
                f"the play area must be under {MAX_PLAY_AREA_SIDE_M / 1000:.0f} km across"
            )
        room.bounds = bounds
        return room

    def start(self, code: str, pid: str) -> Room:
        room = self._host_room(code, pid)
        if room.status != "lobby":
            raise LobbyError("the round is already running")
        if room.bounds is None:
            raise LobbyError("draw the play area on the map first")
        room.status = "running"
        for player in room.players.values():
            player.trail.clear()
        return room

    def record_position(self, code: str, pid: str, pos: Pos) -> tuple[Player, bool]:
        """Store a fix, returning the player and whether the trail grew a vertex."""
        room = self.get(code)
        player = room.players.get(pid)
        if player is None:
            raise LobbyError("you are not in that room")

        if player.lat is not None and player.lng is not None and player.seen_at is not None:
            moved = distance_metres(player.lat, player.lng, pos.lat, pos.lng)
            elapsed = max((pos.t - player.seen_at) / 1000.0, MIN_FIX_GAP_S)
            if moved / elapsed > MAX_SPEED_MPS:
                return player, False

        player.lat, player.lng, player.seen_at = pos.lat, pos.lng, pos.t
        if room.status != "running":
            return player, False

        tail = player.trail[-1] if player.trail else None
        if tail is None or distance_metres(tail[0], tail[1], pos.lat, pos.lng) >= MIN_TRAIL_STEP_M:
            player.trail.append((pos.lat, pos.lng))
            return player, True
        return player, False

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


def _pick_color(room: Room, requested: str | None) -> str:
    """Honour the requested swatch when it is still free, else hand out the next one."""
    taken = {p.color for p in room.players.values()}
    if requested is not None and requested not in taken:
        return requested
    for color in PALETTE:
        if color not in taken:
            return color
    raise LobbyError(f"room {room.code} is full")
