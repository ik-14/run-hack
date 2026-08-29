# Runner.io — design & implementation plan

Team HTTP 418

## 1. The idea

Paper.io, but the controller is your legs.

You open a web app on your phone, join a room with your friends, and start running.
Your GPS trail is drawn live on a shared map. When you run a loop and return to your
own territory, everything you enclosed becomes yours. Run through someone else's
trail while they're outside their territory and they die. Most area when the round
timer ends wins.

Rounds are self-contained — no accounts, no persistent territory, no progression.
Join, run for N minutes, see the winner, play again.

## 2. Core rules

| Concept | Rule |
|---|---|
| Identity | You pick a name **and a colour** in the lobby. Your colour is your trail and your territory everywhere in the game. |
| Play area | The host draws a **rectangle on the map** in the lobby. Everything happens inside it. |
| Spawn | On joining, you get a small starting circle of territory at your current GPS position (~25 m radius). |
| Trail | Whenever you are outside your own territory, your path is recorded as a trail. |
| Claim | When your trail re-enters your own territory, the enclosed region (trail + territory boundary) is added to your territory. |
| Steal | Claimed area is subtracted from every other player's territory. |
| Kill | If any player's position crosses another player's *active trail*, the trail owner dies. |
| Death | On death you lose your trail and respawn with a fresh starting circle (round continues). |
| Self-kill | Crossing your own trail kills you too. |
| Out of bounds | Leave the rectangle and your phone **vibrates** and shows a countdown. Come back within `OUT_OF_BOUNDS_GRACE` (30 s) or you are **disqualified** for the rest of the round. |
| Win | Highest total territory area (m²) when the round timer hits zero. |

Anti-cheat is explicitly **out of scope** for the hackathon (we do a basic speed sanity
check — >8 m/s sustained is flagged — but nothing more).

## 3. Architecture

```
 phone browser (Next.js/TS)          server (Python, FastAPI)
┌──────────────────────┐            ┌───────────────────────────────────┐
│ Geolocation API      │  position  │ Room registry (in-memory)         │
│  watchPosition()     ├───────────►│  ├─ players[] (name, colour)      │
│                      │   ~1 Hz    │  ├─ bounds: rectangle             │
│ Map view (MapLibre)  │            │  ├─ territories: Polygon per pid  │
│  ├─ own trail        │◄───────────┤  ├─ trails: LineString per pid    │
│  ├─ territories      │  state     │  └─ round timer                   │
│  └─ other players    │  ~5 Hz     │ Geometry engine (shapely)         │
│                      │            │  ├─ close_loop() → polygon        │
│ Lobby / HUD / result │            │  ├─ union/difference territories  │
└──────────────────────┘            │  └─ trail intersection → kills    │
                                    └───────────────────────────────────┘
```

- **Client is dumb, server is authoritative.** The phone only sends
  `{lat, lng, accuracy, t}`; every claim, kill and score is computed server-side so
  two phones can't disagree.
- **All state in memory**, keyed by room code. A room dies when it's empty. No DB.
- **Geometry in a metric projection.** We convert lat/lng to a local
  equirectangular metre grid centred on the room's spawn point, do all polygon maths
  there, and convert back for rendering. Avoids degenerate area maths near the poles
  and keeps shapely fast.

### Why the server is a separate Python service

Vercel serverless functions can't hold long-lived socket connections or in-memory room
state, so the realtime half is its own long-lived process: **FastAPI + `websockets`**,
deployed to Railway/Fly/Render, with the Next.js UI on Vercel. Geometry is
[shapely](https://shapely.readthedocs.io) (the turf.js equivalent) — same predicates
(`union`, `difference`, `intersects`, `is_simple`), and the whole game loop stays in one
typed codebase (ruff + pyright strict).

## 4. Protocol

Client → server:

```ts
{ type: 'create', name: 'kal', color: '#84cc16' }
{ type: 'join',   room: 'ABCD', name: 'kal', color: '#84cc16' }
{ type: 'config', round_minutes: 10 }                        // host only
{ type: 'bounds', south, west, north, east }                 // host only, drawn rectangle
{ type: 'start' }                                            // host only
{ type: 'pos',    lat: 51.5, lng: -0.12, acc: 8, t: 1724930000000 }
```

Server → client:

```ts
{ type: 'joined', pid, room }
{ type: 'lobby',  room, status, host, round_minutes, bounds, players: [{ pid, name, color }] }
{ type: 'state',  t, ends_at, players: [{ pid, name, color, lat, lng, alive, area, out_of_bounds_since }],
                  trails:  { pid: [[lat,lng], ...] },
                  territories: { pid: GeoJSONPolygon } }
{ type: 'event',  kind: 'claim'|'kill'|'death'|'respawn'|'out_of_bounds'|'returned'|'disqualified',
                  pid, victim?, area?, deadline? }
{ type: 'over',   standings: [{ pid, name, color, area }] }
{ type: 'error',  detail }
```

Colours come from a fixed 8-swatch palette so two players can never pick near-identical
shades and so the server can hand a free colour to anyone who doesn't choose.

`state` is broadcast on a fixed 200 ms tick, not per position update — territories are
sent as diffs (only polygons that changed since the last tick) to keep messages small.

## 5. Geometry: the interesting bit

```
onPosition(pid, p):
  if inside(territory[pid], p):
      if trail[pid].length > 1:
          claim(pid)                     # closed the loop
      trail[pid] = []
  else:
      trail[pid].push(p)
      if selfIntersects(trail[pid]): kill(pid, by=pid)
      for other in players:
          if trail[other] and crosses(p, prev(p), trail[other]): kill(other, by=pid)

claim(pid):
  loop      = polygonize(trail[pid] + shortestPathThroughTerritory)
  gained    = union(territory[pid], loop)
  for other != pid:
      territory[other] = difference(territory[other], gained)
  territory[pid] = gained
```

Known edge cases we accept: GPS jitter can make a "loop" self-intersect just before
closing (we smooth with a 3-point moving average + 5 m minimum step distance), and
`difference()` can split a victim's territory into multiple polygons (we keep all
parts, MultiPolygon is fine).

## 6. Screens

1. **Home** — enter name, **pick a colour**, create room or join with a 4-letter code.
2. **Lobby** — player list with colours, round length picker (5 / 10 / 20 min), and a map
   on which the host **drags out the play-area rectangle**; everyone else watches it
   appear. Host presses Start (blocked until bounds exist). Requests geolocation
   permission here so nobody is blocked at the whistle.
3. **Game** — full-screen map, own trail bright, others' trails dimmed, boundary
   rectangle drawn on top, HUD with timer, your area, live leaderboard, and a
   kill/claim toast feed. Leaving the rectangle vibrates the phone and starts a visible
   return countdown.
4. **Results** — final standings, area totals, "play again" back to lobby.

## 7. Milestones

Rough order, each one is demoable on its own:

- **Phase 0 — skeleton (t+0 to t+2h).** Next.js app, room create/join over WS, name +
  colour picker, host sets round length and drags the boundary rectangle, two phones
  showing each other's dots move on a MapLibre map. Deployment target chosen and
  deployed on day one, not at the end.
- **Phase 1 — trails & claims (t+2 to t+6h).** Spawn circles, trail recording,
  loop detection, `claim()` with union/difference, area scoring on the HUD.
- **Phase 2 — combat & bounds (t+6 to t+9h).** Trail crossing → kill, death/respawn,
  out-of-bounds vibration + 30 s disqualification countdown, event toasts, round timer
  and results screen.
- **Phase 3 — feel (t+9 to t+14h).** Lobby polish, colours per player, wake-lock so
  the screen doesn't sleep mid-run, GPS smoothing, reconnect handling, sound on claim.
- **Phase 4 — demo prep.** A **simulator mode** (fake GPS driven by dragging on a
  desktop map) so the judges see the game without anyone sprinting round the block.
  Build this early if Phase 1 debugging gets painful — it doubles as our test harness.

## 8. Work split (4 people)

- **Geometry / server**: room state, tick loop, shapely claim + kill logic.
- **Client / map**: MapLibre rendering, trails, territories, smooth interpolation.
- **UI / flow**: home, lobby, HUD, results, permissions and error states.
- **Infra / demo**: deployment, simulator mode, phone testing, pitch and demo script.

The protocol in §4 is the contract — agree on it first and the four tracks can move
in parallel from hour one.

## 9. Risks

| Risk | Mitigation |
|---|---|
| GPS accuracy (±10 m in cities) is bigger than the game's features | Large spawn circles, 5 m minimum step, demo in an open park |
| Phone screen sleeps / browser throttles background tabs | Screen Wake Lock API, keep the tab foregrounded, warn in the lobby |
| Nobody wants to run during the demo | Simulator mode (Phase 4) |
| Polygon ops get slow with long trails | Simplify trails (shapely `simplify`, ~2 m tolerance) before every claim |
| Serverless can't hold sockets | Decided up front in Phase 0 |

## 10. Stack

Next.js (App Router) + TypeScript · MapLibre GL JS with free OpenStreetMap raster tiles
(no API key to babysit during a hackathon) · FastAPI + `websockets` on Python 3.12 for
the realtime server, linted with ruff and type-checked with pyright in strict mode ·
shapely for geometry · Tailwind for UI · Vercel + Railway for hosting. No database —
rooms live in the server process and disappear when empty.
