# Live House

**Live House** is an AI-native realtime live-commerce platform project. The target experience combines a continuous livestream, realtime audience interaction, synchronized products and checkout, and fal-powered AI media generation without making AI inference a dependency of playback or commerce.

This repository is the canonical handoff bundle for continued development. It contains the executable v0.1 vertical slice, architecture and security documents, interactive demonstrations, generated visual assets, tests, API contracts, release artifacts, and a machine-readable project status file.

## Start here

1. Read [`PROJECT_CONTEXT.md`](../PROJECT_CONTEXT.md) for scope, architectural decisions, invariants, and the immediate development sequence.
2. Read [`AGENTS.md`](../AGENTS.md) before making code changes with an AI coding agent.
3. Run the current application from [`apps/live-commerce`](../apps/live-commerce).
4. Open the standalone interactive architecture at [`docs/demos/interactive-live-commerce-architecture.html`](demos/interactive-live-commerce-architecture.html).
5. Review [`PROJECT_STATUS.yaml`](../PROJECT_STATUS.yaml) for current capabilities and planned increments.

## Project map

```text
live-house/
├── README.md
├── AGENTS.md
├── PROJECT_CONTEXT.md
├── PROJECT_STATUS.yaml
├── CHANGELOG.md
├── Makefile
├── apps/
│   └── live-commerce/          # Runnable FastAPI vertical slice
├── docs/
│   ├── REQUIREMENTS.md
│   ├── HANDOFF.md
│   ├── architecture/           # Canonical copied technical docs
│   ├── decisions/              # Architecture decision records
│   ├── assets/                 # Architecture and preview images
│   └── demos/                  # Standalone interactive HTML demos
├── releases/
│   ├── *.whl                   # Installable application package
│   └── previous/               # Earlier source release artifacts
└── scripts/
    ├── bootstrap.sh
    ├── run.sh
    ├── test.sh
    └── package.sh
```

## Quick start

Python 3.11 or 3.12 is recommended.

```bash
cd apps/live-commerce
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
uvicorn livecommerce.main:app --reload --host 0.0.0.0 --port 8000
```

Open:

- Host studio: `http://localhost:8000/studio`
- Viewer application: `http://localhost:8000/viewer`
- Interactive architecture: `http://localhost:8000/architecture`
- OpenAPI: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`

The default mock generation mode requires no fal credentials. For real fal queued generation, follow [`apps/live-commerce/README.md`](../apps/live-commerce/README.md).

## Current development baseline

The v0.1 implementation includes:

- Live-session lifecycle and guarded state transitions.
- Ordered room events, snapshot recovery, replay, and WebSocket fanout.
- Chat, polling, deterministic one-vote-per-user counts, and product pinning.
- Catalog, cart, atomic inventory deduction, and idempotent mock checkout.
- AI segment lifecycle with moderation, deadlines, fallback, QA, and explicit on-air control.
- fal queued-submission boundary, typed H3 Max text-to-video arguments, webhook verification, and duplicate-delivery handling.
- Host studio, viewer app, interactive architecture, tests, Docker packaging, and OpenAPI documentation.

The next priority is **Increment 0.2: real fal staging integration**, followed by durable state/event infrastructure and a real media plane.

## Core architectural rule

fal is the AI inference and generation layer. It is **not** the one-to-many livestream CDN, the product database, the inventory authority, or the payment system. Viewer playback and checkout must continue through an AI outage.
