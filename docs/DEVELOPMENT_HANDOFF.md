# Development handoff

## What has been delivered

The Live House bundle contains a production-shaped local vertical slice, not a static mockup. It demonstrates host control, persistent session state, ordered realtime events, synchronized viewer UI, a basic commerce flow, fal/mock generation, provider callback verification, segment deadlines, fallback behavior, and explicit broadcast eligibility.

## Where to work

Use `apps/live-commerce` as the active codebase. The standalone architecture demo in `docs/demos` is a communication artifact; the integrated application version is served at `/architecture` from the FastAPI app.

## How to resume work in a new development session

Use this context:

> Continue the Live House project from the repository root. Read `AGENTS.md`, `PROJECT_CONTEXT.md`, `PROJECT_STATUS.yaml`, and the application documentation before editing. Preserve the architectural invariants. Begin with Increment 0.2 unless a different task is explicitly requested. Keep local mock mode working and add tests plus documentation for every contract change.

## Recommended first engineering ticket

**Title:** Complete a real fal staging generation round trip.

**Acceptance criteria:**

- An environment-gated integration test submits a typed request to an allowlisted fal endpoint.
- The provider request ID, model version, submission time, deadline, and estimated/actual cost are persisted.
- The signed callback is verified against raw bytes and current JWKS.
- The returned asset is decoded or probed, copied into controlled private storage, and associated with lineage metadata.
- Duplicate callbacks are no-ops.
- Conflicting callback bodies are rejected and audited.
- A completion after the scene deadline cannot return the scene to `READY`.
- Cancellation/status reconciliation handles callbacks lost during development testing.
- Mock mode and the existing local end-to-end flow remain functional.

## Known boundaries

The current app does not yet provide a managed media ingest/origin/CDN, a cloud compositor, distributed realtime gateways, durable workflows, production identity, complete moderation, or a real payment/order stack. Those omissions are deliberate and documented in the roadmap.
