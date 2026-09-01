# ADR 0003 — Synchronize viewer UI to program media time

- Status: Accepted
- Date: 2026-09-01

## Decision

Product, poll, and scene UI events that correspond to content carry `program_time_ms`. Clients apply them relative to the player timeline rather than WebSocket arrival time.

## Consequences

Viewers with different CDN/player latency see commerce UI at the intended content moment. Production requires a reliable wall-clock/media-time anchor or timed stream metadata.
