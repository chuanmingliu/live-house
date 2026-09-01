# ADR 0001 — fal is the AI plane, not broadcast delivery

- Status: Accepted
- Date: 2026-09-01

## Decision

Use fal for queued generation, realtime inference, and custom GPU applications. Deliver the final one-to-many program through a media compositor, origin, and CDN.

## Consequences

AI failures can degrade to safe content without stopping playback. Media egress scales independently from model execution, and the media provider remains replaceable.
