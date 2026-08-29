import pytest

from app.lobby import MAX_PLAYERS, LobbyError, RoomRegistry


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


def test_join_after_start_is_rejected():
    registry = RoomRegistry()
    room, host = registry.create("kal")
    registry.start(room.code, host.pid)

    with pytest.raises(LobbyError, match="already started"):
        registry.join(room.code, "late")


def test_only_host_can_start_or_configure():
    registry = RoomRegistry()
    room, _ = registry.create("kal")
    _, guest = registry.join(room.code, "sam")

    with pytest.raises(LobbyError, match="only the host"):
        registry.start(room.code, guest.pid)
    with pytest.raises(LobbyError, match="only the host"):
        registry.set_round_minutes(room.code, guest.pid, 5)


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
