"""Turning running trails into claimed ground (DESIGN.md §2).

Geometry is done with shapely in raw lat/lng degrees: over a play area of a few hundred
metres the distortion is negligible, and areas are converted to square metres with the
local metres-per-degree scale.
"""

from __future__ import annotations

from shapely.geometry import LineString, MultiPolygon, Point, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from app.geo import distance_metres, metres_per_degree

# A runner who gets back within this of their own start has closed the loop.
CLOSE_LOOP_M = 15.0
# Ignore slivers: a claim has to be worth at least this much ground.
MIN_CLAIM_M2 = 100.0

LatLng = tuple[float, float]


def _xy(point: LatLng) -> tuple[float, float]:
    """Shapely works in x/y, i.e. lng/lat."""
    return point[1], point[0]


def find_loop(trail: list[LatLng]) -> tuple[list[LatLng], list[LatLng]] | None:
    """Split a trail into (closed ring, trail left over) once it closes on itself.

    A loop closes either by the newest segment crossing an earlier one, or by the runner
    arriving back where the streak started.
    """
    if len(trail) < 4:
        return None

    last = LineString([_xy(trail[-2]), _xy(trail[-1])])
    # Skip the segment adjoining the last one: it always touches at the shared vertex.
    for index in range(len(trail) - 3):
        earlier = LineString([_xy(trail[index]), _xy(trail[index + 1])])
        crossing = last.intersection(earlier)
        if crossing.is_empty:
            continue
        point = crossing.centroid if not isinstance(crossing, Point) else crossing
        cut: LatLng = (point.y, point.x)
        return [cut, *trail[index + 1 : -1], cut], [cut, trail[-1]]

    head, tail = trail[0], trail[-1]
    if distance_metres(head[0], head[1], tail[0], tail[1]) <= CLOSE_LOOP_M:
        return [*trail, head], [tail]

    return None


def ring_to_polygon(ring: list[LatLng]) -> Polygon | None:
    """Build a valid polygon from a ring, or None if it encloses nothing."""
    if len(ring) < 4:
        return None
    raw = Polygon([_xy(point) for point in ring])
    # A figure-of-eight trail makes a bow-tie polygon; buffer(0) splits it into valid parts.
    fixed: BaseGeometry = raw if raw.is_valid else raw.buffer(0)
    if fixed.is_empty:
        return None
    if isinstance(fixed, MultiPolygon):
        return max(fixed.geoms, key=lambda part: part.area)
    return fixed


def add(existing: BaseGeometry | None, claim: BaseGeometry) -> BaseGeometry:
    return claim if existing is None else unary_union([existing, claim])


def take_from(existing: BaseGeometry | None, claim: BaseGeometry) -> BaseGeometry | None:
    """Remove the newly claimed ground from a rival's territory."""
    if existing is None:
        return None
    remaining = existing.difference(claim)
    return None if remaining.is_empty else remaining


def area_m2(geometry: BaseGeometry | None, latitude: float) -> float:
    if geometry is None or geometry.is_empty:
        return 0.0
    per_lng, per_lat = metres_per_degree(latitude)
    return geometry.area * per_lng * per_lat


def rings(geometry: BaseGeometry | None) -> list[list[LatLng]]:
    """Exterior rings as [lat, lng] lists, ready for the client to draw."""
    if geometry is None or geometry.is_empty:
        return []
    parts = geometry.geoms if isinstance(geometry, MultiPolygon) else [geometry]
    out: list[list[LatLng]] = []
    for part in parts:
        if isinstance(part, Polygon):
            out.append([(y, x) for x, y in part.exterior.coords])
    return out
