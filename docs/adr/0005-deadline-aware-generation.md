# ADR 0005 — Generation is asynchronous, deadline-aware, and fallback-first

- Status: Accepted
- Date: 2026-09-01

## Decision

Every generated segment has an intended air time, generation deadline, stale time, bounded retry policy, cost ceiling, and fallback asset. Provider completion alone never makes an asset broadcastable.

## Consequences

The show remains continuous through provider latency or failure, and late results cannot appear at the wrong point in the program.
