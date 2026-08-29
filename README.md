!

We are team HTTP 418.

# Runner.io

Paper.io, but you claim territory by actually running. Mobile web app, GPS trails on a
shared map, closed loops become your land, round-based multiplayer with friends.

See [DESIGN.md](./DESIGN.md) for the full design and implementation plan.

## Repo layout

- `backend/` — Python FastAPI game server (in-memory rooms, WebSocket protocol).
  Ruff for lint/format, Pyright in strict mode, pytest.
- `frontend/` — Next.js + TypeScript + Tailwind mobile web client.

## Running both halves

```bash
(cd backend && uv sync && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000)
(cd frontend && npm install && npm run dev)
```

Open `http://localhost:3000` on your phone (same network) or desktop.

## Deploying

Frontend on Vercel, game server on Render, both auto-deploying from `main`.
See [DEPLOY.md](./DEPLOY.md).

Ethan test
