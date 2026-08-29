"use client";

import "maplibre-gl/dist/maplibre-gl.css";

import maplibregl, { LngLat, Map as MapLibreMap, StyleSpecification } from "maplibre-gl";
import { useEffect, useRef, useState } from "react";

import { boundsFromCorners, boundsToPolygon } from "@/lib/geo";
import type { Bounds } from "@/lib/protocol";

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

type Props = {
  bounds: Bounds | null;
  center: { lat: number; lng: number } | null;
  /** When true, dragging on the map rubber-bands the play-area rectangle. */
  drawing?: boolean;
  onDrawn?: (bounds: Bounds) => void;
  className?: string;
};

export function MapView({ bounds, center, drawing = false, onDrawn, className }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const centredRef = useRef(false);
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
      setReady(true);
    });
    return () => {
      map.remove();
      mapRef.current = null;
    };
    // The map is created once; camera and data updates happen in the effects below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
    if (!preview && bounds) {
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

  return <div ref={containerRef} className={className} />;
}
