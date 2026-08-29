import pytest
from fastapi.testclient import TestClient

from app.main import app, rooms
from app.protocol import PALETTE


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
            {
                "pid": joined["pid"],
                "name": "kal",
                "color": joined["color"],
                "connected": True,
                "lat": None,
                "lng": None,
                "trail": [],
                "territory": [],
                "area_m2": 0.0,
                "outside": False,
                "disqualified": False,
            }
        ]

        with client.websocket_connect("/ws") as guest:
            guest.send_json({"type": "join", "room": code.lower(), "name": "sam"})
            guest.receive_json()
            lobby = host.receive_json()

            assert [p["name"] for p in lobby["players"]] == ["kal", "sam"]
            assert lobby["host"] == joined["pid"]


def test_unknown_colour_is_rejected():
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "create", "name": "kal", "color": "#123456"})
        assert ws.receive_json() == {
            "type": "error",
            "detail": "Value error, pick a colour from the palette",
        }


def test_players_get_distinct_colours():
    with TestClient(app) as client, client.websocket_connect("/ws") as host:
        host.send_json({"type": "create", "name": "kal", "color": PALETTE[0]})
        joined = host.receive_json()
        host.receive_json()

        with client.websocket_connect("/ws") as guest:
            guest.send_json(
                {
                    "type": "join",
                    "room": joined["room"],
                    "name": "sam",
                    "color": PALETTE[0],
                }
            )
            assert guest.receive_json()["color"] != PALETTE[0]


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


BOUNDS = {
    "type": "bounds",
    "south": 51.5,
    "west": -0.12,
    "north": 51.505,
    "east": -0.115,
}


def test_host_configures_and_starts():
    with TestClient(app) as client, client.websocket_connect("/ws") as host:
        host.send_json({"type": "create", "name": "kal"})
        host.receive_json()
        host.receive_json()

        host.send_json({"type": "config", "round_minutes": 5})
        assert host.receive_json()["round_minutes"] == 5

        host.send_json({"type": "start"})
        assert host.receive_json() == {
            "type": "error",
            "detail": "draw the play area on the map first",
        }

        host.send_json(BOUNDS)
        assert host.receive_json()["bounds"] == {
            "south": 51.5,
            "west": -0.12,
            "north": 51.505,
            "east": -0.115,
        }

        host.send_json({"type": "start"})
        assert host.receive_json()["status"] == "running"
        assert host.receive_json() == {"type": "started", "round_minutes": 5}


def test_inverted_rectangle_is_rejected():
    with TestClient(app) as client, client.websocket_connect("/ws") as host:
        host.send_json({"type": "create", "name": "kal"})
        host.receive_json()
        host.receive_json()

        host.send_json({**BOUNDS, "north": 51.4})
        assert "positive width" in host.receive_json()["detail"]


def test_positions_are_broadcast_to_the_room():
    with TestClient(app) as client, client.websocket_connect("/ws") as host:
        host.send_json({"type": "create", "name": "kal"})
        host.receive_json()
        host.receive_json()
        host.send_json(BOUNDS)
        host.receive_json()
        host.send_json({"type": "start"})
        host.receive_json()
        host.receive_json()

        host.send_json({"type": "pos", "lat": 51.502, "lng": -0.118, "acc": 5, "t": 0})
        update = host.receive_json()

        assert update["type"] == "pos"
        assert (update["lat"], update["lng"]) == (51.502, -0.118)
        assert update["extend"] is True


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

            guest.send_json({"type": "leave"})
            assert [p["name"] for p in host.receive_json()["players"]] == ["kal"]


def test_a_dropped_socket_leaves_the_runner_in_the_room():
    with TestClient(app) as client, client.websocket_connect("/ws") as host:
        host.send_json({"type": "create", "name": "kal"})
        code = host.receive_json()["room"]
        host.receive_json()

        with client.websocket_connect("/ws") as guest:
            guest.send_json({"type": "join", "room": code, "name": "sam"})
            guest.receive_json()
            guest.receive_json()
            host.receive_json()

        players = host.receive_json()["players"]
        assert [(p["name"], p["connected"]) for p in players] == [
            ("kal", True),
            ("sam", False),
        ]


def test_rejoin_restores_the_runner_mid_round():
    with TestClient(app) as client, client.websocket_connect("/ws") as host:
        host.send_json({"type": "create", "name": "kal"})
        joined = host.receive_json()
        code = joined["room"]
        host.receive_json()

        with client.websocket_connect("/ws") as guest:
            guest.send_json({"type": "join", "room": code, "name": "sam"})
            guest_pid = guest.receive_json()["pid"]
            guest.receive_json()
            host.receive_json()

            host.send_json(BOUNDS)
            host.receive_json()
            guest.receive_json()
            host.send_json({"type": "start"})
            host.receive_json()
            host.receive_json()
            guest.receive_json()
            guest.receive_json()

            guest.send_json({"type": "pos", "lat": 51.502, "lng": -0.118, "acc": 5, "t": 0})
            guest.receive_json()
            host.receive_json()

        host.receive_json()  # guest marked offline

        with client.websocket_connect("/ws") as back:
            back.send_json({"type": "rejoin", "room": code, "pid": guest_pid})
            assert back.receive_json() == {
                "type": "joined",
                "pid": guest_pid,
                "room": code,
                "color": PALETTE[1],
            }
            snapshot = back.receive_json()
            sam = next(p for p in snapshot["players"] if p["pid"] == guest_pid)

            assert snapshot["status"] == "running"
            assert sam["connected"] is True
            assert sam["trail"] == [[51.502, -0.118]]


def test_rejoining_a_dead_room_errors():
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "rejoin", "room": "ZZZZ", "pid": "deadbeef"})
        assert ws.receive_json()["type"] == "error"
