# Product and system requirements

## Original objective

Create a realtime live application inspired by large social-media live-shopping experiences, using fal for AI media generation and realtime inference where appropriate.

## Viewer requirements

- Join a live room quickly and recover transparently after transient disconnects.
- Watch one continuous adaptive-bitrate program.
- Read and send moderated chat.
- React, vote, and participate in audience-directed choices.
- See products synchronized with the exact program moment in which they are presented.
- Inspect products, add to cart, and complete checkout without leaving the live context.
- Continue watching and buying during an AI-generation outage.

## Host and producer requirements

- Create, warm, start, degrade, recover, and end a live session.
- Ingest a camera/microphone or select a virtual-presenter mode.
- Pin products and control approved offers.
- Open polls and observe deterministic results.
- Request AI-generated segments from a constrained scene plan.
- Preview, reject, approve, schedule, and place segments on air.
- Cut immediately to host feed, slate, or approved fallback media.

## AI requirements

- Sanitize and aggregate audience input before planning.
- Produce strict structured scene plans.
- Use only allowed models and bounded budgets.
- Use approved product facts and reference assets.
- Validate prompt, output media, identity, product fidelity, timing, and policy compliance.
- Reject late results and preserve continuity through a rolling ready-to-air buffer.
- Record prompt, model, policy, references, cost, timing, and decision lineage.

## Commerce requirements

- Catalog, price, offer, inventory, tax, shipping, and order systems remain authoritative.
- Checkout revalidates all commercial data.
- Flash-sale inventory is reserved atomically and expires safely.
- Mutation APIs and payment callbacks are idempotent.
- AI-generated overlays never become the source of truth for price or availability.

## Reliability requirements

- Playback, chat, AI generation, and commerce have independent failure domains.
- Every AI request has a deadline and fallback.
- Important sessions use warm capacity, standby ingest, standby composition, and synthetic monitoring.
- Realtime clients recover through snapshot plus sequence replay.
- Late or duplicate provider callbacks do not alter terminal state.

## Security requirements

- Long-lived provider credentials remain server-side.
- Viewer, host, merchant, producer, and moderator permissions are distinct.
- Webhooks are signature-verified before parsing or mutation.
- Prompt injection, abuse, bot voting, fraud, and sensitive product claims receive dedicated controls.
- Private reference assets use restricted storage and retention policies.
