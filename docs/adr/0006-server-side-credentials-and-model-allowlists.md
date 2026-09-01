# ADR 0006 — Keep provider credentials server-side and models allowlisted

- Status: Accepted
- Date: 2026-09-01

## Decision

Clients authenticate to Live House. Only the backend or a narrowly scoped short-lived token path may call approved fal endpoints; long-lived provider keys remain server-side.

## Consequences

The platform controls spend, model access, auditability, safety defaults, and provider replacement without exposing privileged credentials.
