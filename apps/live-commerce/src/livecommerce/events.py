from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket

from .store import Store


@dataclass(slots=True)
class RoomConnection:
    websocket: WebSocket
    client_id: str
    role: str
    ready: bool = False
    pending: list[dict[str, Any]] = field(default_factory=list)
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class RoomHub:
    """In-process WebSocket fanout with snapshot-before-events ordering.

    A connection enters the room in a non-ready state. Broadcasts are buffered until the
    server has sent its initial snapshot, preventing a new event from overtaking that
    snapshot and then being overwritten by older state on the client.
    """

    def __init__(self, *, pending_limit: int = 500) -> None:
        self._rooms: dict[str, dict[int, RoomConnection]] = {}
        self._lock = asyncio.Lock()
        self.pending_limit = pending_limit

    async def connect(
        self, session_id: str, websocket: WebSocket, *, client_id: str, role: str
    ) -> None:
        await websocket.accept()
        async with self._lock:
            self._rooms.setdefault(session_id, {})[id(websocket)] = RoomConnection(
                websocket=websocket,
                client_id=client_id,
                role=role,
            )

    async def send_snapshot(
        self, session_id: str, websocket: WebSocket, message: dict[str, Any]
    ) -> None:
        connection = await self._get_connection(session_id, websocket)
        if connection is None:
            return
        await self._send(connection, message)

    async def activate(self, session_id: str, websocket: WebSocket) -> None:
        connection = await self._get_connection(session_id, websocket)
        if connection is None:
            return
        # Hold the per-connection send lock while flipping to ready and flushing the
        # buffer. A concurrent broadcast can therefore never overtake buffered events.
        try:
            async with connection.send_lock:
                async with self._lock:
                    current = self._rooms.get(session_id, {}).get(id(websocket))
                    if current is None:
                        return
                    current.ready = True
                    pending = list(current.pending)
                    current.pending.clear()
                for message in pending:
                    await connection.websocket.send_json(message)
        except Exception:
            await self.disconnect(session_id, websocket)

    async def send_personal(
        self, session_id: str, websocket: WebSocket, message: dict[str, Any]
    ) -> None:
        connection = await self._get_connection(session_id, websocket)
        if connection is None:
            return
        await self._send(connection, message)

    async def disconnect(self, session_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            room = self._rooms.get(session_id)
            if not room:
                return
            room.pop(id(websocket), None)
            if not room:
                self._rooms.pop(session_id, None)

    async def broadcast(self, session_id: str, message: dict[str, Any]) -> None:
        ready: list[RoomConnection] = []
        async with self._lock:
            for connection in self._rooms.get(session_id, {}).values():
                if connection.ready:
                    ready.append(connection)
                else:
                    connection.pending.append(message)
                    if len(connection.pending) > self.pending_limit:
                        # Preserve the latest state changes. Snapshot replay remains the
                        # recovery mechanism if this limit is ever reached.
                        del connection.pending[: len(connection.pending) - self.pending_limit]

        stale: list[WebSocket] = []
        for connection in ready:
            try:
                await self._send(connection, message)
            except Exception:
                stale.append(connection.websocket)
        for websocket in stale:
            await self.disconnect(session_id, websocket)

    async def connection_count(self, session_id: str) -> int:
        async with self._lock:
            return len(self._rooms.get(session_id, {}))

    async def _get_connection(
        self, session_id: str, websocket: WebSocket
    ) -> RoomConnection | None:
        async with self._lock:
            return self._rooms.get(session_id, {}).get(id(websocket))

    @staticmethod
    async def _send(connection: RoomConnection, message: dict[str, Any]) -> None:
        async with connection.send_lock:
            await connection.websocket.send_json(message)


class EventBroker:
    def __init__(self, store: Store, hub: RoomHub):
        self.store = store
        self.hub = hub
        self._session_locks: dict[str, asyncio.Lock] = {}

    async def publish(
        self,
        session_id: str,
        event_type: str,
        payload: dict[str, Any],
        *,
        program_time_ms: int | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
    ) -> dict[str, Any]:
        # Serialize persistence and fanout per session so the WebSocket delivery order
        # is identical to the durable sequence order, even under concurrent requests.
        lock = self._session_locks.setdefault(session_id, asyncio.Lock())
        async with lock:
            event = self.store.append_event(
                session_id,
                event_type,
                payload,
                program_time_ms=program_time_ms,
                correlation_id=correlation_id,
                causation_id=causation_id,
            )
            await self.hub.broadcast(session_id, event)
            return event
