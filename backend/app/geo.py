"""Lat/lng ↔ local metre grid helpers (DESIGN.md §3).

All game maths happens in a local equirectangular metre grid centred on the room, so
areas and distances are ordinary Euclidean numbers.
"""

from __future__ import annotations

import math

from app.protocol import Bounds

EARTH_RADIUS_M = 6_371_000.0


def metres_per_degree(latitude: float) -> tuple[float, float]:
    """Metres per degree of longitude and latitude at the given latitude."""
    per_lat = math.pi * EARTH_RADIUS_M / 180.0
    per_lng = per_lat * math.cos(math.radians(latitude))
    return per_lng, per_lat


def bounds_size_metres(bounds: Bounds) -> tuple[float, float]:
    """Width (east-west) and height (north-south) of the play area in metres."""
    mid_lat = (bounds.south + bounds.north) / 2
    per_lng, per_lat = metres_per_degree(mid_lat)
    return (bounds.east - bounds.west) * per_lng, (bounds.north - bounds.south) * per_lat


def contains(bounds: Bounds, lat: float, lng: float) -> bool:
    return bounds.south <= lat <= bounds.north and bounds.west <= lng <= bounds.east
