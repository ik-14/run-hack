---
name: testing-runner-io
description: How to run and UI-test Runner.io (Next.js frontend + FastAPI websocket backend) end to end, including mocking two players' GPS through Chrome DevTools Protocol.
---

# Testing Runner.io end to end

## Running the app

```bash
(cd backend && ~/.local/bin/uv run uvicorn app.main:app --host 0.0.0.0 --port 8000)
(cd frontend && npm run dev)            # http://localhost:3000
```

No accounts, no DB, no credentials. Rooms are in-memory and disappear when empty.
The client picks the WS URL from `NEXT_PUBLIC_WS_URL`, defaulting to
`ws://<page host>:8000/ws` (`frontend/lib/protocol.ts`).

## Devin Secrets Needed

None.

## Two players at once

Use **two separate, both-visible Chrome windows** tiled side by side, not two tabs:
geolocation `watchPosition` callbacks are throttled/suspended in hidden background
tabs, so a backgrounded second player stops sending fixes.

```bash
wmctrl -l -G                                  # find the window ids
wmctrl -i -r <id1> -e 0,0,0,800,1100
wmctrl -i -r <id2> -e 0,800,0,800,1100
```

## Mocking GPS (the only game input)

Drive `Emulation.setGeolocationOverride` over CDP. Chrome's debug port on Devin boxes
is usually **29229** (check the `--remote-debugging-port` flag in `ps aux | grep chrome`),
targets are listed at `http://localhost:<port>/json`.

Key gotchas:
- The override is **session-scoped**: keep one long-lived CDP websocket connection open
  (e.g. `python3 -i` REPL, `/usr/bin/python3` has the `websockets` package) for the whole
  test. Closing the connection reverts the mock.
- Grant permission first with `Browser.grantPermissions {origin, ["geolocation"]}`,
  otherwise the page shows a permission prompt.
- Never call `getCurrentPosition` via `Runtime.evaluate` with `awaitPromise` on a hidden
  tab — it can hang forever. Verify the mock through the app UI (the dot on the map).
- Identify which CDP target is which window with `window.screenX`.

## Server rules that will silently eat your fake fixes

From `backend/app/lobby.py` / `territory.py`:
- Speed sanity check: a fix is **discarded** if it implies > 12 m/s, with the gap between
  fixes floored at 2 s → move at most ~20 m per fix. A big teleport looks like "nothing
  happened".
- Trail vertices need ≥ 5 m of movement; play area sides must be 50 m–5 km.
- A loop closes when the trail self-crosses or comes back within 15 m of its start, and a
  claim must be ≥ 100 m². A 4×4 grid of 10 m steps around a 40 m square claims ~1600 m².
- Out of bounds: 30 s grace, timed off the *device* clock in the fixes, then disqualified.
  Note the server only broadcasts a full lobby snapshot on disqualification, so other
  clients do **not** show the amber "outside" tag during the countdown — only "OUT" at the end.

## Reading authoritative state without a third player

Instead of joining an observer client (which would show up in the player list), install a
read-only WS sniffer before load via
`Page.addScriptToEvaluateOnNewDocument` that stores every parsed message on
`window.__msgs` / `window.__lobby`. That gives exact `bounds` lat/lng for planning a run.

## Known fragile UI area

`MapView` renders a plain `<div className=...>` that MapLibre mutates. Any parent
re-render that changes that `className` (e.g. `h-64` → `h-80` when the round starts in
`LobbyScreen.tsx`) drops MapLibre's own `maplibregl-map` class, and the map canvas jumps
to the top-left of the page. If the map looks displaced, check
`getComputedStyle(container).position === 'static'`.
