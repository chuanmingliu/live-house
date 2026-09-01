# Architecture decision record

## ADR-001 — fal is an inference layer, not the broadcast plane

**Decision:** fal handles AI inference and generated-media workflows behind an internal gateway. A media origin and CDN distribute the final one-to-many program.

**Reason:** Model transport and GPU sessions scale with interactive inference; viewer media delivery scales with audience size and requires broadcast-specific packaging, caching, failover, and cost controls.

## ADR-002 — start with a modular monolith

**Decision:** Prove contracts, states, idempotency, and failure behavior in one FastAPI application before extracting services.

**Reason:** This minimizes operational complexity while keeping boundaries explicit in service classes, adapters, and event contracts.

## ADR-003 — commerce remains deterministic and authoritative

**Decision:** Product facts, prices, offers, inventory, cart, checkout, payment, and orders are never sourced from model output.

**Reason:** Generated content is probabilistic and cannot safely own commercial truth or regulated claims.

## ADR-004 — synchronize UI with program time

**Decision:** Product pins and scene events carry `program_time_ms`; clients align them with the playback timeline rather than applying them on network arrival.

**Reason:** Viewers have different CDN and player latency, so wall-clock delivery does not imply the same content moment.

## ADR-005 — generation uses a rolling buffer and hard deadlines

**Decision:** AI content is generated ahead of air time, validated, and placed into a ready queue. Late outputs are stale and cannot air.

**Reason:** Continuous broadcast cannot block on nondeterministic model execution.

## ADR-006 — provider credentials are server-side and endpoints are allowlisted

**Decision:** Clients receive application-level authorization only. The backend chooses approved models and calls fal.

**Reason:** This prevents credential disclosure, unbounded spend, and arbitrary endpoint access.

## ADR-007 — model completion is not broadcast approval

**Decision:** Provider completion moves a segment only into validation/QA; explicit scheduler or producer action is required before `ON_AIR`.

**Reason:** Successful generation does not establish safety, product fidelity, continuity, timing suitability, or editorial approval.
