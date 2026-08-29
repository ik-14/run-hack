import pytest

from app.lobby import MAX_PLAYERS, LobbyError, RoomRegistry
from app.protocol import PALETTE, Bounds, Pos


def a_rectangle(side_deg: float = 0.005) -> Bounds:
    return Bounds(
        type="bounds",
        south=51.5,
        west=-0.12,
        north=51.5 + side_deg,
        east=-0.12 + side_deg,
    )


def test_create_makes_host_the_only_player():
    registry = RoomRegistry()
    room, host = registry.create("kal")

    assert room.host_pid == host.pid
    assert room.status == "lobby"
    assert list(room.players) == [host.pid]
    assert len(room.code) == 4


def test_join_is_case_insensitive_and_dedupes_names():
    registry = RoomRegistry()
    room, _ = registry.create("kal")

    _, second = registry.join(room.code.lower(), "kal")

    assert second.name == "kal 2"
    assert len(room.players) == 2


def test_requested_colour_is_honoured_once():
    registry = RoomRegistry()
    room, host = registry.create("kal", PALETTE[3])
    _, guest = registry.join(room.code, "sam", PALETTE[3])

    assert host.color == PALETTE[3]
    assert guest.color != PALETTE[3]
    assert guest.color in PALETTE


def test_colours_are_unique_without_a_preference():
    registry = RoomRegistry()
    room, host = registry.create("host")
    colors = {host.color}
    for i in range(MAX_PLAYERS - 1):
        _, player = registry.join(room.code, f"p{i}")
        colors.add(player.color)

    assert len(colors) == MAX_PLAYERS


def test_join_unknown_room():
    registry = RoomRegistry()
    with pytest.raises(LobbyError):
        registry.join("ZZZZ", "kal")


def test_join_full_room():
    registry = RoomRegistry()
    room, _ = registry.create("host")
    for i in range(MAX_PLAYERS - 1):
        registry.join(room.code, f"p{i}")

    with pytest.raises(LobbyError, match="full"):
        registry.join(room.code, "late")


def test_start_needs_a_play_area():
    registry = RoomRegistry()
    room, host = registry.create("kal")

    with pytest.raises(LobbyError, match="draw the play area"):
        registry.start(room.code, host.pid)


def test_play_area_must_be_a_sensible_size():
    registry = RoomRegistry()
    room, host = registry.create("kal")

    with pytest.raises(LobbyError, match="at least"):
        registry.set_bounds(room.code, host.pid, a_rectangle(0.0001))
    with pytest.raises(LobbyError, match="under"):
        registry.set_bounds(room.code, host.pid, a_rectangle(0.1))

    updated = registry.set_bounds(room.code, host.pid, a_rectangle())
    assert updated.bounds is not None


def test_join_mid_round_is_allowed_and_starts_fresh():
    registry = RoomRegistry()
    room, host = registry.create("kal")
    registry.set_bounds(room.code, host.pid, a_rectangle())
    registry.start(room.code, host.pid)

    room, latecomer = registry.join(room.code, "late")

    assert room.status == "running"
    assert latecomer.pid in room.players
    assert latecomer.trail == []
    assert latecomer.land is None
    assert not latecomer.disqualified


def test_only_host_can_start_or_configure():
    registry = RoomRegistry()
    room, _ = registry.create("kal")
    _, guest = registry.join(room.code, "sam")

    with pytest.raises(LobbyError, match="only the host"):
        registry.start(room.code, guest.pid)
    with pytest.raises(LobbyError, match="only the host"):
        registry.set_round_minutes(room.code, guest.pid, 5)
    with pytest.raises(LobbyError, match="only the host"):
        registry.set_bounds(room.code, guest.pid, a_rectangle())


def a_fix(lat: float, lng: float, seconds: float = 0.0) -> Pos:
    return Pos(type="pos", lat=lat, lng=lng, acc=5.0, t=seconds * 1000)


def test_trail_only_grows_once_the_round_is_running():
    registry = RoomRegistry()
    room, host = registry.create("kal")
    registry.set_bounds(room.code, host.pid, a_rectangle())

    assert registry.record_position(room.code, host.pid, a_fix(51.501, -0.119)).extended is False
    assert host.trail == []
    assert host.lat == 51.501

    registry.start(room.code, host.pid)
    assert registry.record_position(room.code, host.pid, a_fix(51.501, -0.119)).extended is True
    assert len(host.trail) == 1


def test_jitter_does_not_add_vertices_but_real_steps_do():
    registry = RoomRegistry()
    room, host = registry.create("kal")
    registry.set_bounds(room.code, host.pid, a_rectangle())
    registry.start(room.code, host.pid)

    registry.record_position(room.code, host.pid, a_fix(51.501, -0.119, 0))
    # ~1 m away: jitter.
    registry.record_position(room.code, host.pid, a_fix(51.501009, -0.119, 5))
    assert len(host.trail) == 1

    # ~22 m away: a real step.
    registry.record_position(room.code, host.pid, a_fix(51.5012, -0.119, 10))
    assert len(host.trail) == 2


def test_teleporting_fixes_are_ignored():
    registry = RoomRegistry()
    room, host = registry.create("kal")
    registry.set_bounds(room.code, host.pid, a_rectangle())
    registry.start(room.code, host.pid)

    registry.record_position(room.code, host.pid, a_fix(51.501, -0.119, 0))
    fix = registry.record_position(room.code, host.pid, a_fix(51.9, -0.119, 5))

    assert fix.extended is False
    assert len(host.trail) == 1
    assert host.lat == 51.501


def test_round_length_must_be_a_choice():
    registry = RoomRegistry()
    room, host = registry.create("kal")

    assert registry.set_round_minutes(room.code, host.pid, 20).round_minutes == 20
    with pytest.raises(LobbyError):
        registry.set_round_minutes(room.code, host.pid, 7)


def test_host_leaving_promotes_someone_else():
    registry = RoomRegistry()
    room, host = registry.create("kal")
    _, guest = registry.join(room.code, "sam")

    remaining = registry.leave(room.code, host.pid)

    assert remaining is not None
    assert remaining.host_pid == guest.pid


def test_empty_room_is_dropped():
    registry = RoomRegistry()
    room, host = registry.create("kal")

    assert registry.leave(room.code, host.pid) is None
    with pytest.raises(LobbyError):
        registry.get(room.code)
