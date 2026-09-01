# Live House — live-commerce application

The runnable Live House vertical slice for an AI-native live-commerce platform. It implements the first production-shaped path from a host action to a viewer experience:

```text
host control
  → transactional session state
  → sequenced domain event
  → WebSocket fanout and replay
  → synchronized viewer UI
  → cart and atomic checkout

scene prompt
  → moderation seam
  → fal queue adapter or local mock
  → signed/idempotent completion webhook
  → deadline check and QA seam
  → READY segment
  → explicit ON_AIR event
```

The default mode needs no fal credentials. It generates a local demo segment after a short delay, allowing the complete state and event flow to be tested offline. Queue mode uses `fal_client.submit(...)` and a public webhook.

## Implemented in this cut

- Live-session lifecycle with guarded state transitions.
- SQLite transactions and monotonically increasing event sequences per room.
- Snapshot plus event replay after reconnect, with snapshot-before-event and sequence-order guarantees.
- WebSocket chat, heartbeat, voting, and room fanout.
- Product catalog and media-timeline product pin events.
- Cart and idempotent checkout with atomic inventory deduction.
- Segment states: `PLANNED → MODERATED → SUBMITTED → QA → READY → ON_AIR`.
- Proactive generation deadline timer and stale/late-result fallback path.
- fal queue adapter with an endpoint allowlist and a typed H3 Max text-to-video payload adapter.
- ED25519 verification of fal webhook signatures against cached JWKS.
- Idempotent webhook receipt handling.
- Host studio, viewer app, OpenAPI documentation, tests, Dockerfile, and Compose file.

## Quick start

Python 3.11 or 3.12 is recommended.

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
uvicorn livecommerce.main:app --reload --host 0.0.0.0 --port 8000
```

Open:

- Host studio: `http://localhost:8000/studio`
- Viewer: `http://localhost:8000/viewer`
- OpenAPI: `http://localhost:8000/docs`
- Interactive architecture: `http://localhost:8000/architecture`

In the studio, select **Create demo room**, open the viewer link, start the room, pin a product, open a poll, and generate a segment. In mock mode the segment becomes `READY` automatically; put it on air from the studio.

## Run tests

```bash
python -m pip install -e ".[dev]"
pytest
```

## Docker

```bash
cp .env.example .env
docker compose up --build
```

## Connect real fal queued inference

Install the optional client and configure queue mode:

```bash
python -m pip install -e ".[fal]"
```

```dotenv
APP_ENV=production
PUBLIC_BASE_URL=https://live-api.example.com
FAL_MODE=queue
FAL_KEY=your-api-scoped-key
FAL_MODEL_ID=your-approved-model-id
FAL_VERIFY_WEBHOOKS=true
```

The starter includes a typed adapter for `minimax/h3-max/text-to-video`. A five-second scene request becomes a validated payload with `768P`, `16:9`, the provider safety checker enabled, and balanced prompt expansion. The generation endpoint also accepts optional model-specific `arguments`; known adapters reject unknown fields. Other model IDs use a generic `{"prompt": "..."}` contract until a typed adapter is added.

The configured `FAL_MODEL_ID` is the model allowlist for this cut. A caller cannot select an arbitrary endpoint. The backend submits with:

```python
client = fal_client.SyncClient(key=settings.fal_key)
handle = client.submit(
    settings.fal_model_id,
    arguments=arguments,
    webhook_url=settings.webhook_url,
)
```

fal must be able to reach:

```text
POST {PUBLIC_BASE_URL}/v1/webhooks/fal
```

The webhook handler verifies these headers over the raw request body:

```text
X-Fal-Webhook-Request-Id
X-Fal-Webhook-User-Id
X-Fal-Webhook-Timestamp
X-Fal-Webhook-Signature
```

For local webhook testing, expose the service through a secure development tunnel and update `PUBLIC_BASE_URL`.

## Important boundary

This starter intentionally does **not** use fal as the one-to-many broadcast CDN. The local UI switches video sources to demonstrate the `segment.on_air` contract. The next media increment should introduce:

```text
host/WebRTC or SRT ingest
  + approved generated segments
  + deterministic product graphics
  → cloud compositor
  → encoder/origin
  → low-latency CDN playback
```

The APIs and event contracts in this repository are designed so that this media plane can be added without rewriting commerce or the AI job workflow.

## Production migrations

The starter is a single-process deployment. Before horizontal production scale, replace the implementations behind the existing seams:

| Starter implementation | Production implementation |
|---|---|
| SQLite | PostgreSQL with migrations and outbox table |
| In-process WebSocket hub | Regional gateways plus Redis/NATS/Kafka fanout |
| Background `asyncio` task | Temporal or another durable workflow engine |
| Browser media-source switching | Cloud compositor and continuous CDN stream |
| Presence stored nowhere | Redis presence with TTL |
| Minimal prompt filter | Layered text, product-claim, visual, audio, and operator moderation |
| Media URL presence check | Decode, duration, safety, fidelity, loudness, freeze, and human QA |
| Demo role query parameter | OIDC/JWT with merchant, producer, moderator, and viewer roles |
| Mock checkout | PSP integration, tax, shipping, fraud, order management, refunds |

See `docs/ARCHITECTURE.md`, `docs/EVENT_CONTRACTS.md`, and `docs/ROADMAP.md`.

## Official fal references used

- Documentation index: <https://fal.ai/docs/documentation>
- Client setup: <https://fal.ai/docs/documentation/model-apis/inference/client-setup>
- Async webhooks: <https://fal.ai/docs/documentation/model-apis/inference/webhooks>
- Realtime endpoints: <https://fal.ai/docs/documentation/development/realtime>
- World Model Accelerator: <https://fal.ai/docs/documentation/development/wma>
