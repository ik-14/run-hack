from app.lobby import OOB_GRACE_S, RoomRegistry
from app.protocol import Bounds, Pos

AREA = Bounds(type="bounds", south=51.499, west=-0.121, north=51.503, east=-0.117)
INSIDE = (51.5010, -0.1190)
OUTSIDE = (51.5060, -0.1190)


def a_room() -> tuple[RoomRegistry, str, str]:
    registry = RoomRegistry()
    room, host = registry.create("kal")
    registry.set_bounds(room.code, host.pid, AREA)
    registry.start(room.code, host.pid)
    return registry, room.code, host.pid


def fix(registry: RoomRegistry, code: str, pid: str, point: tuple[float, float], seconds: float):
    lat, lng = point
    return registry.record_position(code, pid, Pos(type="pos", lat=lat, lng=lng, t=seconds * 1000))


def test_staying_inside_never_starts_the_countdown():
    registry, code, pid = a_room()
    assert fix(registry, code, pid, INSIDE, 0).grace_left_s is None


def test_leaving_the_area_starts_the_countdown():
    registry, code, pid = a_room()
    fix(registry, code, pid, INSIDE, 0)
    # Far enough out to trip the boundary, slow enough to pass the speed check.
    warned = fix(registry, code, pid, OUTSIDE, 120)

    assert warned.grace_left_s == OOB_GRACE_S
    assert warned.disqualified is False


def test_coming_back_inside_clears_the_countdown():
    registry, code, pid = a_room()
    fix(registry, code, pid, INSIDE, 0)
    fix(registry, code, pid, OUTSIDE, 120)
    back = fix(registry, code, pid, INSIDE, 140)

    assert back.grace_left_s is None
    assert back.player.disqualified is False


def test_staying_out_past_the_grace_period_disqualifies():
    registry, code, pid = a_room()
    fix(registry, code, pid, INSIDE, 0)
    fix(registry, code, pid, OUTSIDE, 120)
    out = fix(registry, code, pid, OUTSIDE, 120 + OOB_GRACE_S)

    assert out.disqualified is True
    assert out.player.disqualified is True


def test_a_disqualified_runner_stops_drawing_trail():
    registry, code, pid = a_room()
    fix(registry, code, pid, INSIDE, 0)
    fix(registry, code, pid, OUTSIDE, 120)
    fix(registry, code, pid, OUTSIDE, 120 + OOB_GRACE_S)
    length = len(registry.get(code).players[pid].trail)

    fix(registry, code, pid, INSIDE, 200)
    assert len(registry.get(code).players[pid].trail) == length


def test_the_trail_does_not_grow_while_out_of_bounds():
    registry, code, pid = a_room()
    fix(registry, code, pid, INSIDE, 0)
    length = len(registry.get(code).players[pid].trail)
    fix(registry, code, pid, OUTSIDE, 120)

    assert len(registry.get(code).players[pid].trail) == length
