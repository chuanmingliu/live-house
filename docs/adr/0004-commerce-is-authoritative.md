# ADR 0004 — Commerce is authoritative; AI is advisory

- Status: Accepted
- Date: 2026-09-01

## Decision

Catalog, pricing, promotion, inventory, checkout, payment, and order services are the only authorities for commerce facts and state. AI receives approved facts and cannot mutate these systems directly.

## Consequences

Purchase decisions are revalidated deterministically, and prices or regulated claims are rendered from trusted data rather than generated pixels or speech.
