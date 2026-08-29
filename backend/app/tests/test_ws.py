import pytest
from fastapi.testclient import TestClient

from app.main import app, rooms


@pytest.fixture(autouse=True)
def fresh_registry():
    yield
    rooms.clear()


def test_health():
    with TestClient(app) as client:
        assert client.get("/api/health").json() == {"status": "ok"}


def test_create_then_join_broadcasts_lobby():
    with TestClient(app) as client, client.websocket_connect("/ws") as host:
        host.send_json({"type": "create", "name": "kal"})
        joined = host.receive_json()
        code = joined["room"]
        assert joined["type"] == "joined"
        assert host.receive_json()["players"] == [
            {"pid": joined["pid"], "name": "kal", "connected": True}
        ]

        with client.websocket_connect("/ws") as guest:
            guest.send_json({"type": "join", "room": code.lower(), "name": "sam"})
            guest.receive_json()
            lobby = host.receive_json()

            assert [p["name"] for p in lobby["players"]] == ["kal", "sam"]
            assert lobby["host"] == joined["pid"]


def test_guest_cannot_start():
    with TestClient(app) as client, client.websocket_connect("/ws") as host:
        host.send_json({"type": "create", "name": "kal"})
        code = host.receive_json()["room"]
        host.receive_json()

        with client.websocket_connect("/ws") as guest:
            guest.send_json({"type": "join", "room": code, "name": "sam"})
            guest.receive_json()
            guest.receive_json()

            guest.send_json({"type": "start"})
            assert guest.receive_json() == {
                "type": "error",
                "detail": "only the host can do that",
            }


def test_host_configures_and_starts():
    with TestClient(app) as client, client.websocket_connect("/ws") as host:
        host.send_json({"type": "create", "name": "kal"})
        host.receive_json()
        host.receive_json()

        host.send_json({"type": "config", "round_minutes": 5})
        assert host.receive_json()["round_minutes"] == 5

        host.send_json({"type": "start"})
        assert host.receive_json()["status"] == "running"
        assert host.receive_json() == {"type": "started", "round_minutes": 5}


def test_joining_missing_room_errors():
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "join", "room": "ZZZZ", "name": "kal"})
        assert ws.receive_json()["type"] == "error"


def test_message_before_joining_errors():
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "start"})
        assert ws.receive_json() == {
            "type": "error",
            "detail": "join a room before sending anything else",
        }


def test_leaving_updates_the_other_players():
    with TestClient(app) as client, client.websocket_connect("/ws") as host:
        host.send_json({"type": "create", "name": "kal"})
        code = host.receive_json()["room"]
        host.receive_json()

        with client.websocket_connect("/ws") as guest:
            guest.send_json({"type": "join", "room": code, "name": "sam"})
            guest.receive_json()
            guest.receive_json()
            host.receive_json()

        assert [p["name"] for p in host.receive_json()["players"]] == ["kal"]
