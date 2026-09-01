# Next Sprint — Milestone 0.2: Real fal Staging Integration

## Sprint objective

Prove the existing provider boundary against a real fal staging account without weakening offline development, idempotency, deadlines, or safety. The milestone is complete when one real generated asset reaches `READY` through a verified public callback and all failure cases remain deterministic.

## LH-020 — Staging configuration and smoke command

**Work**

- Add an explicit `FAL_ENV=mock|staging|production` configuration.
- Add validation for required staging variables.
- Add a CLI command that submits one known-safe generation request.
- Log normalized request ID, model, adapter version, deadline, and correlation ID without logging credentials.

**Acceptance criteria**

- Mock remains the default.
- Staging cannot start with a missing key, model allowlist, or public callback URL.
- The smoke command records a provider request ID.
- Unit tests cover configuration errors.

## LH-021 — Typed reference-to-video adapter

**Work**

- Select an approved fal endpoint supporting image/reference-to-video.
- Add typed input/output Pydantic models.
- Reject unknown fields and arbitrary model IDs.
- Support product/presenter reference IDs, aspect ratio, duration, and safety controls.
- Persist adapter name and version.

**Acceptance criteria**

- Invalid reference, duration, or dimensions fail before provider submission.
- Adapter contract has unit tests and documented example payloads.
- Generic fallback is not used for the approved reference endpoint.

## LH-022 — Private reference asset workflow

**Work**

- Introduce an `AssetStore` interface.
- Implement local development storage and a production object-store adapter seam.
- Validate media type, byte size, dimensions, and checksum.
- Use private objects and time-limited signed access.
- Record asset owner, purpose, consent/rights metadata, and retention class.

**Acceptance criteria**

- Unreleased product and presenter references are never public by default.
- Duplicate uploads can be identified by checksum.
- Expired references fail cleanly before generation.
- Tests cover invalid type, oversize file, and unauthorized access.

## LH-023 — Provider status reconciliation and cancellation

**Work**

- Add provider status lookup behind `GenerationGateway`.
- Reconcile `SUBMITTED`/`GENERATING` jobs after process restart or missed callback.
- Add deadline-aware cancellation where supported.
- Ignore successful completion after `STALE` or `CANCELLED`.
- Add a bounded periodic reconciler.

**Acceptance criteria**

- A missed webhook can be reconciled exactly once.
- A terminal local state never regresses.
- Late success does not reach `READY`.
- Reconciler cannot create an unbounded provider polling loop.

## LH-024 — Generation telemetry and cost metadata

**Work**

- Store submission, queue, execution, callback, QA, and ready timestamps.
- Persist provider/model/adapter and normalized usage or cost metadata.
- Emit OpenTelemetry-ready structured logs and metrics.
- Add per-session generation totals.

**Acceptance criteria**

- Each segment exposes end-to-end and provider latency.
- Missing provider cost is represented as unknown, not zero.
- Metrics do not expose prompts containing private data.

## LH-025 — Public HTTPS webhook integration

**Work**

- Deploy or tunnel a staging callback endpoint.
- Validate signature, timestamp, raw-body hash, and request ID.
- Test duplicate delivery and same-ID/different-body conflict.
- Add replay-safe operator documentation.

**Acceptance criteria**

- A genuine signed callback succeeds.
- Modified body, invalid signature, stale timestamp, and conflicting duplicate fail.
- A duplicate valid callback is harmless.
- Callback response meets provider timeout expectations.

## LH-026 — Approved-output storage and QA boundary

**Work**

- Fetch provider output through a controlled downloader.
- Validate HTTPS host policy, size, media type, checksum, decode, duration, and dimensions.
- Copy approved media into project-controlled private object storage.
- Schedule only the copied canonical asset, not the transient provider URL.

**Acceptance criteria**

- Inaccessible, oversized, malformed, or wrong-duration output fails.
- The canonical asset has lineage back to provider request and source references.
- Provider URL expiry does not break an already approved segment.

## LH-027 — Staging contract test

**Work**

- Add an opt-in test marker disabled in normal offline CI.
- Submit a bounded safe request to staging.
- Wait for verified callback or reconcile status.
- Assert final state, output metadata, and idempotency.
- Enforce a cost and time limit.

**Acceptance criteria**

- Offline unit suite remains deterministic.
- Staging test is explicit, budget-limited, and self-cleaning.
- Test artifacts and secrets are not committed.

## Sprint-wide definition of done

- All existing tests remain green.
- New provider behavior is behind interfaces and typed adapters.
- No long-lived fal key reaches browser code.
- Every real request has a deadline and fallback.
- Malformed, unsafe, late, or noncanonical media cannot become `READY`.
- The staging runbook documents setup, execution, cleanup, and incident handling.
