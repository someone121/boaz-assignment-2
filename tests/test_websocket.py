"""Real-time WebSocket channel and the in-memory ConnectionManager."""

import asyncio

from app.services.ws_manager import ConnectionManager
from tests.conftest import start_session


class FakeSocket:
    def __init__(self, fail: bool = False):
        self.sent: list[dict] = []
        self.fail = fail

    async def accept(self):
        pass

    async def send_json(self, payload):
        if self.fail:
            raise RuntimeError("socket closed")
        self.sent.append(payload)


def test_broadcast_reaches_session_and_global_listeners():
    manager = ConnectionManager()
    in_session, in_global, elsewhere = FakeSocket(), FakeSocket(), FakeSocket()

    async def scenario():
        await manager.connect(in_session, "s1")
        await manager.connect(in_global, "global")
        await manager.connect(elsewhere, "s2")
        await manager.broadcast_event("s1", "POLL_UPDATE", {"x": 1})

    asyncio.run(scenario())
    expected = [{"event": "POLL_UPDATE", "data": {"x": 1}}]
    assert in_session.sent == expected
    assert in_global.sent == expected
    assert elsewhere.sent == []


def test_global_broadcast_is_not_sent_twice():
    manager = ConnectionManager()
    sock = FakeSocket()

    async def scenario():
        await manager.connect(sock, "global")
        await manager.broadcast_event("global", "NEW_FORUM_POST", {})

    asyncio.run(scenario())
    assert len(sock.sent) == 1


def test_failing_socket_is_dropped():
    manager = ConnectionManager()
    dead = FakeSocket(fail=True)

    async def scenario():
        await manager.connect(dead, "s1")
        await manager.broadcast_event("s1", "QUIZ_UPDATE", {})

    asyncio.run(scenario())
    assert "s1" not in manager.active_connections


def test_poll_vote_is_pushed_over_websocket(client):
    session_id = start_session(client)
    with client.websocket_connect(f"/ws/{session_id}") as ws:
        poll = client.post(
            "/api/poll/create",
            json={"session_id": session_id, "prompt": "Clear?", "option_1": "Yes", "option_2": "No"},
        ).json()
        created = ws.receive_json()
        assert created["event"] == "POLL_UPDATE"
        assert created["data"]["poll_id"] == poll["poll_id"]

        client.post("/api/poll/vote", json={"poll_id": poll["poll_id"], "selected_option": "Yes"})
        voted = ws.receive_json()
        assert voted["data"]["results"] == {"Yes": 1, "No": 0}


def test_attendance_done_is_pushed_over_websocket(client):
    session_id = start_session(client)
    with client.websocket_connect(f"/ws/{session_id}") as ws:
        client.post("/api/attendance/stop", params={"session_id": session_id})
        msg = ws.receive_json()
        assert msg["event"] == "ATTENDANCE_DONE"
        assert msg["data"]["download_url"].endswith(session_id)
