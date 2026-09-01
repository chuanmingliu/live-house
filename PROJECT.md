# Live House project brief

## Mission

Build a realtime live-commerce platform in which human or virtual hosts can broadcast, viewers can interact and purchase, and fal-powered AI can generate approved media segments without becoming a dependency of the core stream or commerce transaction path.

The long-term experience should support three operating modes:

1. **Human host with AI assistance** — generated B-roll, backgrounds, captions, translation, product demonstrations, and short avatar inserts.
2. **Virtual presenter with a managed rundown** — approved scripts and buffered generated scenes under operator control.
3. **Audience-directed generative channel** — viewers vote or submit ideas; a structured show director converts the deterministic outcome into a moderated scene plan.

## Product principles

- Playback and checkout remain available when AI generation is unavailable.
- fal is the generation/inference plane, not the mass-broadcast delivery plane.
- Catalog, pricing, inventory, promotions, and orders are deterministic systems of record.
- AI never invents or commits prices, inventory, discounts, legal claims, payments, or orders.
- Viewer UI events are synchronized to media time, not WebSocket arrival time.
- Every generated scene has a deadline, stale time, fallback, and explicit approval/scheduling decision.
- Provider webhooks are signature-verified, replay-safe, and idempotent.
- No long-lived provider credential is shipped to a browser or mobile client.

## Repository status

### Delivered in 0.1

- FastAPI modular monolith.
- Host studio and viewer web applications.
- Live-room lifecycle and persisted state.
- Sequenced events, WebSocket fanout, snapshots, and replay.
- Chat, reactions, polls, and deterministic voting.
- Catalog, product pinning, carts, inventory, and mock checkout.
- Generated-scene lifecycle and local mock generation.
- fal async queue adapter and webhook verifier.
- Typed H3 Max text-to-video input adapter.
- Interactive architecture explorer.
- Docker, Compose, CI, OpenAPI, packaging, and tests.

### Deliberately not production-complete

- Managed WebRTC/SRT ingest and CDN delivery.
- Continuous cloud composition and generated-segment insertion.
- Staging verification with a paid fal account.
- PostgreSQL/outbox, distributed event bus, Redis presence, or Temporal workflows.
- OIDC/JWT and role enforcement.
- Full multimodal moderation and product-claim verification.
- Payment provider, tax, shipping, fraud, orders, returns, and refunds.
- Multi-region operation, load tests, chaos tests, and disaster recovery.

## Current architecture

The current code is a modular monolith because this is the lowest-risk way to prove state, ordering, deadline, and idempotency invariants. Network service extraction should occur only when a clear scaling or ownership boundary exists.

```text
Browser surfaces
  ├── Host studio
  ├── Viewer app
  └── Interactive architecture
        │
        ▼
FastAPI control plane
  ├── Live session APIs
  ├── Realtime WebSocket hub
  ├── Chat and polls
  ├── Catalog/cart/checkout
  ├── Segment workflow
  ├── fal gateway
  └── fal webhook verification
        │
        ▼
SQLite + in-process event broker + local assets
```

The production target separates edge, realtime, transaction, AI control, media, and analytics planes. See `docs/MASTER_ARCHITECTURE.md`.

## Immediate work package: increment 0.2

### Goal

Prove one real fal-generated segment through the exact production callback path while preserving all current invariants.

### Work items

- Configure a staging environment with an API-scoped fal key.
- Expose the webhook through a stable HTTPS endpoint.
- Add a typed image/reference-to-video model adapter.
- Add private reference-asset upload and expiry controls.
- Add provider request status reconciliation.
- Add cancellation where the chosen endpoint supports it.
- Record provider, model, request, duration, cost, and output metadata.
- Copy approved output to project-owned object storage.
- Add contract tests or a staging smoke-test command.
- Document exact staging setup and teardown.

### Definition of done

- A real request reaches `READY` through a signed webhook.
- Duplicate signed webhook delivery is harmless.
- Modified-body and stale-timestamp signatures are rejected.
- A completion received after the scene deadline remains stale and never returns to `READY`.
- Output is copied to controlled storage before it can be scheduled.
- The provider key is absent from browser bundles, logs, and committed files.
- The test suite and verification script pass.

## Development commands

```bash
./scripts/bootstrap.sh
make run
make test
```

## Important routes

| Route | Purpose |
|---|---|
| `/` | Project landing page |
| `/studio` | Host/producer UI |
| `/viewer` | Viewer UI |
| `/architecture` | Interactive architecture map |
| `/docs` | OpenAPI UI |
| `/health` | Liveness/config summary |
| `/v1/demo/bootstrap` | Seed a local demo session |
| `/v1/webhooks/fal` | fal completion callback |

## Project ownership map

| Area | Current location | Future extraction target |
|---|---|---|
| HTTP and WebSocket APIs | `apps/live-commerce/src/livecommerce/main.py` | API and regional realtime gateways |
| Events and room hub | `apps/live-commerce/src/livecommerce/events.py` | Durable bus plus distributed fanout |
| Transaction store | `apps/live-commerce/src/livecommerce/store.py` | PostgreSQL repositories and outbox |
| Domain workflows | `apps/live-commerce/src/livecommerce/services.py` | Temporal workflows and activities |
| fal boundary | `apps/live-commerce/src/livecommerce/fal_gateway.py` | Dedicated generation orchestrator |
| Model contracts | `apps/live-commerce/src/livecommerce/model_adapters.py` | Versioned model registry |
| Webhook security | `apps/live-commerce/src/livecommerce/webhook_verifier.py` | Shared provider-webhook gateway |
| Browser applications | `apps/live-commerce/src/livecommerce/static/` | Separate deployable web apps |

## Success measures

The first production pilot should demonstrate:

- Stable playback during AI failure.
- No lost or duplicate purchase commits.
- No late generated scene entering the program.
- Product card synchronization within the selected target.
- A complete audit trail from audience intent to scene plan, fal request, QA, schedule, and on-air event.
- A tested operator emergency fallback.

