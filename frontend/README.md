# Runner.io frontend

Next.js (App Router) + TypeScript + Tailwind. Designed phone-first: home screen to pick
a name and create/join a room, then the lobby.

```bash
npm install
npm run dev   # http://localhost:3000
```

The WebSocket URL defaults to `ws://<current host>:8000/ws`; override it with
`NEXT_PUBLIC_WS_URL` when the backend runs elsewhere.

Checks: `npm run lint`, `npx tsc --noEmit`, `npm run build`.
