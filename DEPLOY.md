# Deploying Runner.io

Two deploys, one push. The frontend goes to Vercel, the game server goes to Render,
and the frontend is told where the server lives with one environment variable.
Both providers auto-deploy on every push to `main` once connected.

## Why the backend is not on Vercel

Vercel Functions *can* serve WebSockets now (public beta), but two things about this
game don't fit:

- A connection is pinned to one function instance, and **new** connections are not
  guaranteed to land on the same one. Our rooms live in process memory
  (`backend/app/lobby.py`), so two friends joining the same code could land on
  different instances and never see each other. Fixing that means moving room state
  into Redis.
- The server also runs a 200 ms broadcast tick per room, which is a long-lived
  background loop, not a request/response.

A single always-on Render web service keeps the whole room in one process, which is
exactly what the design assumes. `render.yaml` in the repo root already describes it.

## 1. Backend → Render

1. Render dashboard → **New → Blueprint** → pick the `ik-14/run-hack` repo.
   It reads `render.yaml` and creates the `runner-io-backend` web service.
2. Wait for the deploy, then check `https://<service>.onrender.com/api/health`
   returns `{"status":"ok"}`.
3. The WebSocket URL is `wss://<service>.onrender.com/ws` — copy it.

Free instances sleep after ~15 minutes idle and take ~30 s to wake, which drops
in-memory rooms. Hit the URL once before the demo, or use a paid instance on the day.

## 2. Frontend → Vercel

1. Vercel → **Add New → Project** → import `ik-14/run-hack`.
2. Set **Root Directory** to `frontend` (Settings → Build and Deployment). Vercel then
   auto-detects Next.js and configures the build. Do not add a `vercel.json` with
   `--prefix frontend` commands — that fights Vercel's own monorepo handling and the
   Next.js builder still looks for `next` in the *root* `package.json`, which fails.
3. Add an environment variable for all environments:

   ```
   NEXT_PUBLIC_WS_URL = wss://<service>.onrender.com/ws
   ```

   This is baked in at build time (`serverUrl()` in `frontend/lib/protocol.ts`), so
   after changing it you must redeploy, not just restart.
4. Deploy. Every push to `main` redeploys; PRs get preview URLs.

## 3. Check it works across devices

- Open the Vercel URL on two phones on different networks (mobile data, not just
  wifi) — this is the thing that only breaks in production.
- Geolocation requires a secure context: Vercel gives you HTTPS, so the socket
  **must** be `wss://`. A `ws://` URL is blocked as mixed content and the lobby will
  silently never connect.
- Create a room on one device, join with the code on the other; both should appear
  in each other's player list within a second.

## Local development

Unchanged — with no `NEXT_PUBLIC_WS_URL` set, the client falls back to
`ws://<page host>:8000/ws`:

```bash
(cd backend && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000)
(cd frontend && npm run dev)
```
