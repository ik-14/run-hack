"use client";

import { LobbyState, ROUND_MINUTE_CHOICES } from "@/lib/protocol";

type Props = {
  lobby: LobbyState;
  pid: string | null;
  isHost: boolean;
  onRoundMinutes: (minutes: number) => void;
  onStart: () => void;
  onLeave: () => void;
};

export function LobbyScreen({
  lobby,
  pid,
  isHost,
  onRoundMinutes,
  onStart,
  onLeave,
}: Props) {
  return (
    <div className="flex flex-col gap-6">
      <header className="space-y-2">
        <button
          onClick={onLeave}
          className="text-xs uppercase tracking-widest text-white/50"
        >
          ← Leave
        </button>
        <p className="text-xs uppercase tracking-widest text-white/50">
          Room code
        </p>
        <p className="font-mono text-5xl font-black tracking-[0.3em] text-lime-400">
          {lobby.room}
        </p>
        <p className="text-sm text-white/60">
          Share the code — everyone joins from their own phone.
        </p>
      </header>

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
                {player.pid === pid && (
                  <span className="text-white/40"> (you)</span>
                )}
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
          className="rounded-xl bg-lime-400 px-4 py-4 text-lg font-bold text-black"
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
