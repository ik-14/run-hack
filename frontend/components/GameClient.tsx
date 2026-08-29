"use client";

import { HomeScreen } from "@/components/HomeScreen";
import { LobbyScreen } from "@/components/LobbyScreen";
import { useLobby } from "@/lib/useLobby";

export function GameClient() {
  const game = useLobby();

  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-md flex-col justify-center gap-4 p-6">
      {game.error && (
        <p
          role="alert"
          className="rounded-xl bg-red-500/20 px-4 py-3 text-sm text-red-200"
        >
          {game.error}
        </p>
      )}

      {game.lobby ? (
        <LobbyScreen
          lobby={game.lobby}
          pid={game.pid}
          isHost={game.isHost}
          onRoundMinutes={game.setRoundMinutes}
          onStart={game.start}
          onLeave={game.leave}
        />
      ) : (
        <HomeScreen
          busy={game.connection === "connecting"}
          onCreate={game.createRoom}
          onJoin={game.joinRoom}
        />
      )}
    </main>
  );
}
