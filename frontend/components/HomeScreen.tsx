"use client";

import { FormEvent, useState } from "react";

import { PALETTE, ROOM_CODE_LENGTH } from "@/lib/protocol";

type Props = {
  busy: boolean;
  onCreate: (name: string, color: string) => void;
  onJoin: (room: string, name: string, color: string) => void;
};

export function HomeScreen({ busy, onCreate, onJoin }: Props) {
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [color, setColor] = useState<string>(PALETTE[0]);

  const trimmedName = name.trim();
  const canCreate = trimmedName.length > 0 && !busy;
  const canJoin = canCreate && code.length === ROOM_CODE_LENGTH;

  const submitJoin = (event: FormEvent) => {
    event.preventDefault();
    if (canJoin) onJoin(code, trimmedName, color);
  };

  return (
    <form onSubmit={submitJoin} className="flex flex-col gap-6">
      <header className="space-y-1">
        <h1 className="text-4xl font-black tracking-tight">Runner.io</h1>
        <p className="text-sm text-white/60">
          Paper.io, but the controller is your legs.
        </p>
      </header>

      <label className="flex flex-col gap-2">
        <span className="text-xs uppercase tracking-widest text-white/50">
          Your name
        </span>
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          maxLength={16}
          autoComplete="off"
          placeholder="kal"
          className="rounded-xl bg-white/10 px-4 py-3 text-lg outline-none ring-lime-400 focus:ring-2"
        />
      </label>

      <fieldset className="flex flex-col gap-2">
        <legend className="text-xs uppercase tracking-widest text-white/50">
          Your colour
        </legend>
        <div className="grid grid-cols-8 gap-2">
          {PALETTE.map((swatch) => (
            <button
              key={swatch}
              type="button"
              aria-label={`colour ${swatch}`}
              aria-pressed={color === swatch}
              onClick={() => setColor(swatch)}
              style={{ backgroundColor: swatch }}
              className={`aspect-square rounded-full transition ${
                color === swatch
                  ? "ring-2 ring-white ring-offset-2 ring-offset-[#0a0a0a]"
                  : "opacity-70"
              }`}
            />
          ))}
        </div>
        <p className="text-xs text-white/40">
          Someone already took it? You&apos;ll get the next free colour.
        </p>
      </fieldset>

      <button
        type="button"
        disabled={!canCreate}
        onClick={() => onCreate(trimmedName, color)}
        className="rounded-xl bg-lime-400 px-4 py-4 text-lg font-bold text-black disabled:opacity-40"
      >
        Create a room
      </button>

      <div className="flex items-center gap-3 text-xs uppercase tracking-widest text-white/40">
        <span className="h-px flex-1 bg-white/15" />
        or
        <span className="h-px flex-1 bg-white/15" />
      </div>

      <label className="flex flex-col gap-2">
        <span className="text-xs uppercase tracking-widest text-white/50">
          Room code
        </span>
        <input
          value={code}
          onChange={(event) =>
            setCode(
              event.target.value
                .toUpperCase()
                .replace(/[^A-Z]/g, "")
                .slice(0, ROOM_CODE_LENGTH),
            )
          }
          inputMode="text"
          autoCapitalize="characters"
          autoComplete="off"
          placeholder="ABCD"
          className="rounded-xl bg-white/10 px-4 py-3 text-center text-3xl font-mono tracking-[0.5em] outline-none ring-lime-400 focus:ring-2"
        />
      </label>

      <button
        type="submit"
        disabled={!canJoin}
        className="rounded-xl border border-white/25 px-4 py-4 text-lg font-bold disabled:opacity-40"
      >
        Join room
      </button>
    </form>
  );
}
