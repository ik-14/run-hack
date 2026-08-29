from app.lobby import RoomRegistry
from app.protocol import Bounds, Pos
from app.territory import area_m2, find_loop, ring_to_polygon

# A ~35 m x ~55 m lap (~1900 m²) starting and ending at the same corner.
SIDE_DEG = 0.0005
LAP: list[tuple[float, float]] = [
    (51.5000, -0.1200),
    (51.5000, -0.1200 + SIDE_DEG),
    (51.5000 + SIDE_DEG, -0.1200 + SIDE_DEG),
    (51.5000 + SIDE_DEG, -0.1200),
]


def a_rectangle() -> Bounds:
    return Bounds(type="bounds", south=51.499, west=-0.121, north=51.503, east=-0.117)


def test_open_trail_is_not_a_loop():
    assert find_loop(LAP[:3]) is None


def test_returning_to_the_start_closes_the_loop():
    closed = find_loop([*LAP, (51.50001, -0.12001)])
    assert closed is not None
    ring, leftover = closed
    assert ring[0] == ring[-1]
    assert len(leftover) == 1

    polygon = ring_to_polygon(ring)
    assert polygon is not None
    assert 1500 < area_m2(polygon, 51.5) < 2500


def test_crossing_an_earlier_segment_closes_the_loop():
    # Run the lap, then cut back across the first side.
    trail = [*LAP, (51.4999, -0.1200 + SIDE_DEG / 2)]
    closed = find_loop(trail)
    assert closed is not None
    ring, leftover = closed
    assert ring[0] == ring[-1]
    assert leftover[-1] == trail[-1]


def run_lap(registry: RoomRegistry, code: str, pid: str, points: list[tuple[float, float]]) -> None:
    for index, (lat, lng) in enumerate(points):
        registry.record_position(code, pid, Pos(type="pos", lat=lat, lng=lng, t=index * 10_000))


def test_closing_a_lap_claims_ground_and_resets_the_trail():
    registry = RoomRegistry()
    room, host = registry.create("kal")
    registry.set_bounds(room.code, host.pid, a_rectangle())
    registry.start(room.code, host.pid)

    run_lap(registry, room.code, host.pid, [*LAP, LAP[0]])

    assert host.land is not None
    assert 1500 < area_m2(host.land, room.centre_lat) < 2500
    assert len(host.trail) <= 2


def test_a_rival_lap_takes_the_overlap_away():
    registry = RoomRegistry()
    room, host = registry.create("kal")
    _, rival = registry.join(room.code, "sam")
    registry.set_bounds(room.code, host.pid, a_rectangle())
    registry.start(room.code, host.pid)

    run_lap(registry, room.code, host.pid, [*LAP, LAP[0]])
    claimed = area_m2(host.land, room.centre_lat)

    # The rival runs the same lap shifted half a side east, so it bites into the host.
    shifted = [(lat, lng + SIDE_DEG / 2) for lat, lng in LAP]
    run_lap(registry, room.code, rival.pid, [*shifted, shifted[0]])

    assert rival.land is not None
    assert area_m2(host.land, room.centre_lat) < claimed
