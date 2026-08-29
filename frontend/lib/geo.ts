import type { Bounds } from "@/lib/protocol";

const EARTH_RADIUS_M = 6_371_000;

/** Metres per degree of longitude and of latitude at a given latitude. */
export function metresPerDegree(latitude: number): [number, number] {
  const perLat = (Math.PI * EARTH_RADIUS_M) / 180;
  return [perLat * Math.cos((latitude * Math.PI) / 180), perLat];
}

export function boundsSizeMetres(bounds: Bounds): [number, number] {
  const [perLng, perLat] = metresPerDegree((bounds.south + bounds.north) / 2);
  return [
    (bounds.east - bounds.west) * perLng,
    (bounds.north - bounds.south) * perLat,
  ];
}

export function boundsToPolygon(bounds: Bounds): GeoJSON.Feature<GeoJSON.Polygon> {
  const { south, west, north, east } = bounds;
  return {
    type: "Feature",
    properties: {},
    geometry: {
      type: "Polygon",
      coordinates: [
        [
          [west, south],
          [east, south],
          [east, north],
          [west, north],
          [west, south],
        ],
      ],
    },
  };
}

export function boundsFromCorners(
  a: { lng: number; lat: number },
  b: { lng: number; lat: number },
): Bounds {
  return {
    south: Math.min(a.lat, b.lat),
    north: Math.max(a.lat, b.lat),
    west: Math.min(a.lng, b.lng),
    east: Math.max(a.lng, b.lng),
  };
}
