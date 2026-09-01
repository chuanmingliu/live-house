# Live House project context

## 1. Product vision

Build a realtime live-commerce platform comparable in interaction style to TikTok Live shopping, enhanced with AI-generated media. A host or virtual presenter runs a continuous program while viewers watch, chat, vote, react, inspect synchronized products, add products to a cart, and complete checkout.

The product should evolve through three modes:

1. **Human host with AI assistance** — generated B-roll, backgrounds, captions, translation, and short inserts.
2. **Virtual host with managed rundown** — approved scripts, avatar presentation, buffered segments, and operator oversight.
3. **Audience-directed generative channel** — viewers vote or suggest directions, and a constrained show director produces the next approved scene.

## 2. Architectural position of fal

fal provides AI model APIs, queued inference, WebSocket realtime inference, custom serverless GPU applications, and experimental WebRTC/world-model primitives. Within Live House, fal is isolated behind one internal orchestration boundary.

fal must not become:

- The mass-viewer broadcast delivery system.
- The authoritative product, price, promotion, or inventory database.
- The checkout, payment, order, or refund system.
- A client-side secret exposed in web or mobile code.
- A direct recipient of untrusted raw audience prompts.

## 3. Target system planes

### Client and operator plane

- Viewer web and mobile applications.
- Host/seller studio.
- Moderator and merchant administration consoles.

### Edge and media-delivery plane

- API gateway and authentication.
- Regional realtime gateways.
- WebRTC/SRT/RTMP ingest.
- Compositor, encoder, origin, adaptive bitrate packaging, and CDN.

### Core backend plane

- Live-session service.
- Chat, polls, reactions, presence, and audience intent.
- Product catalog, pricing, promotions, inventory, cart, checkout, payments, and orders.
- Notification and moderation services.

### AI control plane

- Audience-intent aggregation.
- Structured show director.
- Prompt compiler and approved product-fact retrieval.
- fal orchestrator and model registry.
- Durable scene workflow, output moderation, QA, and generation budget controls.

### Data and operations plane

- PostgreSQL for transactional state.
- Redis for presence, ephemeral state, and rate limits.
- Kafka, Redpanda, NATS JetStream, or equivalent for durable event distribution.
- Object storage and media CDN for approved assets.
- Analytics warehouse, observability, audit logs, and feature flags.

## 4. Non-negotiable invariants

1. Catalog and commerce services are authoritative for product facts, prices, offers, inventory, and orders.
2. AI-generated text cannot directly change commercial state.
3. Checkout revalidates price, eligibility, promotion, and inventory.
4. Room events are ordered by server-assigned per-session sequence numbers.
5. Product and scene UI events use program/media time rather than WebSocket arrival time.
6. Every generated segment has a deadline, stale time, maximum retries, cost ceiling, and fallback.
7. A model completion does not automatically place content on air.
8. Prompt and output moderation happen before broadcast eligibility.
9. fal credentials and privileged provider calls remain server-side.
10. Webhooks and commerce mutations are idempotent.
11. Playback and checkout continue when AI generation is degraded or unavailable.
12. One program is generated per channel and distributed through a CDN; generation is not repeated per viewer.

## 5. Current implementation

The executable project lives in `apps/live-commerce` and is currently a modular monolith. This is intentional: it proves contracts and failure behavior before services are extracted.

Implemented capabilities:

- FastAPI REST and WebSocket APIs.
- SQLite persistence with guarded transitions.
- Per-room sequenced events, snapshots, replay, and ordered fanout.
- Chat, presence heartbeat, polling, deterministic voting, product pinning, and media-time metadata.
- Catalog, cart, atomic inventory deduction, and idempotent local checkout.
- Segment workflow from plan through moderation, fal/mock submission, QA, ready, fallback, and explicit on-air state.
- Generation deadline watchdog and late-result protection.
- fal model allowlist and typed `minimax/h3-max/text-to-video` adapter.
- Signed ED25519 fal webhook verification, timestamp tolerance, JWKS caching, and idempotent webhook claims.
- Host studio, viewer app, architecture UI, OpenAPI specification, packaging, Docker, and automated tests.

## 6. Current deliberate substitutions

| v0.1 implementation | Production target |
|---|---|
| SQLite | PostgreSQL, migrations, and transactional outbox |
| In-process WebSocket hub | Regional gateways plus Redis/NATS/Kafka fanout |
| `asyncio` task | Temporal or another durable workflow engine |
| Browser source switching | Cloud compositor and one continuous CDN stream |
| Session-start time approximation | Program timeline anchor or timed metadata |
| Query-parameter demo identity | OIDC/JWT and role authorization |
| Minimal prompt checks | Layered text, claim, visual, audio, and human moderation |
| Mock checkout | Payment, tax, shipping, fraud, orders, cancellation, and refund systems |

## 7. Immediate development sequence

### Increment 0.2 — real fal staging path

- Exercise the H3 Max adapter against a staging fal account.
- Add typed reference-to-video support for product and presenter continuity.
- Add private input-reference upload and retention rules.
- Add request status reconciliation, cancellation, and cost metadata.
- Validate signed callbacks over a public HTTPS endpoint.
- Add an opt-in staging contract test.

### Increment 0.3 — durable platform foundation

- PostgreSQL migrations and transactional outbox.
- Redis presence and distributed room state.
- Durable event transport.
- Temporal scene workflow.
- OIDC/JWT and scoped producer/moderator roles.
- OpenTelemetry traces and metrics.
- Private object-storage copy of approved outputs.

### Increment 0.4 — real media plane

- Managed host ingest.
- Cloud compositor control API.
- Deterministic product overlays from catalog data.
- Generated-segment insertion and fallback slate.
- Encoder, origin, LL-HLS/DASH delivery, program-time synchronization, and failover.

## 8. Development rules

- Preserve public contracts unless a migration plan is included.
- Add tests for every state transition, idempotency path, and failure branch.
- Use monotonic server sequence numbers; never trust client timestamps for ordering.
- Reject late provider results instead of airing them out of sequence.
- Keep provider-specific schemas behind adapters.
- Do not introduce a new direct fal call outside the fal gateway/orchestrator boundary.
- Never render generated price, inventory, discount, legal, medical, or shipping claims as authoritative data.
- Keep the viewer functional during generation and realtime-control failures.
- Run the full test suite after every backend change and syntax-check browser JavaScript after UI changes.

## 9. Definition of a production-worthy vertical slice

A live session can run continuously while a producer inserts an approved AI-generated segment into a single uninterrupted broadcast stream; product UI is synchronized to the correct program moment; carts and checkout remain idempotent and inventory-safe; duplicate or delayed provider callbacks are harmless; and every failure has a tested fallback that avoids dead air.
