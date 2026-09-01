# ADR 0007 — Provider completion requires QA and explicit scheduling

- Status: Accepted
- Date: 2026-09-01

## Decision

A provider success moves an asset into validation. Policy, media QA, canonical storage, timing, and producer/scheduler rules must pass before `READY` or `ON_AIR`.

## Consequences

Technically successful but unsafe, malformed, inconsistent, late, or editorially unsuitable output cannot enter the broadcast.
