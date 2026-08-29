"use client";

import { useEffect, useState } from "react";

export type Fix = {
  lat: number;
  lng: number;
  acc: number;
  t: number;
};

export type Geolocation = {
  fix: Fix | null;
  error: string | null;
};

/** Follows the device position for as long as the component is mounted. */
export function useGeolocation(enabled = true): Geolocation {
  const [fix, setFix] = useState<Fix | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled) return;
    if (typeof navigator === "undefined" || !navigator.geolocation) {
      setError("this browser has no GPS");
      return;
    }
    const id = navigator.geolocation.watchPosition(
      (position) => {
        setError(null);
        setFix({
          lat: position.coords.latitude,
          lng: position.coords.longitude,
          acc: position.coords.accuracy,
          t: position.timestamp,
        });
      },
      (positionError) => setError(positionError.message),
      { enableHighAccuracy: true, maximumAge: 1000, timeout: 15000 },
    );
    return () => navigator.geolocation.clearWatch(id);
  }, [enabled]);

  return { fix, error };
}
