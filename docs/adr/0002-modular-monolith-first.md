# ADR 0002 — Begin with a modular monolith

- Status: Accepted
- Date: 2026-09-01

## Decision

Validate session, event, commerce, and generation contracts in one deployable FastAPI application before extracting distributed services.

## Consequences

Development and tests remain fast while boundaries stay explicit. SQLite, in-process fanout, and background tasks are temporary implementations behind portable contracts.
