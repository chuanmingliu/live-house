# Event contracts

Every durable room event follows this envelope:

```json
{
  "event_id": "evt_…",
  "type": "product.pinned",
  "occurred_at": "2026-09-01T00:00:00+00:00",
  "session_id": "live_…",
  "sequence": 42,
  "program_time_ms": 12500,
  "correlation_id": "SKU-AURORA-LAMP",
  "causation_id": null,
  "payload": {}
}
```

## Ordering and replay

- `sequence` is monotonically increasing within one live session.
- Clients persist their highest applied sequence.
- On reconnect, clients supply `after_sequence`.
- The server replies with a current snapshot plus a bounded replay.
- Consumers must ignore duplicates and older sequences.
- `occurred_at` is an audit timestamp; it is not a media synchronization clock.

## Program-time behavior

`program_time_ms` is measured from `session.program_started_at`. A viewer compares it with the current program timeline and applies the UI event at the intended media position. This prevents product cards from appearing at different content moments merely because network latency differs.

The production media player should use a server-provided wall-clock/media-time anchor or timed metadata from the stream. The current UI uses the session start timestamp as the first implementation seam.

## Events currently emitted

| Event | Purpose |
|---|---|
| `live.session.created` | Room was created. |
| `live.session.started` | Program clock starts. |
| `live.session.ended` | Room is terminal. |
| `chat.message.published` | Moderated room chat. |
| `poll.opened` | Audience choice became active. |
| `poll.updated` | Deterministic vote counts changed. |
| `product.pinned` | Product becomes featured at program time. |
| `product.unpinned` | Featured product is removed. |
| `product.clicked` | Viewer commerce intent signal. |
| `checkout.completed` | Idempotent checkout committed. |
| `inventory.updated` | Catalog inventory changed after checkout. |
| `scene.plan.created` | Generation workflow was created. |
| `scene.plan.approved` | Starter moderation gate passed. |
| `fal.job.submitted` | Provider request ID was persisted. |
| `fal.job.completed` | Provider returned a usable media URL. |
| `fal.job.failed` | Provider failed. |
| `segment.qa.passed` | Current QA seam accepted the asset. |
| `segment.ready` | Segment is eligible for scheduling. |
| `segment.on_air` | Scheduler selected the segment for program time. |
| `segment.fallback_activated` | A rejected, failed, or late segment will not air. |

## WebSocket client messages

```json
{"type":"presence.heartbeat","payload":{}}
{"type":"chat.send","payload":{"content":"Hello"}}
{"type":"vote.cast","payload":{"poll_id":"poll_…","option_id":"option_a"}}
{"type":"product.click","payload":{"sku":"SKU-AURORA-LAMP"}}
```

High-volume reactions are intentionally not in the durable starter contract. Production should fan them out ephemerally and persist aggregates rather than one database row per reaction.
