# Architecture

## Current vertical slice

```mermaid
flowchart LR
    Studio[Host Studio] --> API[FastAPI Control Plane]
    Viewer[Viewer App] --> API
    Studio <--> WS[WebSocket Room Hub]
    Viewer <--> WS
    API --> DB[(SQLite)]
    API --> Broker[Sequenced Event Broker]
    Broker --> WS
    API --> Generation[Generation Service]
    Generation --> Gateway{Generation Gateway}
    Gateway -->|default| Mock[Local Mock]
    Gateway -->|FAL_MODE=queue| Fal[fal Queue]
    Fal --> Webhook[Signed fal Webhook]
    Webhook --> Generation
    Generation --> Broker
```

The slice is deliberately a modular monolith. It proves contracts and failure behavior with low operational overhead. Service boundaries are represented by Python classes and event contracts so they can later be extracted.

## Key invariants

1. The catalog is authoritative for names, prices, inventory, and approved facts.
2. Checkout revalidates and atomically commits inventory.
3. Events are ordered by a per-session sequence, not client arrival time.
4. Product and segment events may carry `program_time_ms` for media synchronization.
5. A generated result is not broadcast merely because a provider completed it.
6. Every generated segment has a deadline and a fallback path.
7. fal credentials remain server-side.
8. Webhook signatures are checked before JSON is trusted in queue mode.
9. Repeated webhook deliveries are safe.
10. AI failure must not disable playback or checkout.

## Production target

```mermaid
flowchart TB
    subgraph Clients
      V[Viewer Web/Mobile]
      H[Host Studio]
      O[Moderator Console]
    end
    subgraph Edge
      G[API Gateway / OIDC]
      R[Regional Realtime Gateways]
      I[WebRTC/SRT Ingest]
      C[Playback CDN]
    end
    subgraph Control
      S[Live Session]
      P[Chat / Polls / Presence]
      X[Catalog / Pricing / Inventory / Checkout]
      D[AI Show Director]
      F[fal Orchestrator]
      W[Durable Segment Workflow]
    end
    subgraph Media
      Q[Generated Asset QA]
      M[Active/Standby Compositor]
      E[Encoder / Origin]
    end
    subgraph Data
      PG[(PostgreSQL)]
      REDIS[(Redis)]
      BUS[(Kafka/NATS)]
      WH[(Analytics Warehouse)]
    end

    V --> C
    V <--> R
    H --> I
    H <--> R
    O --> G
    G --> S
    G --> X
    R --> P
    S --> PG
    X --> PG
    P --> REDIS
    S --> BUS
    X --> BUS
    P --> BUS
    BUS --> D
    D --> W
    W --> F
    F --> Q
    Q --> M
    I --> M
    X --> M
    M --> E
    E --> C
    BUS --> WH
```

## Scaling cut lines

### Realtime

`RoomHub` is replaced by regional WebSocket gateways. Domain events enter a durable backbone; ephemeral reactions may use a cheaper Redis/NATS channel and periodic aggregation. Snapshot recovery remains an API concern.

### Transactions

`Store` moves to PostgreSQL. Event publication uses a transactional outbox. Cart, reservation, payment, and order workflows become explicit services as business scope grows.

### Generation

`GenerationService` moves into a durable workflow. Provider completion, QA, human approval, transcoding, cancellation, and stale-result handling become workflow activities. `GenerationGateway` remains the provider boundary.

### Media

`segment.on_air` becomes a command to the compositor scheduler. The viewer receives a continuous CDN stream; it does not switch to the generated asset directly. Viewer-side events remain tied to the program timeline.

## Security progression

- Replace demo identities with OIDC/JWT.
- Issue role- and session-scoped permissions.
- Put all producer actions behind merchant authorization.
- Use a distinct API-scoped fal key per environment.
- Restrict model IDs and generation budgets by merchant policy.
- Add replay protection, audit retention, rate limits, WAF, and bot controls.
- Treat product reference assets and unreleased products as private data.
