
(() => {
  'use strict';

  const STAGE_WIDTH = 1760;
  const STAGE_HEIGHT = 1110;
  const stage = document.getElementById('diagramStage');
  const sizer = document.getElementById('stageSizer');
  const viewport = document.getElementById('viewport');
  const svg = document.getElementById('connections');
  const detailPane = document.getElementById('detailsPane');
  const overviewContent = document.getElementById('overviewContent');
  const nodeContent = document.getElementById('nodeContent');
  const sidePanel = document.getElementById('sidePanel');
  const logList = document.getElementById('logList');
  const activityCount = document.getElementById('activityCount');
  const toastStack = document.getElementById('toastStack');

  let zoom = 0.78;
  let activeFilter = 'all';
  let selectedNode = null;
  let hoverNode = null;
  let falOutage = false;
  let runningFlow = false;
  let logCount = 0;

  const connections = [
    { id:'host-edge', from:'host-studio', to:'edge-lb', type:'secure', label:'control plane' },
    { id:'host-media', from:'host-studio', to:'delivery-webrtc', type:'media', label:'live ingest' },
    { id:'viewer-edge', from:'viewer-apps', to:'edge-lb', type:'secure', label:'API + room token' },
    { id:'admin-api', from:'admin-console', to:'api-gateway', type:'secure', label:'operator commands' },
    { id:'edge-api', from:'edge-lb', to:'api-gateway', type:'sync', label:'routed request' },
    { id:'edge-rt', from:'edge-lb', to:'realtime-gateway', type:'sync' },
    { id:'ingest-abr', from:'delivery-webrtc', to:'delivery-hls', type:'media', label:'compose + encode' },
    { id:'abr-cdn', from:'delivery-hls', to:'edge-cdn', type:'media' },
    { id:'cdn-viewers', from:'edge-cdn', to:'global-viewers', type:'media', label:'one-to-many playback' },
    { id:'viewers-rt', from:'global-viewers', to:'realtime-gateway', type:'async', label:'chat / votes' },
    { id:'api-room', from:'api-gateway', to:'live-room', type:'sync' },
    { id:'api-commerce', from:'api-gateway', to:'commerce', type:'sync' },
    { id:'api-identity', from:'api-gateway', to:'identity', type:'secure' },
    { id:'rt-chat', from:'realtime-gateway', to:'chat', type:'async' },
    { id:'rt-engagement', from:'realtime-gateway', to:'engagement', type:'async' },
    { id:'rt-room', from:'realtime-gateway', to:'live-room', type:'async' },
    { id:'chat-bus', from:'chat', to:'event-bus', type:'async' },
    { id:'engagement-bus', from:'engagement', to:'event-bus', type:'async' },
    { id:'room-bus', from:'live-room', to:'event-bus', type:'async' },
    { id:'commerce-bus', from:'commerce', to:'event-bus', type:'async' },
    { id:'bus-notify', from:'event-bus', to:'notification', type:'async' },
    { id:'room-fal', from:'live-room', to:'fal-request', type:'async', label:'scene plan' },
    { id:'fal-1', from:'fal-request', to:'fal-queue', type:'async' },
    { id:'fal-2', from:'fal-queue', to:'fal-inference', type:'async' },
    { id:'fal-3', from:'fal-inference', to:'fal-webhook', type:'async' },
    { id:'fal-4', from:'fal-webhook', to:'fal-processing', type:'async' },
    { id:'fal-5', from:'fal-processing', to:'fal-media', type:'sync' },
    { id:'fal-air', from:'fal-media', to:'delivery-hls', type:'media', label:'approved segment' },
    { id:'fal-storage', from:'fal-processing', to:'object-storage', type:'sync' },
    { id:'commerce-pay', from:'commerce', to:'payments', type:'secure' },
    { id:'commerce-ship', from:'commerce', to:'shipping', type:'async' },
    { id:'notify-email', from:'notification', to:'email', type:'async' },
    { id:'notify-push', from:'notification', to:'push', type:'async' },
    { id:'bus-analytics', from:'event-bus', to:'analytics', type:'async' },
    { id:'commerce-pg', from:'commerce', to:'postgres', type:'sync' },
    { id:'room-redis', from:'live-room', to:'redis', type:'sync' },
    { id:'chat-redis', from:'chat', to:'redis', type:'sync' },
    { id:'analytics-warehouse', from:'analytics', to:'warehouse', type:'async' },
    { id:'backend-monitor', from:'event-bus', to:'monitoring', type:'async' },
    { id:'fal-trace', from:'fal-webhook', to:'tracing', type:'async' },
    { id:'fallback-edge', from:'live-room', to:'delivery-hls', type:'fallback', label:'host / approved fallback' }
  ];

  const nodeDetails = {
    'host-studio': {
      title:'Host / Seller Studio', layer:'Clients', summary:'The producer-facing control surface for live capture, show rundown, product pins, audience controls, AI preview and emergency takeover.',
      responsibilities:['Capture camera and microphone with device checks','Control live-room lifecycle and scene rundown','Approve or reject generated segments before broadcast','Provide immediate cut-to-host, slate and fallback controls'],
      interfaces:['WebRTC, SRT or RTMP media ingest','REST commands for session and commerce state','WebSocket events for room health and audience feedback'],
      tech:['React','WebRTC','SRT/RTMP','WebCodecs','OIDC'], slo:'Control actions acknowledged at p95 < 250 ms; standby ingest available for priority shows.', risk:'If the studio disconnects, keep the existing program on air and allow a secondary producer or fallback playlist to take control.'
    },
    'viewer-apps': {
      title:'Viewer Applications', layer:'Clients', summary:'Web and mobile clients that combine adaptive live playback with chat, polls, product discovery, cart and checkout.',
      responsibilities:['Start playback quickly and adapt bitrate','Synchronize product pins to media program time','Recover room state after reconnect','Keep checkout usable even when AI or chat is degraded'],
      interfaces:['LL-HLS / DASH playback','REST commerce APIs','Regional WebSocket gateway'],
      tech:['React / React Native','Native AV players','WebSocket','Service workers'], slo:'Viewer join p95 < 2 s; rebuffer ratio < 1%; product pin alignment within ±300 ms.', risk:'Never couple checkout availability to the realtime connection; cache a safe room snapshot and independently retry commerce requests.'
    },
    'admin-console': {
      title:'Admin & Moderator Console', layer:'Clients', summary:'A privileged operations surface for content safety, products, users, orders, incident response and AI output approval.',
      responsibilities:['Review prompts and generated media','Manage bans, rate limits and policy escalations','Inspect order and inventory incidents','Operate emergency cut and platform degradation controls'],
      interfaces:['Privileged REST APIs','Audit event stream','Media preview URLs'], tech:['React','RBAC/ABAC','Immutable audit log'], slo:'All privileged actions are attributable, authorized and durably audited.', risk:'Apply least privilege, device-aware authentication and dual approval for high-impact controls.'
    },
    'edge-cdn': {
      title:'CDN', layer:'Edge & Delivery', summary:'Caches static assets and distributes the packaged live program to a global audience without multiplying AI inference sessions.',
      responsibilities:['Deliver adaptive media segments close to viewers','Absorb traffic spikes','Protect the media origin','Expose playback telemetry'], interfaces:['LL-HLS / DASH','Signed playback URLs','Origin shield'], tech:['Managed CDN','Multi-CDN steering','Origin shield'], slo:'Playback availability 99.95% or better with regional failover.', risk:'Keep at least one alternate playback domain or provider for major commercial events.'
    },
    'edge-security': {
      title:'WAF & DDoS Protection', layer:'Edge & Delivery', summary:'Filters abusive traffic before it reaches application, realtime and commerce services.', responsibilities:['Rate-limit abusive clients','Block common application exploits','Protect login, voting and checkout endpoints','Feed abuse intelligence to trust systems'], interfaces:['HTTP edge policies','Bot signals','Security event stream'], tech:['WAF','DDoS protection','Bot management'], slo:'Mitigation must not materially increase p95 API latency.', risk:'Overly broad rules can block legitimate flash-sale traffic; rehearse expected peak patterns.'
    },
    'edge-lb': {
      title:'Global Load Balancer', layer:'Edge & Delivery', summary:'Routes API and realtime traffic to the healthiest nearby region while preserving room affinity where needed.', responsibilities:['Health-based regional routing','TLS-aware traffic policies','Failover and traffic shifting','WebSocket-compatible affinity'], interfaces:['HTTPS','WSS','Health probes'], tech:['Anycast DNS / global LB','Regional ingress'], slo:'Regional failover within the defined recovery objective without reconnect storms.', risk:'Room state and replay must be recoverable in the destination region before aggressive failover.'
    },
    'edge-tls': {
      title:'TLS Termination', layer:'Edge & Delivery', summary:'Centralizes certificates, modern transport policy and secure service ingress.', responsibilities:['Certificate issuance and rotation','Enforce modern cipher and protocol policy','Forward verified identity context','Support signed origin requests'], interfaces:['TLS 1.2+','mTLS to sensitive origins'], tech:['Managed certificates','KMS'], slo:'Zero expired certificates; automated renewal with alerting.', risk:'Do not forward spoofable identity headers from untrusted network paths.'
    },
    'delivery-webrtc': {
      title:'Interactive Media Transport', layer:'Live Streaming', summary:'Carries host ingest, guest video, preview feeds and subsecond interactive media where the latency requirement justifies it.', responsibilities:['Accept host and guest media','Provide low-latency preview','Forward sources to cloud composition','Collect packet-loss and jitter telemetry'], interfaces:['WebRTC','SRT','RTMP'], tech:['SFU','TURN','SRT gateway'], slo:'Stable ingest under realistic mobile packet loss, with a tested standby route.', risk:'Do not use one WebRTC peer per mass viewer unless the product truly requires subsecond media and the cost is accepted.'
    },
    'delivery-hls': {
      title:'Mass Playback Pipeline', layer:'Live Streaming', summary:'Composes, encodes and packages one continuous adaptive-bitrate program for efficient one-to-many delivery.', responsibilities:['Compose host, AI segments and deterministic overlays','Encode an ABR ladder','Package low-latency HLS or DASH','Maintain an uninterrupted program timeline'], interfaces:['Media ingest','Generated asset store','CDN origin'], tech:['FFmpeg / GStreamer','Cloud compositor','LL-HLS'], slo:'No unhandled broadcast gaps; audio/video sync remains stable throughout long sessions.', risk:'Operate active/standby composition for high-value shows and keep a pre-approved fallback playlist.'
    },
    'global-viewers': {
      title:'Global Viewer Population', layer:'Clients', summary:'The audience receives a shared media program over CDN while interaction events use horizontally scalable regional gateways.', responsibilities:['Consume adaptive media','Send chat, reactions and votes','Receive product and room state','Complete purchases through authoritative APIs'], interfaces:['CDN playback','WebSocket room channel','REST commerce API'], tech:['Web / iOS / Android'], slo:'Scale media egress by viewers while AI-generation capacity scales primarily by active channels.', risk:'Bot and fraud controls must distinguish high excitement from coordinated manipulation.'
    },
    'api-gateway': {
      title:'API Gateway', layer:'Core Backend', summary:'The authenticated entry point for session, catalog, cart, checkout, order and administrative APIs.', responsibilities:['Authenticate and authorize requests','Apply quotas and idempotency','Route to versioned services','Propagate correlation IDs'], interfaces:['REST / GraphQL','OIDC / JWT','Internal service RPC'], tech:['Go or TypeScript','Envoy / managed API gateway','OpenAPI'], slo:'Checkout path availability 99.99%; p95 latency budgets enforced by route.', risk:'Avoid putting business logic in the gateway; keep policies declarative and independently testable.'
    },
    'realtime-gateway': {
      title:'Realtime Gateway', layer:'Core Backend', summary:'Maintains room WebSockets, presence, ordered sequence numbers, missed-event replay and snapshot recovery.', responsibilities:['Authenticate short-lived room tokens','Fan out chat, polls, product pins and status','Track connection and presence state','Replay events or return a complete snapshot on reconnect'], interfaces:['WSS','Redis / event bus','Room service'], tech:['Go / Elixir / Node.js','Redis','NATS / Kafka'], slo:'Interaction p95 < 250 ms in the primary region; reconnect restores correct state without duplicate actions.', risk:'Shed low-value reactions before chat, product events or commerce notifications during overload.'
    },
    'live-room': {
      title:'Live Room Service', layer:'Core Backend', summary:'Owns the live-session state machine, program timeline, active product, poll, segment queue and operator controls.', responsibilities:['Transition room states safely','Publish authoritative session snapshots','Maintain program-time anchors','Initiate AI scene workflows and fallbacks'], interfaces:['REST commands','WebSocket events','Event bus','Workflow engine'], tech:['Go / TypeScript','PostgreSQL','Redis','Temporal'], slo:'State transitions are idempotent and ordered; fallback activation < 1 s.', risk:'Never use process-local memory as the only source of live-room truth in a multi-replica deployment.'
    },
    'chat': {
      title:'Chat Service', layer:'Core Backend', summary:'Processes realtime messages with abuse prevention, moderation and recoverable history.', responsibilities:['Accept and sequence messages','Apply text moderation and spam rules','Publish approved messages','Support removal and moderator actions'], interfaces:['Realtime gateway','Moderation providers','Event bus'], tech:['Streaming moderation','Redis','Search index'], slo:'Moderation and fanout remain within the room interaction latency budget.', risk:'Raw audience text must never be passed directly into the AI generation prompt.'
    },
    'engagement': {
      title:'Engagement Service', layer:'Core Backend', summary:'Handles reactions, polls, deterministic voting, questions and anti-manipulation controls.', responsibilities:['Open and close polls','Accept one valid vote per rule set','Calculate winners deterministically','Detect bots and coordinated abuse'], interfaces:['Realtime gateway','Event bus','Redis'], tech:['Redis atomic operations','Fraud rules','Event streaming'], slo:'Vote acknowledgment p95 < 250 ms; final totals reproducible from durable events.', risk:'The LLM may interpret a winning option but must never secretly select the winner.'
    },
    'commerce': {
      title:'Commerce Service', layer:'Core Backend', summary:'The system of authority for catalog, price, promotion, inventory reservation, cart, checkout, order and refund workflows.', responsibilities:['Serve versioned product facts','Reserve inventory atomically','Revalidate price and eligibility at checkout','Create orders idempotently and process refunds'], interfaces:['REST / GraphQL','Payment and shipping adapters','PostgreSQL','Event bus'], tech:['PostgreSQL','Workflow engine','Idempotency store'], slo:'Checkout availability 99.99%; zero duplicate orders and zero platform-caused oversell.', risk:'Do not let generated scripts or video pixels become authoritative for price, inventory or legal claims.'
    },
    'notification': {
      title:'Notification Service', layer:'Core Backend', summary:'Routes in-app, email, SMS, push and operational notifications through provider-independent policies.', responsibilities:['Template transactional messages','Route by locale and preference','Retry provider failures safely','Publish delivery status'], interfaces:['Event bus','Email/SMS providers','Push providers'], tech:['Queue workers','Template service'], slo:'Order confirmations are durable and idempotent even when an external provider is unavailable.', risk:'Marketing notifications and mandatory transactional messages require different consent and retry policies.'
    },
    'event-bus': {
      title:'Event Bus / Streaming Layer', layer:'Core Backend', summary:'Decouples chat, room, commerce, AI and analytics workflows through durable, versioned domain events.', responsibilities:['Persist ordered events where required','Fan out to independent consumers','Support replay and backpressure','Carry correlation and causation IDs'], interfaces:['Kafka / Redpanda / NATS JetStream','Transactional outbox'], tech:['Schema registry','Dead-letter topics','Consumer groups'], slo:'No silent event loss; consumers are idempotent and observable.', risk:'Treat event schemas as public contracts—version them and avoid leaking sensitive data.'
    },
    'fal-request': {
      title:'fal Segment Request', layer:'AI Content Generation', summary:'A structured, policy-approved scene plan containing references, product facts, deadline, fallback and cost ceiling.', responsibilities:['Compile approved model arguments','Attach continuity references','Set generation and stale deadlines','Select an allowlisted model policy'], interfaces:['Scene planner','fal orchestrator'], tech:['Typed Pydantic schemas','Policy engine'], slo:'Every request is reproducible from versioned inputs and policy metadata.', risk:'Never forward arbitrary user prompts, arbitrary model IDs or secrets from the browser.'
    },
    'fal-queue': {
      title:'fal Queue Submission', layer:'AI Content Generation', summary:'Submits longer-running generation through durable asynchronous inference and tracks the fal request ID.', responsibilities:['Submit through a server-side fal client','Store job and correlation identifiers','Apply budget and concurrency limits','Set signed webhook callback'], interfaces:['fal queue API','Workflow engine','Job store'], tech:['fal-client','Temporal'], slo:'Submission is idempotent and bounded by show-level budget and deadline.', risk:'Bound retries and stop once a scene can no longer be ready before its intended air time.'
    },
    'fal-inference': {
      title:'fal Model Inference', layer:'AI Content Generation', summary:'Executes an allowlisted text-to-video, image-to-video, audio, avatar or custom GPU workload on fal infrastructure.', responsibilities:['Run the selected model','Expose status and result metadata','Scale warm capacity for scheduled events','Support model fallback through orchestration'], interfaces:['fal Model APIs','Custom fal.App or realtime endpoint'], tech:['fal Serverless','GPU models','Realtime WebSocket / WebRTC where justified'], slo:'Model-specific generation target plus enough margin for QA before the segment deadline.', risk:'Inference latency is not complete scene-to-air latency; account for moderation, transfer, QA and composition.'
    },
    'fal-webhook': {
      title:'Signed fal Webhook', layer:'AI Content Generation', summary:'Receives completion or failure callbacks, verifies authenticity and processes retries idempotently.', responsibilities:['Verify timestamp and ED25519 signature','Hash and bind the raw request body','Deduplicate repeated delivery','Reject callbacks for unknown or stale jobs'], interfaces:['Public HTTPS webhook','fal JWKS','Workflow engine'], tech:['ED25519','Idempotency table'], slo:'Valid callbacks are acknowledged quickly and processed exactly once at the domain level.', risk:'Never trust a webhook merely because the request ID looks valid; verify the full signature construction.'
    },
    'fal-processing': {
      title:'AI Result Processing & QA', layer:'AI Content Generation', summary:'Validates generated media before it becomes eligible for broadcast.', responsibilities:['Decode and inspect duration, resolution and frame rate','Run visual, audio and product-fidelity checks','Reject black, frozen or unsafe output','Transcode and create provenance metadata'], interfaces:['Moderation models','Object storage','Segment workflow'], tech:['FFmpeg','Computer vision QA','Human approval queue'], slo:'100% of generated media passes the defined policy gates before air.', risk:'Low-confidence product or identity verification must route to a human or fallback, never silently pass.'
    },
    'fal-media': {
      title:'Approved Media', layer:'AI Content Generation', summary:'A validated asset in the rolling program buffer, with a fixed intended air time and safe fallback.', responsibilities:['Store immutable approved version','Publish segment-ready event','Insert into program scheduler','Reject late or superseded results'], interfaces:['Object storage','Program scheduler','Cloud compositor'], tech:['Signed URLs','Media manifest','Segment state machine'], slo:'At least two ready-to-air segments or a safe host/fallback path for AI-led shows.', risk:'A result that arrives after its stale time must never jump back into the live program.'
    },
    'payments': {
      title:'Payment Gateway', layer:'External Integration', summary:'Authorizes and captures payments while returning idempotent status to the commerce workflow.', responsibilities:['Tokenize payment details','Authorize and capture','Send signed webhooks','Support refunds and disputes'], interfaces:['Provider SDK/API','Signed webhook'], tech:['Stripe / Adyen / PayPal / local PSP'], slo:'Duplicate callbacks cannot create duplicate orders or captures.', risk:'Keep payment data outside application logs and follow the applicable PCI scope.'
    },
    'shipping': {
      title:'Shipping & Fulfillment', layer:'External Integration', summary:'Provides rates, labels, tracking and downstream fulfillment status.', responsibilities:['Calculate shipping options','Create labels or fulfillment requests','Track shipment events','Handle address exceptions'], interfaces:['Carrier / 3PL APIs','Event bus'], tech:['Adapter layer','Workflow retries'], slo:'A shipping-provider outage does not corrupt paid order state.', risk:'Model estimated delivery dates as external promises with explicit freshness and confidence.'
    },
    'identity': {
      title:'Identity Provider', layer:'External Integration', summary:'Authenticates viewers, merchants, hosts and operators and supplies trustworthy role claims.', responsibilities:['Login and token issuance','MFA/passkeys for privileged users','Role and organization membership','Device and risk signals'], interfaces:['OIDC / OAuth 2.1','SCIM where needed'], tech:['Auth0 / Firebase / Cognito / enterprise IdP'], slo:'Privileged access uses phishing-resistant authentication where possible.', risk:'Do not use display names or client-provided roles as authorization evidence.'
    },
    'postgres': {
      title:'PostgreSQL', layer:'Data & Storage', summary:'Transactional system of record for identity links, products, rooms, carts, orders and configuration.', responsibilities:['Enforce relational constraints','Support atomic inventory and checkout operations','Back the transactional outbox','Maintain audit-friendly history'], interfaces:['SQL','Change data capture'], tech:['Managed PostgreSQL','Read replicas','PITR'], slo:'Recovery point and recovery time align with order and inventory criticality.', risk:'Use migrations, bounded queries and connection pooling; flash-sale traffic can expose lock contention.'
    },
    'redis': {
      title:'Redis', layer:'Data & Storage', summary:'Low-latency ephemeral and replay state for room presence, votes, rate limits, leaderboards and short event windows.', responsibilities:['Store presence and heartbeats','Support atomic counters and deduplication','Cache room snapshots','Provide bounded replay windows'], interfaces:['RESP','Pub/sub or streams'], tech:['Managed Redis / Valkey'], slo:'Loss of cache does not lose authoritative orders or unrecoverable room state.', risk:'Define eviction and persistence intentionally; do not confuse fast cache state with the durable source of truth.'
    },
    'object-storage': {
      title:'Object Storage & Media CDN', layer:'Data & Storage', summary:'Stores product references, generated outputs, approved broadcast assets, recordings and thumbnails with explicit access controls.', responsibilities:['Private reference storage','Lifecycle and retention policies','Signed access URLs','Replication and integrity checks'], interfaces:['S3-compatible API','CDN origin'], tech:['Object storage','KMS encryption','Signed URLs'], slo:'Approved program assets remain available for the show duration and replay obligations.', risk:'Generated provider URLs may have different retention or ACL behavior; copy approved assets into controlled storage.'
    },
    'warehouse': {
      title:'Analytics Warehouse', layer:'Data & Storage', summary:'Combines media, interaction, AI cost and commerce events for funnels, attribution, experiments and operations.', responsibilities:['Ingest versioned events','Compute GMV and conversion funnels','Attribute product pins and scenes','Track cost per generated second and live minute'], interfaces:['Batch / streaming ingestion','BI tools'], tech:['ClickHouse / BigQuery / Snowflake'], slo:'Business metrics are reproducible from governed event definitions.', risk:'Do not expose raw personal data broadly; use purpose-limited models and retention.'
    },
    'monitoring': {
      title:'Monitoring & SLOs', layer:'Observability', summary:'Measures media, interaction, AI, commerce and infrastructure health through actionable service-level indicators.', responsibilities:['Track latency, availability and saturation','Measure buffer depth and deadline misses','Alert on checkout and playback impact','Drive capacity and cost tuning'], interfaces:['Prometheus-compatible metrics','Dashboards'], tech:['Prometheus','Grafana','fal analytics export'], slo:'Alerts are tied to user impact rather than raw infrastructure noise.', risk:'Averages hide livestream incidents; monitor p95/p99, per-region and per-session outliers.'
    },
    'tracing': {
      title:'Distributed Tracing', layer:'Observability', summary:'Correlates viewer actions, room events, scene jobs, fal request IDs, checkout and orders across service boundaries.', responsibilities:['Propagate trace and correlation IDs','Join async event causation','Sample high-value errors and purchases','Link media and AI timelines'], interfaces:['OpenTelemetry'], tech:['OpenTelemetry','Jaeger / Tempo'], slo:'A production incident can be followed end-to-end without manual log guessing.', risk:'Redact secrets, payment details and raw private prompts from spans.'
    },
    'kubernetes': {
      title:'Application Orchestration', layer:'Cloud Infrastructure', summary:'Runs the non-fal application services, realtime gateways and workers with controlled deployment and recovery.', responsibilities:['Schedule services and workers','Expose health and readiness checks','Enforce resource boundaries','Roll out and roll back safely'], interfaces:['Container runtime','Ingress','Service mesh where justified'], tech:['Kubernetes / ECS / Cloud Run'], slo:'No single application node is required to keep a live session running.', risk:'Do not put media state or room authority solely inside a disposable pod.'
    },
    'secrets': {
      title:'Secrets & Key Management', layer:'Cloud Infrastructure', summary:'Protects fal keys, payment secrets, signing keys and database credentials with controlled rotation.', responsibilities:['Encrypt and rotate secrets','Issue workload identity','Audit access','Separate environments and tenants'], interfaces:['KMS / Vault APIs'], tech:['Cloud KMS','Vault','Workload identity'], slo:'No long-lived fal key appears in browser or mobile code.', risk:'A leaked server credential can create unbounded AI spend; combine rotation with endpoint allowlists and cost caps.'
    }
  };

  const fallbackDetail = (node) => ({
    title: node.querySelector('h3')?.textContent || node.dataset.node,
    layer: node.dataset.layer || 'Architecture',
    summary: node.querySelector('p')?.textContent || 'Architecture component.',
    responsibilities: ['Provide its bounded capability through a versioned interface','Emit observable events and health signals','Fail without corrupting adjacent domains'],
    interfaces: ['Versioned API or event contract'],
    tech: ['Replaceable implementation'],
    slo: 'Define a measurable service objective before production rollout.',
    risk: 'Document failure behavior and keep a tested degradation path.'
  });

  const flows = {
    broadcast: {
      label:'Live broadcast', kind:'media',
      path:['host-studio','delivery-webrtc','delivery-hls','edge-cdn','global-viewers'],
      messages:[
        ['Host feed accepted','Camera and microphone enter the interactive ingest path.'],
        ['Program composed','Host video, approved overlays and audio are mixed into one timeline.'],
        ['Adaptive stream packaged','The encoder creates a low-latency bitrate ladder.'],
        ['CDN fanout active','One program is cached and distributed close to viewers.'],
        ['Audience playing','Viewers receive low-latency playback without one inference session each.']
      ]
    },
    ai: {
      label:'fal AI segment', kind:'ai',
      path:['live-room','fal-request','fal-queue','fal-inference','fal-webhook','fal-processing','fal-media','delivery-hls','edge-cdn','global-viewers'],
      messages:[
        ['Scene plan approved','The room selects a structured scene with a deadline and fallback.'],
        ['Request compiled','Only approved product facts, references and model arguments are included.'],
        ['Job submitted','The fal request ID is stored and the workflow waits asynchronously.'],
        ['GPU inference running','The selected allowlisted model generates the segment.'],
        ['Signed webhook received','Timestamp, body hash and ED25519 signature are verified.'],
        ['Media quality checked','Safety, duration, product fidelity and technical QA are evaluated.'],
        ['Segment ready','Approved media enters the rolling program buffer.'],
        ['Segment inserted','The compositor places the asset on the continuous program timeline.'],
        ['Media distributed','The CDN fans out the updated program.'],
        ['Viewers see segment','The audience sees the generated scene and synchronized product state.']
      ]
    },
    purchase: {
      label:'Purchase', kind:'commerce',
      path:['viewer-apps','edge-lb','api-gateway','commerce','payments','commerce','postgres','event-bus','notification','viewer-apps'],
      messages:[
        ['Buy action submitted','The viewer sends a cart or checkout request with an idempotency key.'],
        ['Request routed','The edge applies security and regional routing.'],
        ['Identity authorized','The API gateway validates the user and request policy.'],
        ['Checkout revalidated','Price, promotion, eligibility and inventory are checked authoritatively.'],
        ['Payment authorized','The provider returns an idempotent result or signed callback.'],
        ['Order workflow continues','The commerce service reconciles payment and inventory state.'],
        ['Order committed','The transactional database stores the order and outbox event atomically.'],
        ['Domain event published','Independent fulfillment, analytics and notification consumers react.'],
        ['Confirmation routed','The notification service selects in-app, email, SMS or push.'],
        ['Viewer confirmed','The application receives durable order status.']
      ]
    }
  };

  function getNode(id) { return document.querySelector(`[data-node="${id}"]`); }

  function setZoom(next, center = false) {
    const previous = zoom;
    zoom = Math.min(1.18, Math.max(.48, Math.round(next * 100) / 100));
    stage.style.transform = `scale(${zoom})`;
    sizer.style.width = `${STAGE_WIDTH * zoom}px`;
    sizer.style.height = `${STAGE_HEIGHT * zoom}px`;
    document.getElementById('zoomLabel').textContent = `${Math.round(zoom * 100)}%`;
    if (center) {
      const ratio = zoom / previous;
      viewport.scrollLeft = (viewport.scrollLeft + viewport.clientWidth / 2) * ratio - viewport.clientWidth / 2;
      viewport.scrollTop = (viewport.scrollTop + viewport.clientHeight / 2) * ratio - viewport.clientHeight / 2;
    }
    requestAnimationFrame(drawConnections);
  }

  function fitStage() {
    const available = Math.max(320, viewport.clientWidth - 28);
    const next = Math.min(.96, available / STAGE_WIDTH);
    setZoom(next);
    viewport.scrollTo({ left: 0, top: 0, behavior:'smooth' });
  }

  function anchor(el, towardEl) {
    const stageRect = stage.getBoundingClientRect();
    const a = el.getBoundingClientRect();
    const b = towardEl.getBoundingClientRect();
    const ax = (a.left - stageRect.left) / zoom;
    const ay = (a.top - stageRect.top) / zoom;
    const aw = a.width / zoom;
    const ah = a.height / zoom;
    const bx = (b.left - stageRect.left) / zoom + (b.width / zoom) / 2;
    const by = (b.top - stageRect.top) / zoom + (b.height / zoom) / 2;
    const acx = ax + aw / 2;
    const acy = ay + ah / 2;
    const dx = bx - acx;
    const dy = by - acy;
    if (Math.abs(dx) > Math.abs(dy) * .72) {
      return dx >= 0 ? { x: ax + aw, y: acy, side:'right' } : { x: ax, y: acy, side:'left' };
    }
    return dy >= 0 ? { x: acx, y: ay + ah, side:'bottom' } : { x: acx, y: ay, side:'top' };
  }

  function makePath(start, end) {
    const horizontal = start.side === 'left' || start.side === 'right';
    if (horizontal) {
      const bend = Math.max(36, Math.abs(end.x - start.x) * .48);
      const c1x = start.x + (start.side === 'right' ? bend : -bend);
      const c2x = end.x + (end.side === 'left' ? -bend : bend);
      return `M ${start.x} ${start.y} C ${c1x} ${start.y}, ${c2x} ${end.y}, ${end.x} ${end.y}`;
    }
    const bend = Math.max(30, Math.abs(end.y - start.y) * .48);
    const c1y = start.y + (start.side === 'bottom' ? bend : -bend);
    const c2y = end.y + (end.side === 'top' ? -bend : bend);
    return `M ${start.x} ${start.y} C ${start.x} ${c1y}, ${end.x} ${c2y}, ${end.x} ${end.y}`;
  }

  function drawConnections() {
    svg.querySelectorAll('.dynamic').forEach(el => el.remove());
    connections.forEach(conn => {
      const from = getNode(conn.from);
      const to = getNode(conn.to);
      if (!from || !to) return;
      const start = anchor(from, to);
      const end = anchor(to, from);
      const d = makePath(start, end);
      const path = document.createElementNS('http://www.w3.org/2000/svg','path');
      path.setAttribute('id', conn.id);
      path.setAttribute('d', d);
      path.setAttribute('class', `dynamic connection ${conn.type || 'sync'} ${conn.type === 'fallback' && falOutage ? 'visible' : ''}`);
      const marker = conn.type === 'media' ? 'arrow-media' : conn.type === 'secure' ? 'arrow-secure' : conn.type === 'fallback' ? 'arrow-fallback' : 'arrow-sync';
      path.setAttribute('marker-end', `url(#${marker})`);
      path.dataset.from = conn.from;
      path.dataset.to = conn.to;
      svg.appendChild(path);
      if (conn.label) {
        const text = document.createElementNS('http://www.w3.org/2000/svg','text');
        text.setAttribute('class','dynamic connection-label');
        const textPath = document.createElementNS('http://www.w3.org/2000/svg','textPath');
        textPath.setAttribute('href', `#${conn.id}`);
        textPath.setAttribute('startOffset','50%');
        textPath.setAttribute('text-anchor','middle');
        textPath.textContent = conn.label;
        text.appendChild(textPath);
        svg.appendChild(text);
      }
    });
    refreshGraphState();
  }

  function neighborsOf(id) {
    const set = new Set([id]);
    connections.forEach(c => {
      if (c.from === id) set.add(c.to);
      if (c.to === id) set.add(c.from);
    });
    return set;
  }

  function refreshGraphState() {
    const focus = hoverNode || selectedNode;
    const neighborhood = focus ? neighborsOf(focus) : null;
    const query = document.getElementById('searchInput').value.trim().toLowerCase();
    let hits = 0;

    document.querySelectorAll('.node').forEach(node => {
      const layerVisible = activeFilter === 'all' || node.dataset.layer === activeFilter;
      const detail = nodeDetails[node.dataset.node] || fallbackDetail(node);
      const haystack = `${detail.title} ${detail.summary} ${detail.layer} ${(detail.tech || []).join(' ')}`.toLowerCase();
      const searchHit = !!query && haystack.includes(query);
      if (searchHit) hits++;
      const graphVisible = !neighborhood || neighborhood.has(node.dataset.node);
      node.classList.toggle('selected', node.dataset.node === selectedNode);
      node.classList.toggle('neighbor', !!focus && neighborhood.has(node.dataset.node) && node.dataset.node !== focus);
      node.classList.toggle('search-hit', searchHit);
      node.classList.toggle('dimmed', !layerVisible || (!!focus && !graphVisible) || (!!query && !searchHit));
    });

    document.querySelectorAll('.panel').forEach(panel => {
      const visible = activeFilter === 'all' || panel.dataset.layer === activeFilter || panel.querySelector(`.node[data-layer="${activeFilter}"]`);
      panel.classList.toggle('dimmed', !visible);
    });

    document.querySelectorAll('.connection').forEach(path => {
      const from = path.dataset.from;
      const to = path.dataset.to;
      const connected = !!focus && (from === focus || to === focus);
      const filterVisible = activeFilter === 'all' || getNode(from)?.dataset.layer === activeFilter || getNode(to)?.dataset.layer === activeFilter;
      path.classList.toggle('highlight', connected);
      path.classList.toggle('dimmed', !filterVisible || (!!focus && !connected));
    });

    document.getElementById('searchCount').textContent = query ? `${hits}` : '';
  }

  function selectNode(id) {
    selectedNode = id;
    const node = getNode(id);
    const d = nodeDetails[id] || fallbackDetail(node);
    overviewContent.hidden = true;
    nodeContent.hidden = false;
    nodeContent.innerHTML = `
      <div class="inspector-kicker">
        <span class="layer-pill">${escapeHtml(d.layer)}</span>
        <span class="node-status"><span class="status-dot ${node.classList.contains('status-degraded') ? 'degraded' : ''}"></span>${node.classList.contains('status-degraded') ? 'Degraded' : 'Healthy'}</span>
      </div>
      <h2>${escapeHtml(d.title)}</h2>
      <p class="inspector-summary">${escapeHtml(d.summary)}</p>
      <div class="detail-section"><h4>Responsibilities</h4><ul>${d.responsibilities.map(x => `<li>${escapeHtml(x)}</li>`).join('')}</ul></div>
      <div class="detail-section"><h4>Interfaces</h4><div class="tag-list">${d.interfaces.map(x => `<span class="tag">${escapeHtml(x)}</span>`).join('')}</div></div>
      <div class="detail-section"><h4>Suggested technology</h4><div class="tag-list">${d.tech.map(x => `<span class="tag">${escapeHtml(x)}</span>`).join('')}</div></div>
      <div class="detail-section"><h4>Service objective</h4><div class="slo-card">${escapeHtml(d.slo)}</div></div>
      <div class="detail-section"><h4>Failure & degradation</h4><div class="risk-card">${escapeHtml(d.risk)}</div></div>
    `;
    switchTab('details');
    refreshGraphState();
    if (window.innerWidth <= 1050) sidePanel.classList.add('open');
  }

  function clearSelection() {
    selectedNode = null;
    overviewContent.hidden = false;
    nodeContent.hidden = true;
    refreshGraphState();
  }

  function switchTab(tab) {
    document.querySelectorAll('.side-tab').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
    document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
    document.getElementById(tab === 'details' ? 'detailsPane' : 'activityPane').classList.add('active');
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  }

  function nowTime() {
    return new Date().toLocaleTimeString([], {hour:'2-digit', minute:'2-digit', second:'2-digit'});
  }

  function addLog(title, message, kind='system') {
    logCount++;
    activityCount.textContent = `(${logCount})`;
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    entry.innerHTML = `<span class="log-time">${nowTime()}</span><span class="log-dot ${kind}"></span><span class="log-message"><strong>${escapeHtml(title)}</strong>${escapeHtml(message)}</span>`;
    logList.prepend(entry);
    while (logList.children.length > 80) logList.lastElementChild.remove();
  }

  function toast(message, kind='') {
    const el = document.createElement('div');
    el.className = `toast ${kind}`;
    el.textContent = message;
    toastStack.appendChild(el);
    setTimeout(() => { el.style.opacity = '0'; el.style.transform = 'translateY(8px)'; }, 2800);
    setTimeout(() => el.remove(), 3200);
  }

  function findConnection(a,b) {
    return connections.find(c => (c.from === a && c.to === b) || (c.from === b && c.to === a));
  }

  function animateDot(connectionId, kind='system') {
    const path = document.getElementById(connectionId);
    if (!path) return;
    const circle = document.createElementNS('http://www.w3.org/2000/svg','circle');
    circle.setAttribute('r','6');
    circle.setAttribute('class','flow-dot dynamic');
    circle.setAttribute('fill', kind === 'ai' ? '#ea6a14' : kind === 'commerce' ? '#17864c' : kind === 'media' ? '#7c3aed' : '#1769d2');
    const motion = document.createElementNS('http://www.w3.org/2000/svg','animateMotion');
    motion.setAttribute('dur','.62s');
    motion.setAttribute('fill','freeze');
    const mpath = document.createElementNS('http://www.w3.org/2000/svg','mpath');
    mpath.setAttribute('href',`#${connectionId}`);
    motion.appendChild(mpath);
    circle.appendChild(motion);
    svg.appendChild(circle);
    motion.beginElement();
    setTimeout(() => circle.remove(), 720);
  }

  const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

  async function runFlow(name) {
    if (runningFlow) { toast('A demonstration is already running.'); return; }
    const flow = flows[name];
    if (!flow) return;
    if (name === 'ai' && falOutage) {
      await runOutageFallback();
      return;
    }
    runningFlow = true;
    switchTab('activity');
    addLog(`${flow.label} started`, 'Following the highlighted components and connectors.', flow.kind);
    toast(`${flow.label} demonstration started`);

    for (let i = 0; i < flow.path.length; i++) {
      const id = flow.path[i];
      const node = getNode(id);
      if (node) {
        node.classList.add('flow-active');
        node.scrollIntoView({behavior:'smooth', block:'center', inline:'center'});
      }
      const msg = flow.messages[i] || [id, ''];
      addLog(msg[0], msg[1], flow.kind);
      if (i > 0) {
        const c = findConnection(flow.path[i-1], id);
        const p = c && document.getElementById(c.id);
        if (p) {
          p.classList.add('flow-active');
          animateDot(c.id, flow.kind);
          await sleep(640);
          p.classList.remove('flow-active');
        } else {
          await sleep(480);
        }
      } else {
        await sleep(430);
      }
      node?.classList.remove('flow-active');
    }
    addLog(`${flow.label} complete`, 'The end-to-end path completed without coupling unrelated failure domains.', flow.kind);
    toast(`${flow.label} flow complete`, 'success');
    runningFlow = false;
  }

  async function runOutageFallback() {
    if (runningFlow) return;
    runningFlow = true;
    switchTab('activity');
    addLog('AI segment requested', 'The room attempts to prepare the next generated segment.', 'ai');
    getNode('live-room')?.classList.add('flow-active');
    await sleep(450);
    getNode('live-room')?.classList.remove('flow-active');
    getNode('fal-request')?.classList.add('flow-active');
    addLog('Circuit breaker open', 'fal generation is unavailable; the request is not retried past the scene deadline.', 'error');
    await sleep(650);
    getNode('fal-request')?.classList.remove('flow-active');
    const fallback = document.getElementById('fallback-edge');
    fallback?.classList.add('flow-active','visible');
    animateDot('fallback-edge','error');
    getNode('delivery-hls')?.classList.add('flow-active');
    addLog('Fallback activated', 'The compositor keeps the human host or an approved clip on air. Playback and checkout remain healthy.', 'media');
    await sleep(900);
    fallback?.classList.remove('flow-active');
    getNode('delivery-hls')?.classList.remove('flow-active');
    addLog('Graceful degradation confirmed', 'AI is degraded, but the media and commerce paths continue independently.', 'commerce');
    toast('fal unavailable: host/fallback program remains on air', 'error');
    runningFlow = false;
  }

  function toggleFalOutage() {
    falOutage = !falOutage;
    document.querySelectorAll('[data-layer="ai"].node').forEach(n => n.classList.toggle('status-degraded', falOutage));
    document.getElementById('outageBtn').classList.toggle('active', falOutage);
    document.getElementById('outageBtn').textContent = falOutage ? 'Recover fal service' : 'Inject fal outage';
    document.getElementById('platformState').textContent = falOutage ? 'AI degraded' : 'Healthy';
    document.getElementById('platformDot').classList.toggle('degraded', falOutage);
    document.getElementById('bufferMetric').textContent = falOutage ? '18 s fallback' : '24 s';
    drawConnections();
    if (falOutage) {
      addLog('fal outage injected', 'AI nodes are degraded. Broadcast and commerce remain available by design.', 'error');
      toast('fal outage injected — run the AI flow to see fallback behavior', 'error');
    } else {
      addLog('fal service recovered', 'New segment generation may resume after health checks and circuit-breaker recovery.', 'ai');
      toast('fal service recovered', 'success');
    }
    if (selectedNode?.startsWith('fal-')) selectNode(selectedNode);
  }

  document.querySelectorAll('.node').forEach(node => {
    node.addEventListener('click', e => { e.stopPropagation(); selectNode(node.dataset.node); });
    node.addEventListener('mouseenter', () => { hoverNode = node.dataset.node; refreshGraphState(); });
    node.addEventListener('mouseleave', () => { hoverNode = null; refreshGraphState(); });
  });

  document.querySelectorAll('[data-flow]').forEach(btn => btn.addEventListener('click', () => runFlow(btn.dataset.flow)));
  document.querySelectorAll('.side-tab').forEach(btn => btn.addEventListener('click', () => switchTab(btn.dataset.tab)));

  document.getElementById('filterGroup').addEventListener('click', e => {
    const chip = e.target.closest('[data-filter]');
    if (!chip) return;
    activeFilter = chip.dataset.filter;
    document.querySelectorAll('[data-filter]').forEach(c => c.classList.toggle('active', c === chip));
    refreshGraphState();
  });

  document.getElementById('searchInput').addEventListener('input', refreshGraphState);
  document.getElementById('zoomIn').addEventListener('click', () => setZoom(zoom + .08, true));
  document.getElementById('zoomOut').addEventListener('click', () => setZoom(zoom - .08, true));
  document.getElementById('fitBtn').addEventListener('click', fitStage);
  document.getElementById('outageBtn').addEventListener('click', toggleFalOutage);
  document.getElementById('themeBtn').addEventListener('click', () => {
    const html = document.documentElement;
    html.dataset.theme = html.dataset.theme === 'dark' ? 'light' : 'dark';
    localStorage.setItem('architecture-theme', html.dataset.theme);
    setTimeout(drawConnections, 30);
  });
  document.getElementById('fullscreenBtn').addEventListener('click', async () => {
    try {
      if (!document.fullscreenElement) await document.documentElement.requestFullscreen();
      else await document.exitFullscreen();
    } catch (_) { toast('Fullscreen is unavailable in this browser.'); }
  });
  document.getElementById('mobileSideBtn').addEventListener('click', () => sidePanel.classList.toggle('open'));
  document.getElementById('clearLogBtn').addEventListener('click', () => { logList.innerHTML=''; logCount=0; activityCount.textContent=''; });

  stage.addEventListener('click', e => {
    if (!e.target.closest('.node')) clearSelection();
  });

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
      clearSelection();
      sidePanel.classList.remove('open');
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      document.getElementById('searchInput').focus();
    }
  });

  window.addEventListener('resize', () => { drawConnections(); if (window.innerWidth > 1050) sidePanel.classList.remove('open'); });
  window.addEventListener('load', () => {
    const savedTheme = localStorage.getItem('architecture-theme');
    if (savedTheme) document.documentElement.dataset.theme = savedTheme;
    setZoom(zoom);
    drawConnections();
    setTimeout(() => { if (viewport.clientWidth < 1420) fitStage(); }, 70);
    addLog('Architecture loaded', 'Select any component or run an end-to-end demonstration.', 'system');
  });
})();
