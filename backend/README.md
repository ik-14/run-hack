# Runner.io backend

FastAPI game server. All room state is in memory — restarting the process wipes every
lobby.

```bash
uv sync
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Checks:

```bash
uv run ruff check . && uv run ruff format --check .
uv run pyright
uv run pytest
```

The client talks to `ws://<host>:8000/ws`; the lobby subset of the protocol
(`create`, `join`, `config`, `start`) is described in [../DESIGN.md](../DESIGN.md) §4.
