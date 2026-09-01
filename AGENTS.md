# Engineering instructions for Live House

This file is the continuation contract for human developers and coding agents working in this repository.

## Read first

Before changing code, read:

1. `PROJECT.md`
2. `docs/architecture/ARCHITECTURE.md`
3. `docs/architecture/EVENT_CONTRACTS.md`
4. `docs/architecture/SECURITY.md`
5. `docs/architecture/ROADMAP.md`
6. Relevant files under `docs/decisions/`

## Non-negotiable invariants

1. **fal is not the viewer broadcast CDN.** Generated media eventually enters a compositor/origin/CDN path.
2. **Commerce truth is deterministic.** AI output cannot set price, promotion, inventory, purchase limit, payment, or order state.
3. **Checkout revalidates.** Never trust a stale product card or model response at checkout time.
4. **Event ordering is server-owned.** Use per-session sequence numbers; do not infer order from client timestamps.
5. **Media synchronization is timeline-based.** Product and scene UI events use `program_time_ms` or equivalent timed metadata.
6. **Generation is deadline-bound.** Every scene has a deadline, stale-after timestamp, bounded retry policy, and fallback.
7. **Provider completion is not approval.** A completed asset must pass policy, QA, storage, and scheduling gates.
8. **Late output stays stale.** No callback may revive a timed-out or cancelled segment to `READY`.
9. **Webhooks are verified before parsing as trusted data.** Preserve raw-body ED25519 verification and timestamp tolerance.
10. **Webhook and payment consumers are idempotent.** Assume duplicate and reordered delivery.
11. **Credentials remain server-side.** Never put `FAL_KEY`, payment secrets, or admin tokens in client code, logs, examples, or fixtures.
12. **AI failure cannot disable playback or checkout.** New dependencies must preserve graceful degradation.

## Current implementation style

- Python 3.11+.
- FastAPI and Pydantic settings.
- Typed Python where practical.
- SQLite is a local implementation detail; domain contracts should remain portable to PostgreSQL.
- Browser code is dependency-free vanilla HTML/CSS/JavaScript in this increment.
- Keep the modular-monolith boundaries explicit rather than scattering logic through route handlers.
- Add comments for invariants and non-obvious failure behavior, not for obvious syntax.

## Change protocol

When adding or changing a domain event:

1. Update the event definition and producer.
2. Update `docs/architecture/EVENT_CONTRACTS.md`.
3. Add or update replay/order/idempotency tests.
4. Update the interactive architecture if the component or flow changed materially.

When adding a fal model:

1. Add a typed adapter with a strict allowlist of accepted fields.
2. Normalize the provider response behind the gateway.
3. Define model-specific deadline, dimensions, and safety defaults.
4. Add unit tests for valid and invalid payloads.
5. Never permit arbitrary caller-selected model IDs.

When adding an external webhook:

1. Verify signatures on the raw body.
2. Enforce timestamp/replay limits.
3. Claim idempotency before side effects.
4. Release or mark retryable claims when processing fails safely.
5. Add duplicate, modified-body, stale-time, and reordered-delivery tests.

When changing inventory or checkout:

1. Preserve atomicity.
2. Require idempotency keys.
3. Test concurrent requests.
4. Separate reservation from final order deduction when production payment is introduced.
5. Never couple purchase completion to AI availability.

## Required verification

Run before considering work complete:

```bash
./scripts/verify.sh
```

At minimum, this must pass:

```bash
python -m compileall -q apps/live-commerce/src
cd apps/live-commerce && pytest
```

For browser changes, validate JavaScript syntax and manually exercise studio, viewer, architecture, and reconnect behavior.

## Near-term priorities

Implement in this order unless a written decision changes it:

1. Real fal staging integration and private asset handling.
2. PostgreSQL, transactional outbox, and distributed event delivery.
3. Durable segment workflow.
4. OIDC/JWT and role authorization.
5. Continuous media compositor/origin/CDN path.
6. Layered moderation and product-claim validation.
7. Production commerce services.
8. Audience-directed show director.

## Scope discipline

Do not prematurely build a bespoke global video CDN, payment processor, or full microservice estate. Buy commodity media/payment capabilities for the pilot and keep internal boundaries replaceable.

## Documentation discipline

- Record a new architectural decision in `docs/decisions/` when it changes a core invariant, service boundary, data owner, transport, or failure policy.
- Keep `PROJECT.md` and `docs/DEVELOPMENT_HANDOFF.md` current at the end of each increment.
- Update `CHANGELOG.md` for externally visible behavior or contract changes.
- Keep `project.yaml` machine-readable and synchronized with the human documents.

