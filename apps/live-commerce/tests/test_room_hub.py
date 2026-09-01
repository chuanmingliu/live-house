from __future__ import annotations

from typing import Any

import pytest

from livecommerce.events import RoomHub


class FakeWebSocket:
    def __init__(self) -> None:
        self.accepted = False
        self.sent: list[dict[str, Any]] = []

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, message: dict[str, Any]) -> None:
        self.sent.append(message)


@pytest.mark.asyncio
async def test_snapshot_is_sent_before_buffered_room_events() -> None:
    hub = RoomHub()
    websocket = FakeWebSocket()

    await hub.connect("live-1", websocket, client_id="viewer-1", role="viewer")  # type: ignore[arg-type]
    await hub.broadcast("live-1", {"type": "product.pinned", "sequence": 8})
    assert websocket.sent == []

    await hub.send_snapshot(
        "live-1", websocket, {"type": "session.snapshot", "sequence": 7}  # type: ignore[arg-type]
    )
    await hub.activate("live-1", websocket)  # type: ignore[arg-type]

    assert [message["type"] for message in websocket.sent] == [
        "session.snapshot",
        "product.pinned",
    ]


@pytest.mark.asyncio
async def test_concurrent_broker_publishes_follow_durable_sequence(tmp_path) -> None:
    import asyncio

    from livecommerce.events import EventBroker
    from livecommerce.models import SessionCreate
    from livecommerce.store import Store

    store = Store(tmp_path / "events.db")
    store.initialize()
    session = store.create_session(SessionCreate(title="ordering"))
    hub = RoomHub()
    websocket = FakeWebSocket()
    await hub.connect(session["id"], websocket, client_id="viewer", role="viewer")  # type: ignore[arg-type]
    await hub.send_snapshot(
        session["id"], websocket, {"type": "session.snapshot", "sequence": 0}  # type: ignore[arg-type]
    )
    await hub.activate(session["id"], websocket)  # type: ignore[arg-type]

    broker = EventBroker(store, hub)
    await asyncio.gather(
        broker.publish(session["id"], "event.a", {}),
        broker.publish(session["id"], "event.b", {}),
        broker.publish(session["id"], "event.c", {}),
    )

    delivered = websocket.sent[1:]
    assert [event["sequence"] for event in delivered] == [1, 2, 3]
    assert [event["sequence"] for event in store.get_events(session["id"])] == [1, 2, 3]
    store.close()
