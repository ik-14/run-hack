"use client";

import "maplibre-gl/dist/maplibre-gl.css";

import maplibregl, { LngLat, Map as MapLibreMap, StyleSpecification } from "maplibre-gl";
import { useEffect, useRef, useState } from "react";

import { boundsFromCorners, boundsToPolygon } from "@/lib/geo";
import type { Bounds, LobbyPlayer } from "@/lib/protocol";

const OSM_STYLE: StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "© OpenStreetMap contributors",
    },
  },
  layers: [{ id: "osm", type: "raster", source: "osm" }],
};

const EMPTY: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: [] };

function playerFeatures(players: LobbyPlayer[]): GeoJSON.FeatureCollection {
  const features: GeoJSON.Feature[] = [];
  for (const player of players) {
    if (player.trail.length > 1) {
      features.push({
        type: "Feature",
        properties: { color: player.color },
        geometry: {
          type: "LineString",
          coordinates: player.trail.map(([lat, lng]) => [lng, lat]),
        },
      });
    }
    if (player.lat !== null && player.lng !== null) {
      features.push({
        type: "Feature",
        properties: { color: player.color, name: player.name },
        geometry: { type: "Point", coordinates: [player.lng, player.lat] },
      });
    }
  }
  return { type: "FeatureCollection", features };
}

function territoryFeatures(players: LobbyPlayer[]): GeoJSON.FeatureCollection {
  const features: GeoJSON.Feature[] = [];
  for (const player of players) {
    for (const ring of player.territory) {
      features.push({
        type: "Feature",
        properties: { color: player.color },
        geometry: {
          type: "Polygon",
          coordinates: [ring.map(([lat, lng]) => [lng, lat])],
        },
      });
    }
  }
  return { type: "FeatureCollection", features };
}

type Props = {
  bounds: Bounds | null;
  players?: LobbyPlayer[];
  center: { lat: number; lng: number } | null;
  /** When true, dragging on the map rubber-bands the play-area rectangle. */
  drawing?: boolean;
  onDrawn?: (bounds: Bounds) => void;
  className?: string;
};

export function MapView({
  bounds,
  players = [],
  center,
  drawing = false,
  onDrawn,
  className,
}: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const centredRef = useRef(false);
  const fittedRef = useRef<string | null>(null);
  const fittedRunnersRef = useRef<string | null>(null);
  const [ready, setReady] = useState(false);
  const [preview, setPreview] = useState<Bounds | null>(null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: OSM_STYLE,
      center: [center?.lng ?? -0.12, center?.lat ?? 51.5],
      zoom: center ? 15 : 11,
      attributionControl: { compact: true },
    });
    mapRef.current = map;
    map.on("load", () => {
      map.addSource("bounds", { type: "geojson", data: EMPTY });
      map.addLayer({
        id: "bounds-fill",
        type: "fill",
        source: "bounds",
        paint: { "fill-color": "#84cc16", "fill-opacity": 0.12 },
      });
      map.addLayer({
        id: "bounds-line",
        type: "line",
        source: "bounds",
        paint: { "line-color": "#84cc16", "line-width": 3, "line-dasharray": [2, 1] },
      });
      map.addSource("territory", { type: "geojson", data: EMPTY });
      map.addLayer({
        id: "territory-fill",
        type: "fill",
        source: "territory",
        paint: { "fill-color": ["get", "color"], "fill-opacity": 0.45 },
      });
      map.addLayer({
        id: "territory-line",
        type: "line",
        source: "territory",
        paint: { "line-color": ["get", "color"], "line-width": 2 },
      });
      map.addSource("players", { type: "geojson", data: EMPTY });
      map.addLayer({
        id: "trails",
        type: "line",
        source: "players",
        filter: ["==", ["geometry-type"], "LineString"],
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": ["get", "color"], "line-width": 5, "line-opacity": 0.9 },
      });
      map.addLayer({
        id: "runners",
        type: "circle",
        source: "players",
        filter: ["==", ["geometry-type"], "Point"],
        paint: {
          "circle-radius": 7,
          "circle-color": ["get", "color"],
          "circle-stroke-width": 2,
          "circle-stroke-color": "#0a0a0a",
        },
      });
      setReady(true);
    });
    return () => {
      map.remove();
      mapRef.current = null;
    };
    // The map is created once; camera and data updates happen in the effects below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const observer = new ResizeObserver(() => mapRef.current?.resize());
    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  // Snap to the runner once, when the first fix lands; after that the camera is theirs.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !center || centredRef.current) return;
    centredRef.current = true;
    map.jumpTo({ center: [center.lng, center.lat], zoom: Math.max(map.getZoom(), 15) });
  }, [center]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const source = map.getSource("bounds");
    if (!(source instanceof maplibregl.GeoJSONSource)) return;
    const shown = preview ?? bounds;
    source.setData(shown ? boundsToPolygon(shown) : EMPTY);

    const key = bounds ? JSON.stringify(bounds) : null;
    const isNew = key !== fittedRef.current;
    fittedRef.current = key;
    if (!preview && bounds && isNew) {
      map.fitBounds(
        [
          [bounds.west, bounds.south],
          [bounds.east, bounds.north],
        ],
        { padding: 40, duration: 400 },
      );
    }
  }, [bounds, preview, ready]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const source = map.getSource("players");
    if (source instanceof maplibregl.GeoJSONSource) {
      source.setData(playerFeatures(players));
    }
    const claimed = map.getSource("territory");
    if (claimed instanceof maplibregl.GeoJSONSource) {
      claimed.setData(territoryFeatures(players));
    }
  }, [players, ready]);

  // Keep every runner who has a fix on screen: without this the camera sits on your own
  // dot and a friend standing a few streets away is simply off the map.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || drawing || bounds) return;
    const located = players.filter(
      (player): player is LobbyPlayer & { lat: number; lng: number } =>
        player.lat !== null && player.lng !== null,
    );
    if (located.length < 2) return;

    // Only re-frame when the set of located runners changes, so panning isn't fought.
    const key = located
      .map((player) => player.pid)
      .sort()
      .join(",");
    if (key === fittedRunnersRef.current) return;
    fittedRunnersRef.current = key;

    const box = new maplibregl.LngLatBounds();
    for (const player of located) box.extend([player.lng, player.lat]);
    map.fitBounds(box, { padding: 60, maxZoom: 16, duration: 500 });
  }, [players, ready, drawing, bounds]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;

    if (!drawing) {
      map.dragPan.enable();
      return;
    }

    map.dragPan.disable();
    let start: LngLat | null = null;

    const begin = (event: { lngLat: LngLat }) => {
      start = event.lngLat;
      setPreview(boundsFromCorners(event.lngLat, event.lngLat));
    };
    const move = (event: { lngLat: LngLat }) => {
      if (start) setPreview(boundsFromCorners(start, event.lngLat));
    };
    const end = (event: { lngLat: LngLat }) => {
      if (!start) return;
      const drawn = boundsFromCorners(start, event.lngLat);
      start = null;
      setPreview(null);
      if (drawn.north > drawn.south && drawn.east > drawn.west) onDrawn?.(drawn);
    };

    map.on("mousedown", begin);
    map.on("mousemove", move);
    map.on("mouseup", end);
    map.on("touchstart", begin);
    map.on("touchmove", move);
    map.on("touchend", end);
    return () => {
      map.off("mousedown", begin);
      map.off("mousemove", move);
      map.off("mouseup", end);
      map.off("touchstart", begin);
      map.off("touchmove", move);
      map.off("touchend", end);
      map.dragPan.enable();
    };
  }, [drawing, ready, onDrawn]);

  // MapLibre owns the inner div's class attribute; Tailwind classes stay on the wrapper
  // so React re-renders can never strip `maplibregl-map` and break the map's positioning.
  return (
    <div className={className}>
      <div ref={containerRef} className="h-full w-full" />
    </div>
  );
}
