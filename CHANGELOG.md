# Changelog

All notable Live House project changes are recorded here.

## 0.1.0 — 2026-09-01

### Added

- Runnable FastAPI live-commerce vertical slice.
- Host studio and viewer web applications.
- Live-session lifecycle and transactional local persistence.
- Sequenced events, snapshots, replay, and WebSocket fanout.
- Chat, reactions, deterministic polls, product pinning, cart, inventory, and mock checkout.
- Generated-scene workflow with deadlines, stale handling, fallback, QA seam, readiness, and explicit on-air control.
- fal queue integration boundary and typed H3 Max adapter.
- fal ED25519 webhook verification and idempotent delivery processing.
- Interactive architecture explorer and overall architecture infographic.
- Docker, Compose, CI, OpenAPI, tests, installable wheel, and consolidated Live House project handoff documents.

### Architectural decisions

- fal is the AI inference plane rather than the viewer broadcast layer.
- The initial implementation is a modular monolith.
- Commerce facts and transactions remain deterministic.
- Realtime domain events are server-sequenced and media-time-aware.
- Generated scenes require buffering, deadlines, QA, fallbacks, and explicit scheduling.

