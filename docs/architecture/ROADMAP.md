# Implementation roadmap

## Completed: vertical slice 0.1

- [x] Runnable API and browser UI.
- [x] Live-session state machine.
- [x] Product catalog, pinning, cart, inventory, checkout.
- [x] Sequenced events, snapshot, replay, WebSocket fanout.
- [x] Polls and one-vote-per-user deterministic counts.
- [x] Segment workflow and local mock generation.
- [x] fal queued-submission adapter and typed H3 Max text-to-video arguments.
- [x] fal webhook signature verification and idempotency.
- [x] Segment deadline, failure, stale, ready, and on-air states.
- [x] Automated tests and Docker packaging.

## Increment 0.2: real fal model adapter

1. Exercise the included H3 Max text-to-video adapter against a staging fal account.
2. Add a typed reference-to-video adapter for product and presenter continuity.
3. Add input reference upload/ACL handling.
4. Add request cancellation and status reconciliation.
5. Add cost metadata per request.
6. Run an external webhook test over HTTPS.
7. Add a contract test against an ephemeral or staging fal endpoint.

Definition of done: one real generated segment reaches `READY`; duplicate signed webhooks are harmless; malformed and stale outputs are rejected.

## Increment 0.3: durable platform foundation

- PostgreSQL migrations.
- Transactional outbox.
- Redis connection/presence layer.
- NATS JetStream, Redpanda, or Kafka event distribution.
- Temporal segment workflow.
- OIDC/JWT and role authorization.
- Structured OpenTelemetry traces and metrics.
- Object storage copy of approved fal outputs.

Definition of done: two API replicas can serve the same room without event loss or duplicate inventory commits.

## Increment 0.4: real media plane

- Managed WebRTC/SRT ingest.
- Cloud compositor control service.
- Product lower thirds rendered from catalog data.
- Generated-asset insertion and fallback slate.
- ABR encoding, origin, and low-latency CDN playback.
- Program timeline anchors or timed metadata.
- Active/standby compositor and ingest failover.

Definition of done: viewers receive one continuous stream while the producer inserts a generated segment; product UI stays within the synchronization target.

## Increment 0.5: moderation and quality

- Text safety and prompt-injection classification.
- Approved product-fact retrieval and claim validator.
- Media decode/duration/frame-rate checks.
- NSFW/violence/logo/text/fidelity classifiers.
- Audio loudness, silence, and speech checks.
- Human preview queue and emergency cut.
- Evaluation set for model/prompt regression.

Definition of done: every candidate asset has recorded checks and policy versions; rejected media cannot be scheduled.

## Increment 0.6: production commerce

- Pricing and promotion service.
- Reservation expiration workflow.
- Payment service provider integration.
- Tax, shipping, fraud, orders, cancellation, refund.
- Flash-sale admission control.
- Merchant budget and purchase limits.

Definition of done: payment and order retries are idempotent, inventory cannot be oversold under the tested concurrency envelope, and AI outages do not affect checkout.

## Increment 0.7: audience-directed show director

- Audience-intent aggregation.
- Anti-bot voting.
- Structured scene planner.
- Scene bible and continuity pack.
- Rolling ready-to-air buffer.
- Model routing by deadline, cost, and quality.
- Producer approval policies.

Definition of done: the deterministic winning vote becomes an approved scene within the target deadline, with a tested fallback for every failure state.
