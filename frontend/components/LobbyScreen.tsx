"use client";

import { useCallback, useState } from "react";

import { MapView } from "@/components/MapView";
import { boundsSizeMetres } from "@/lib/geo";
import { Bounds, LobbyState, ROUND_MINUTE_CHOICES } from "@/lib/protocol";
import type { Fix } from "@/lib/useGeolocation";

type Props = {
  lobby: LobbyState;
  pid: string | null;
  isHost: boolean;
  fix: Fix | null;
  gpsError: string | null;
  onRoundMinutes: (minutes: number) => void;
  onBounds: (bounds: Bounds) => void;
  onStart: () => void;
  onLeave: () => void;
};

export function LobbyScreen({
  lobby,
  pid,
  isHost,
  fix,
  gpsError,
  onRoundMinutes,
  onBounds,
  onStart,
  onLeave,
}: Props) {
  const [drawing, setDrawing] = useState(false);

  const handleDrawn = useCallback(
    (bounds: Bounds) => {
      setDrawing(false);
      onBounds(bounds);
    },
    [onBounds],
  );

  const size = lobby.bounds ? boundsSizeMetres(lobby.bounds) : null;

  return (
    <div className="flex flex-col gap-5">
      <header className="space-y-1">
        <button
          onClick={onLeave}
          className="text-xs uppercase tracking-widest text-white/50"
        >
          ← Leave
        </button>
        <p className="text-xs uppercase tracking-widest text-white/50">Room code</p>
        <p className="font-mono text-5xl font-black tracking-[0.3em] text-lime-400">
          {lobby.room}
        </p>
      </header>

      <section className="space-y-2">
        <div className="flex items-baseline justify-between">
          <h2 className="text-xs uppercase tracking-widest text-white/50">
            Play area
          </h2>
          {size && (
            <span className="text-xs text-white/50">
              {size[0].toFixed(0)} × {size[1].toFixed(0)} m
            </span>
          )}
        </div>
        <MapView
          bounds={lobby.bounds}
          center={fix}
          drawing={drawing}
          onDrawn={handleDrawn}
          className="h-64 w-full overflow-hidden rounded-xl"
        />
        {isHost ? (
          <button
            onClick={() => setDrawing((on) => !on)}
            className={`w-full rounded-xl px-4 py-3 text-sm font-bold ${
              drawing ? "bg-lime-400 text-black" : "border border-white/25"
            }`}
          >
            {drawing
              ? "Drag on the map to draw the boundary"
              : lobby.bounds
                ? "Redraw play area"
                : "Draw play area"}
          </button>
        ) : (
          <p className="text-xs text-white/50">
            {lobby.bounds
              ? "The host has set the play area."
              : "Waiting for the host to draw the play area…"}
          </p>
        )}
        {gpsError && (
          <p className="text-xs text-amber-300">GPS: {gpsError}</p>
        )}
      </section>

      <section className="space-y-2">
        <h2 className="text-xs uppercase tracking-widest text-white/50">
          Players ({lobby.players.length})
        </h2>
        <ul className="divide-y divide-white/10 overflow-hidden rounded-xl bg-white/5">
          {lobby.players.map((player) => (
            <li
              key={player.pid}
              className="flex items-center justify-between px-4 py-3"
            >
              <span className="flex items-center gap-3 text-lg">
                <span
                  aria-hidden
                  style={{ backgroundColor: player.color }}
                  className="h-4 w-4 rounded-full"
                />
                {player.name}
                {player.pid === pid && <span className="text-white/40"> (you)</span>}
              </span>
              {player.pid === lobby.host && (
                <span className="rounded-full bg-lime-400/20 px-2 py-1 text-xs uppercase tracking-widest text-lime-300">
                  host
                </span>
              )}
            </li>
          ))}
        </ul>
      </section>

      <section className="space-y-2">
        <h2 className="text-xs uppercase tracking-widest text-white/50">
          Round length
        </h2>
        <div className="grid grid-cols-3 gap-2">
          {ROUND_MINUTE_CHOICES.map((minutes) => (
            <button
              key={minutes}
              disabled={!isHost}
              onClick={() => onRoundMinutes(minutes)}
              className={`rounded-xl px-3 py-3 text-lg font-bold disabled:opacity-60 ${
                lobby.round_minutes === minutes
                  ? "bg-lime-400 text-black"
                  : "border border-white/25"
              }`}
            >
              {minutes} min
            </button>
          ))}
        </div>
      </section>

      {lobby.status === "running" ? (
        <p className="rounded-xl bg-lime-400/15 px-4 py-4 text-center text-lg font-bold text-lime-300">
          Round started — go!
        </p>
      ) : isHost ? (
        <button
          onClick={onStart}
          disabled={!lobby.bounds}
          className="rounded-xl bg-lime-400 px-4 py-4 text-lg font-bold text-black disabled:opacity-40"
        >
          Start round
        </button>
      ) : (
        <p className="text-center text-sm text-white/50">
          Waiting for the host to start…
        </p>
      )}
    </div>
  );
}
