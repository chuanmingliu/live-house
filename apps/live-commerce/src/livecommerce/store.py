from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .models import (
    PollCreate,
    ProductCreate,
    SegmentGenerateRequest,
    SegmentState,
    SessionCreate,
    SessionState,
)


def utc_now() -> datetime:
    return datetime.now(UTC)


def iso_now() -> str:
    return utc_now().isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


class NotFoundError(KeyError):
    pass


class ConflictError(RuntimeError):
    pass


class ValidationError(ValueError):
    pass


class Store:
    """SQLite-backed transactional store for the runnable vertical slice.

    A single process owns this store. The interfaces intentionally expose the seams that
    should later be implemented by PostgreSQL, Redis, and a durable event backbone.
    """

    def __init__(self, database_path: Path):
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(
            str(database_path), check_same_thread=False, isolation_level=None
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA journal_mode = WAL")
        self._connection.execute("PRAGMA synchronous = NORMAL")

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                yield self._connection
            except Exception:
                self._connection.rollback()
                raise
            else:
                self._connection.commit()

    def initialize(self) -> None:
        schema = """
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            state TEXT NOT NULL,
            playback_url TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            program_started_at TEXT,
            pinned_sku TEXT,
            active_poll_id TEXT,
            last_sequence INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS products (
            sku TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            price_minor INTEGER NOT NULL CHECK(price_minor >= 0),
            currency TEXT NOT NULL,
            inventory INTEGER NOT NULL CHECK(inventory >= 0),
            image_url TEXT,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS events (
            session_id TEXT NOT NULL,
            sequence INTEGER NOT NULL,
            event_id TEXT NOT NULL UNIQUE,
            type TEXT NOT NULL,
            occurred_at TEXT NOT NULL,
            program_time_ms INTEGER,
            correlation_id TEXT,
            causation_id TEXT,
            payload_json TEXT NOT NULL,
            PRIMARY KEY(session_id, sequence),
            FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS events_session_type_idx ON events(session_id, type);

        CREATE TABLE IF NOT EXISTS polls (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            question TEXT NOT NULL,
            options_json TEXT NOT NULL,
            state TEXT NOT NULL,
            created_at TEXT NOT NULL,
            closed_at TEXT,
            FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS votes (
            poll_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            option_id TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY(poll_id, user_id),
            FOREIGN KEY(poll_id) REFERENCES polls(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS carts (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            state TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS cart_items (
            cart_id TEXT NOT NULL,
            sku TEXT NOT NULL,
            quantity INTEGER NOT NULL CHECK(quantity > 0),
            PRIMARY KEY(cart_id, sku),
            FOREIGN KEY(cart_id) REFERENCES carts(id) ON DELETE CASCADE,
            FOREIGN KEY(sku) REFERENCES products(sku)
        );

        CREATE TABLE IF NOT EXISTS checkout_sessions (
            id TEXT PRIMARY KEY,
            cart_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            idempotency_key TEXT NOT NULL UNIQUE,
            state TEXT NOT NULL,
            total_minor INTEGER NOT NULL,
            currency TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(cart_id) REFERENCES carts(id),
            FOREIGN KEY(session_id) REFERENCES sessions(id)
        );

        CREATE TABLE IF NOT EXISTS segments (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            state TEXT NOT NULL,
            prompt TEXT NOT NULL,
            product_skus_json TEXT NOT NULL,
            duration_ms INTEGER NOT NULL,
            model_id TEXT,
            fal_request_id TEXT UNIQUE,
            asset_url TEXT,
            error TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            deadline_at TEXT NOT NULL,
            on_air_program_time_ms INTEGER,
            FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS segments_session_idx ON segments(session_id, created_at DESC);

        CREATE TABLE IF NOT EXISTS webhook_receipts (
            request_id TEXT PRIMARY KEY,
            received_at TEXT NOT NULL,
            body_sha256 TEXT NOT NULL,
            status TEXT NOT NULL,
            processed_at TEXT
        );
        """
        with self._lock:
            self._connection.executescript(schema)

    # ---------- sessions ----------

    def create_session(self, request: SessionCreate) -> dict[str, Any]:
        session_id = new_id("live")
        now = iso_now()
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO sessions(
                    id, title, state, playback_url, created_at, updated_at, last_sequence
                ) VALUES (?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    session_id,
                    request.title,
                    SessionState.DRAFT.value,
                    request.playback_url,
                    now,
                    now,
                ),
            )
        return self.get_session(session_id)

    def get_session(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
        if row is None:
            raise NotFoundError(f"session not found: {session_id}")
        return dict(row)

    def list_sessions(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM sessions ORDER BY created_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def set_session_state(self, session_id: str, target: SessionState) -> dict[str, Any]:
        current = self.get_session(session_id)
        allowed: dict[str, set[SessionState]] = {
            SessionState.DRAFT.value: {SessionState.WARMING, SessionState.READY, SessionState.LIVE},
            SessionState.SCHEDULED.value: {SessionState.WARMING, SessionState.READY},
            SessionState.WARMING.value: {SessionState.READY, SessionState.DEGRADED},
            SessionState.READY.value: {SessionState.LIVE, SessionState.ENDED},
            SessionState.LIVE.value: {SessionState.DEGRADED, SessionState.ENDING, SessionState.ENDED},
            SessionState.DEGRADED.value: {SessionState.LIVE, SessionState.ENDING, SessionState.ENDED},
            SessionState.ENDING.value: {SessionState.ENDED},
            SessionState.ENDED.value: set(),
        }
        if target != SessionState(current["state"]) and target not in allowed[current["state"]]:
            raise ConflictError(f"cannot transition {current['state']} -> {target.value}")

        started_at = current["program_started_at"]
        if target == SessionState.LIVE and not started_at:
            started_at = iso_now()

        with self.transaction() as conn:
            conn.execute(
                """
                UPDATE sessions
                SET state = ?, program_started_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (target.value, started_at, iso_now(), session_id),
            )
        return self.get_session(session_id)

    def current_program_time_ms(self, session_id: str) -> int:
        session = self.get_session(session_id)
        started_at = session.get("program_started_at")
        if not started_at:
            return 0
        started = datetime.fromisoformat(started_at)
        return max(0, int((utc_now() - started).total_seconds() * 1000))

    # ---------- products ----------

    def upsert_products(self, products: list[ProductCreate]) -> list[dict[str, Any]]:
        now = iso_now()
        with self.transaction() as conn:
            for product in products:
                conn.execute(
                    """
                    INSERT INTO products(
                        sku, title, description, price_minor, currency, inventory, image_url, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(sku) DO UPDATE SET
                        title = excluded.title,
                        description = excluded.description,
                        price_minor = excluded.price_minor,
                        currency = excluded.currency,
                        inventory = excluded.inventory,
                        image_url = excluded.image_url,
                        updated_at = excluded.updated_at
                    """,
                    (
                        product.sku,
                        product.title,
                        product.description,
                        product.price_minor,
                        product.currency,
                        product.inventory,
                        product.image_url,
                        now,
                    ),
                )
        return self.list_products()

    def list_products(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute("SELECT * FROM products ORDER BY sku").fetchall()
        return [dict(row) for row in rows]

    def get_product(self, sku: str) -> dict[str, Any]:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM products WHERE sku = ?", (sku,)
            ).fetchone()
        if row is None:
            raise NotFoundError(f"product not found: {sku}")
        return dict(row)

    def pin_product(self, session_id: str, sku: str | None) -> dict[str, Any]:
        self.get_session(session_id)
        if sku is not None:
            self.get_product(sku)
        with self.transaction() as conn:
            conn.execute(
                "UPDATE sessions SET pinned_sku = ?, updated_at = ? WHERE id = ?",
                (sku, iso_now(), session_id),
            )
        return self.get_session(session_id)

    # ---------- events and snapshots ----------

    def append_event(
        self,
        session_id: str,
        event_type: str,
        payload: dict[str, Any],
        *,
        program_time_ms: int | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
    ) -> dict[str, Any]:
        event_id = new_id("evt")
        occurred_at = iso_now()
        with self.transaction() as conn:
            updated = conn.execute(
                """
                UPDATE sessions
                SET last_sequence = last_sequence + 1, updated_at = ?
                WHERE id = ?
                """,
                (occurred_at, session_id),
            )
            if updated.rowcount != 1:
                raise NotFoundError(f"session not found: {session_id}")
            sequence = conn.execute(
                "SELECT last_sequence FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()[0]
            conn.execute(
                """
                INSERT INTO events(
                    session_id, sequence, event_id, type, occurred_at,
                    program_time_ms, correlation_id, causation_id, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    sequence,
                    event_id,
                    event_type,
                    occurred_at,
                    program_time_ms,
                    correlation_id,
                    causation_id,
                    json.dumps(payload, separators=(",", ":")),
                ),
            )
        return {
            "event_id": event_id,
            "type": event_type,
            "occurred_at": occurred_at,
            "session_id": session_id,
            "sequence": sequence,
            "program_time_ms": program_time_ms,
            "correlation_id": correlation_id,
            "causation_id": causation_id,
            "payload": payload,
        }

    def get_events(
        self, session_id: str, *, after_sequence: int = 0, limit: int = 250
    ) -> list[dict[str, Any]]:
        self.get_session(session_id)
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT * FROM events
                WHERE session_id = ? AND sequence > ?
                ORDER BY sequence ASC
                LIMIT ?
                """,
                (session_id, after_sequence, limit),
            ).fetchall()
        return [self._event_from_row(row) for row in rows]

    @staticmethod
    def _event_from_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "event_id": row["event_id"],
            "type": row["type"],
            "occurred_at": row["occurred_at"],
            "session_id": row["session_id"],
            "sequence": row["sequence"],
            "program_time_ms": row["program_time_ms"],
            "correlation_id": row["correlation_id"],
            "causation_id": row["causation_id"],
            "payload": json.loads(row["payload_json"]),
        }

    def snapshot(
        self, session_id: str, *, after_sequence: int = 0, replay_limit: int = 250
    ) -> dict[str, Any]:
        session = self.get_session(session_id)
        pinned_product = (
            self.get_product(session["pinned_sku"]) if session.get("pinned_sku") else None
        )
        active_poll = (
            self.get_poll(session["active_poll_id"])
            if session.get("active_poll_id")
            else None
        )
        return {
            "session": session,
            "program_time_ms": self.current_program_time_ms(session_id),
            "products": self.list_products(),
            "pinned_product": pinned_product,
            "active_poll": active_poll,
            "segments": self.list_segments(session_id),
            "last_sequence": session["last_sequence"],
            "replay": self.get_events(
                session_id, after_sequence=after_sequence, limit=replay_limit
            ),
        }

    # ---------- polls ----------

    def create_poll(self, session_id: str, request: PollCreate) -> dict[str, Any]:
        self.get_session(session_id)
        poll_id = new_id("poll")
        now = iso_now()
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO polls(id, session_id, question, options_json, state, created_at)
                VALUES (?, ?, ?, ?, 'OPEN', ?)
                """,
                (
                    poll_id,
                    session_id,
                    request.question,
                    json.dumps([option.model_dump() for option in request.options]),
                    now,
                ),
            )
            conn.execute(
                "UPDATE sessions SET active_poll_id = ?, updated_at = ? WHERE id = ?",
                (poll_id, now, session_id),
            )
        return self.get_poll(poll_id)

    def get_poll(self, poll_id: str) -> dict[str, Any]:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM polls WHERE id = ?", (poll_id,)
            ).fetchone()
        if row is None:
            raise NotFoundError(f"poll not found: {poll_id}")
        poll = dict(row)
        poll["options"] = json.loads(poll.pop("options_json"))
        poll["counts"] = self.poll_counts(poll_id)
        return poll

    def poll_counts(self, poll_id: str) -> dict[str, int]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT option_id, COUNT(*) AS count
                FROM votes WHERE poll_id = ? GROUP BY option_id
                """,
                (poll_id,),
            ).fetchall()
        return {row["option_id"]: row["count"] for row in rows}

    def vote(self, poll_id: str, user_id: str, option_id: str) -> dict[str, Any]:
        poll = self.get_poll(poll_id)
        if poll["state"] != "OPEN":
            raise ConflictError("poll is closed")
        valid_options = {option["id"] for option in poll["options"]}
        if option_id not in valid_options:
            raise ValidationError("unknown poll option")
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO votes(poll_id, user_id, option_id, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(poll_id, user_id) DO UPDATE SET
                    option_id = excluded.option_id,
                    updated_at = excluded.updated_at
                """,
                (poll_id, user_id, option_id, iso_now()),
            )
        return self.get_poll(poll_id)

    # ---------- carts and checkout ----------

    def create_cart(self, user_id: str) -> dict[str, Any]:
        cart_id = new_id("cart")
        now = iso_now()
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO carts(id, user_id, state, created_at, updated_at) VALUES (?, ?, 'OPEN', ?, ?)",
                (cart_id, user_id, now, now),
            )
        return self.get_cart(cart_id)

    def get_cart(self, cart_id: str) -> dict[str, Any]:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM carts WHERE id = ?", (cart_id,)
            ).fetchone()
            item_rows = self._connection.execute(
                """
                SELECT ci.sku, ci.quantity, p.title, p.price_minor, p.currency, p.inventory
                FROM cart_items ci JOIN products p ON p.sku = ci.sku
                WHERE ci.cart_id = ? ORDER BY ci.sku
                """,
                (cart_id,),
            ).fetchall()
        if row is None:
            raise NotFoundError(f"cart not found: {cart_id}")
        cart = dict(row)
        cart["items"] = [dict(item) for item in item_rows]
        cart["total_minor"] = sum(
            item["quantity"] * item["price_minor"] for item in cart["items"]
        )
        cart["currency"] = cart["items"][0]["currency"] if cart["items"] else None
        return cart

    def add_cart_item(self, cart_id: str, sku: str, quantity: int) -> dict[str, Any]:
        cart = self.get_cart(cart_id)
        if cart["state"] != "OPEN":
            raise ConflictError("cart is not open")
        product = self.get_product(sku)
        if quantity > product["inventory"]:
            raise ConflictError("requested quantity exceeds available inventory")
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO cart_items(cart_id, sku, quantity) VALUES (?, ?, ?)
                ON CONFLICT(cart_id, sku) DO UPDATE SET quantity = quantity + excluded.quantity
                """,
                (cart_id, sku, quantity),
            )
            combined_quantity = conn.execute(
                "SELECT quantity FROM cart_items WHERE cart_id = ? AND sku = ?",
                (cart_id, sku),
            ).fetchone()[0]
            if combined_quantity > product["inventory"]:
                raise ConflictError("cart quantity exceeds available inventory")
            conn.execute(
                "UPDATE carts SET updated_at = ? WHERE id = ?", (iso_now(), cart_id)
            )
        return self.get_cart(cart_id)

    def checkout(
        self, cart_id: str, session_id: str, idempotency_key: str
    ) -> dict[str, Any]:
        self.get_session(session_id)
        with self.transaction() as conn:
            existing = conn.execute(
                "SELECT * FROM checkout_sessions WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if existing is not None:
                replay = dict(existing)
                replay["idempotent_replay"] = True
                return replay

            cart = conn.execute("SELECT * FROM carts WHERE id = ?", (cart_id,)).fetchone()
            if cart is None:
                raise NotFoundError(f"cart not found: {cart_id}")
            if cart["state"] != "OPEN":
                raise ConflictError("cart is not open")

            items = conn.execute(
                """
                SELECT ci.sku, ci.quantity, p.price_minor, p.currency, p.inventory
                FROM cart_items ci JOIN products p ON p.sku = ci.sku
                WHERE ci.cart_id = ?
                """,
                (cart_id,),
            ).fetchall()
            if not items:
                raise ValidationError("cart is empty")
            currencies = {item["currency"] for item in items}
            if len(currencies) != 1:
                raise ValidationError("all cart items must use the same currency")

            total_minor = 0
            for item in items:
                if item["quantity"] > item["inventory"]:
                    raise ConflictError(f"insufficient inventory for {item['sku']}")
                total_minor += item["quantity"] * item["price_minor"]

            for item in items:
                updated = conn.execute(
                    """
                    UPDATE products
                    SET inventory = inventory - ?, updated_at = ?
                    WHERE sku = ? AND inventory >= ?
                    """,
                    (item["quantity"], iso_now(), item["sku"], item["quantity"]),
                )
                if updated.rowcount != 1:
                    raise ConflictError(f"inventory changed for {item['sku']}")

            checkout_id = new_id("checkout")
            now = iso_now()
            conn.execute(
                """
                INSERT INTO checkout_sessions(
                    id, cart_id, session_id, idempotency_key, state,
                    total_minor, currency, created_at
                ) VALUES (?, ?, ?, ?, 'COMPLETED', ?, ?, ?)
                """,
                (
                    checkout_id,
                    cart_id,
                    session_id,
                    idempotency_key,
                    total_minor,
                    next(iter(currencies)),
                    now,
                ),
            )
            conn.execute(
                "UPDATE carts SET state = 'CHECKED_OUT', updated_at = ? WHERE id = ?",
                (now, cart_id),
            )
            result = conn.execute(
                "SELECT * FROM checkout_sessions WHERE id = ?", (checkout_id,)
            ).fetchone()
        created = dict(result)
        created["idempotent_replay"] = False
        return created

    # ---------- segments ----------

    def create_segment(
        self,
        session_id: str,
        request: SegmentGenerateRequest,
        *,
        model_id: str | None,
        deadline_seconds: int,
    ) -> dict[str, Any]:
        self.get_session(session_id)
        for sku in request.product_skus:
            self.get_product(sku)
        segment_id = new_id("seg")
        now = utc_now()
        deadline = now + timedelta(seconds=deadline_seconds)
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO segments(
                    id, session_id, state, prompt, product_skus_json, duration_ms,
                    model_id, created_at, updated_at, deadline_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    segment_id,
                    session_id,
                    SegmentState.PLANNED.value,
                    request.prompt,
                    json.dumps(request.product_skus),
                    request.duration_ms,
                    model_id,
                    now.isoformat(),
                    now.isoformat(),
                    deadline.isoformat(),
                ),
            )
        return self.get_segment(segment_id)

    def get_segment(self, segment_id: str) -> dict[str, Any]:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM segments WHERE id = ?", (segment_id,)
            ).fetchone()
        if row is None:
            raise NotFoundError(f"segment not found: {segment_id}")
        result = dict(row)
        result["product_skus"] = json.loads(result.pop("product_skus_json"))
        return result

    def list_segments(self, session_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM segments WHERE session_id = ? ORDER BY created_at DESC LIMIT 50",
                (session_id,),
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["product_skus"] = json.loads(item.pop("product_skus_json"))
            result.append(item)
        return result

    def update_segment(
        self,
        segment_id: str,
        *,
        state: SegmentState | None = None,
        fal_request_id: str | None = None,
        asset_url: str | None = None,
        error: str | None = None,
        on_air_program_time_ms: int | None = None,
    ) -> dict[str, Any]:
        current = self.get_segment(segment_id)
        values = {
            "state": state.value if state else current["state"],
            "fal_request_id": fal_request_id
            if fal_request_id is not None
            else current["fal_request_id"],
            "asset_url": asset_url if asset_url is not None else current["asset_url"],
            "error": error if error is not None else current["error"],
            "on_air_program_time_ms": on_air_program_time_ms
            if on_air_program_time_ms is not None
            else current["on_air_program_time_ms"],
        }
        with self.transaction() as conn:
            conn.execute(
                """
                UPDATE segments SET
                    state = ?, fal_request_id = ?, asset_url = ?, error = ?,
                    on_air_program_time_ms = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    values["state"],
                    values["fal_request_id"],
                    values["asset_url"],
                    values["error"],
                    values["on_air_program_time_ms"],
                    iso_now(),
                    segment_id,
                ),
            )
        return self.get_segment(segment_id)

    def find_segment_by_request_id(self, request_id: str) -> dict[str, Any]:
        with self._lock:
            row = self._connection.execute(
                "SELECT id FROM segments WHERE fal_request_id = ?", (request_id,)
            ).fetchone()
        if row is None:
            raise NotFoundError(f"fal request not found: {request_id}")
        return self.get_segment(row["id"])

    def claim_webhook(self, request_id: str, body_sha256: str) -> bool:
        """Claim one provider delivery for processing.

        A repeated request ID with different bytes is rejected. A failed handler can
        release its claim so a provider retry is able to make progress.
        """
        with self.transaction() as conn:
            existing = conn.execute(
                "SELECT * FROM webhook_receipts WHERE request_id = ?", (request_id,)
            ).fetchone()
            if existing is not None:
                if existing["body_sha256"] != body_sha256:
                    raise ConflictError("webhook request id was reused with a different body")
                return False
            conn.execute(
                """
                INSERT INTO webhook_receipts(
                    request_id, received_at, body_sha256, status
                ) VALUES (?, ?, ?, 'PROCESSING')
                """,
                (request_id, iso_now(), body_sha256),
            )
        return True

    def complete_webhook(self, request_id: str) -> None:
        with self.transaction() as conn:
            updated = conn.execute(
                """
                UPDATE webhook_receipts
                SET status = 'COMPLETED', processed_at = ?
                WHERE request_id = ?
                """,
                (iso_now(), request_id),
            )
            if updated.rowcount != 1:
                raise NotFoundError(f"webhook receipt not found: {request_id}")

    def release_webhook(self, request_id: str) -> None:
        with self.transaction() as conn:
            conn.execute(
                "DELETE FROM webhook_receipts WHERE request_id = ? AND status = 'PROCESSING'",
                (request_id,),
            )
