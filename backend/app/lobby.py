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

from shapely.geometry.base import BaseGeometry

from app import territory
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
# How long a runner has to get back inside the play area before they are out (DESIGN.md §7).
OOB_GRACE_S = 30.0

RoomStatus = Literal["lobby", "running"]


class LobbyError(Exception):
    """A client asked for something the lobby cannot do."""


@dataclass
class FixResult:
    """What a GPS fix did: moved the dot, maybe grew the trail, maybe claimed ground."""

    player: Player
    extended: bool = False
    # The player's total territory in m² when this fix closed a loop, else None.
    claimed_m2: float | None = None
    # Seconds left to get back inside, or None while the runner is in bounds.
    grace_left_s: float | None = None
    # True on the fix that disqualifies the runner.
    disqualified: bool = False
    # True on the fix that brings the runner back inside the play area.
    returned: bool = False


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
    # Ground this player owns, in lat/lng degrees.
    land: BaseGeometry | None = None
    # Device clock (ms) when the runner left the play area, else None.
    outside_since: float | None = None
    disqualified: bool = False

    def state(self, latitude: float) -> dict[str, object]:
        return {
            "pid": self.pid,
            "name": self.name,
            "color": self.color,
            "connected": self.connected,
            "lat": self.lat,
            "lng": self.lng,
            "trail": [list(point) for point in self.trail],
            "territory": [[list(point) for point in ring] for ring in territory.rings(self.land)],
            "area_m2": round(territory.area_m2(self.land, latitude), 1),
            "outside": self.outside_since is not None,
            "disqualified": self.disqualified,
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
            "players": [p.state(self.centre_lat) for p in self.players.values()],
        }

    @property
    def centre_lat(self) -> float:
        """Latitude the local metre scale is computed at."""
        return 0.0 if self.bounds is None else (self.bounds.south + self.bounds.north) / 2


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
        if len(room.players) >= MAX_PLAYERS:
            raise LobbyError(f"room {room.code} is full")
        # A latecomer joining a running round starts from scratch — no trail, no land —
        # which is exactly the fresh Player below, so nothing special is needed here.
        player = Player(
            pid=_new_pid(),
            name=self._unique_name(room, name),
            color=_pick_color(room, color),
        )
        room.players[player.pid] = player
        return room, player

    def leave(self, code: str, pid: str) -> Room | None:
        """Remove a player for good, returning the room or None if it is now empty."""
        room = self.get(code)
        room.players.pop(pid, None)
        return self._settle(room, pid)

    def disconnect(self, code: str, pid: str) -> Room | None:
        """Park a player whose socket dropped so they can rejoin with the same pid.

        Phones drop the socket constantly (screen lock, backgrounded tab, wifi to 5G), and
        deleting the runner would throw away their trail and territory mid-round.
        """
        room = self.get(code)
        player = room.players.get(pid)
        if player is not None:
            player.connected = False
        return self._settle(room, pid)

    def rejoin(self, code: str, pid: str) -> tuple[Room, Player]:
        room = self.get(code)
        player = room.players.get(pid)
        if player is None:
            raise LobbyError("you are no longer in that room")
        player.connected = True
        return room, player

    def _settle(self, room: Room, gone_pid: str) -> Room | None:
        """Drop the room once nobody is left on it, else keep the host reachable."""
        if not any(player.connected for player in room.players.values()):
            del self._rooms[room.code]
            return None
        if room.host_pid == gone_pid:
            room.host_pid = next(p.pid for p in room.players.values() if p.connected)
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
            player.land = None
            player.outside_since = None
            player.disqualified = False
        return room

    def record_position(self, code: str, pid: str, pos: Pos) -> FixResult:
        """Store a fix, extending the trail and claiming ground when a loop closes."""
        room = self.get(code)
        player = room.players.get(pid)
        if player is None:
            raise LobbyError("you are not in that room")
        result = FixResult(player=player)

        if player.lat is not None and player.lng is not None and player.seen_at is not None:
            moved = distance_metres(player.lat, player.lng, pos.lat, pos.lng)
            elapsed = max((pos.t - player.seen_at) / 1000.0, MIN_FIX_GAP_S)
            if moved / elapsed > MAX_SPEED_MPS:
                return result

        player.lat, player.lng, player.seen_at = pos.lat, pos.lng, pos.t
        if room.status != "running" or player.disqualified:
            return result

        self._check_bounds(room, player, pos, result)
        if player.disqualified or player.outside_since is not None:
            return result

        tail = player.trail[-1] if player.trail else None
        if (
            tail is not None
            and distance_metres(tail[0], tail[1], pos.lat, pos.lng) < MIN_TRAIL_STEP_M
        ):
            return result

        player.trail.append((pos.lat, pos.lng))
        result.extended = True
        result.claimed_m2 = self._try_claim(room, player)
        return result

    def _check_bounds(self, room: Room, player: Player, pos: Pos, result: FixResult) -> None:
        """Start, clear or expire the out-of-bounds countdown for this fix."""
        bounds = room.bounds
        if bounds is None:
            return
        inside = bounds.south <= pos.lat <= bounds.north and bounds.west <= pos.lng <= bounds.east
        if inside:
            result.returned = player.outside_since is not None
            player.outside_since = None
            return

        if player.outside_since is None:
            player.outside_since = pos.t
        away_s = (pos.t - player.outside_since) / 1000.0
        if away_s >= OOB_GRACE_S:
            player.disqualified = True
            player.outside_since = None
            result.disqualified = True
            result.grace_left_s = 0.0
            return
        result.grace_left_s = round(OOB_GRACE_S - away_s, 1)

    def _try_claim(self, room: Room, player: Player) -> float | None:
        """Close the streak into territory, taking any overlap off the other players."""
        closed = territory.find_loop(player.trail)
        if closed is None:
            return None
        ring, leftover = closed
        claim = territory.ring_to_polygon(ring)
        if claim is None:
            return None

        gained = territory.area_m2(claim, room.centre_lat)
        if gained < territory.MIN_CLAIM_M2:
            return None

        player.trail = leftover
        player.land = territory.add(player.land, claim)
        for rival in room.players.values():
            if rival.pid != player.pid:
                rival.land = territory.take_from(rival.land, claim)
        return round(territory.area_m2(player.land, room.centre_lat), 1)

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
