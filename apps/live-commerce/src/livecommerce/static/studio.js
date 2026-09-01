import { api, createElement, formatClock, money, queryParam, randomId, wsUrl } from "/static/common.js";

const dom = {
  bootstrapButton: document.querySelector("#bootstrapButton"),
  startButton: document.querySelector("#startButton"),
  endButton: document.querySelector("#endButton"),
  attachButton: document.querySelector("#attachButton"),
  sessionInput: document.querySelector("#sessionInput"),
  viewerLink: document.querySelector("#viewerLink"),
  statusLine: document.querySelector("#statusLine"),
  connectionBadge: document.querySelector("#connectionBadge"),
  sessionBadge: document.querySelector("#sessionBadge"),
  sessionState: document.querySelector("#sessionState"),
  programVideo: document.querySelector("#programVideo"),
  liveChip: document.querySelector("#liveChip"),
  programClock: document.querySelector("#programClock"),
  productList: document.querySelector("#productList"),
  unpinButton: document.querySelector("#unpinButton"),
  promptInput: document.querySelector("#promptInput"),
  generateButton: document.querySelector("#generateButton"),
  segmentStatus: document.querySelector("#segmentStatus"),
  segmentList: document.querySelector("#segmentList"),
  pollQuestion: document.querySelector("#pollQuestion"),
  pollOptionA: document.querySelector("#pollOptionA"),
  pollOptionB: document.querySelector("#pollOptionB"),
  pollButton: document.querySelector("#pollButton"),
  eventLog: document.querySelector("#eventLog"),
  sequenceValue: document.querySelector("#sequenceValue"),
};

const state = {
  sessionId: null,
  session: null,
  products: [],
  segments: [],
  socket: null,
  lastSequence: 0,
  producerId: localStorage.getItem("fal-live-producer-id") || randomId("producer"),
  basePlaybackUrl: "/static/demo-program.mp4",
};
localStorage.setItem("fal-live-producer-id", state.producerId);

function status(message, kind = "") {
  dom.statusLine.textContent = message;
  dom.statusLine.className = `status-line small ${kind}`;
}
function segmentStatus(message, kind = "") {
  dom.segmentStatus.textContent = message;
  dom.segmentStatus.className = `status-line small ${kind}`;
}
function currentProgramTime() {
  if (!state.session?.program_started_at) return 0;
  return Math.max(0, Date.now() - Date.parse(state.session.program_started_at));
}

function renderSession() {
  const session = state.session;
  if (!session) return;
  dom.sessionBadge.textContent = session.id;
  dom.sessionState.textContent = `${session.title} · ${session.state}`;
  dom.liveChip.textContent = session.state === "LIVE" ? "LIVE" : session.state;
  dom.liveChip.classList.toggle("live", session.state === "LIVE");
  dom.startButton.disabled = session.state === "LIVE" || session.state === "ENDED";
  dom.endButton.disabled = session.state !== "LIVE" && session.state !== "DEGRADED";
  dom.generateButton.disabled = session.state === "ENDED";
  dom.pollButton.disabled = session.state !== "LIVE";
  dom.unpinButton.disabled = !session.pinned_sku;
  state.basePlaybackUrl = session.playback_url || "/static/demo-program.mp4";
  if (!dom.programVideo.src.endsWith(state.basePlaybackUrl)) {
    dom.programVideo.src = state.basePlaybackUrl;
    dom.programVideo.play().catch(() => {});
  }
  dom.viewerLink.href = `/viewer?session_id=${encodeURIComponent(session.id)}`;
  dom.viewerLink.hidden = false;
}

function renderProducts() {
  dom.productList.replaceChildren();
  for (const product of state.products) {
    const card = createElement("div", { className: "product-card" });
    const image = createElement("img", { attrs: { src: product.image_url || "", alt: product.title } });
    const info = createElement("div");
    info.append(
      createElement("strong", { text: product.title }),
      createElement("p", { text: `${money(product.price_minor, product.currency)} · ${product.inventory} available` }),
    );
    const button = createElement("button", {
      className: state.session?.pinned_sku === product.sku ? "success" : "secondary",
      text: state.session?.pinned_sku === product.sku ? "Pinned" : "Pin",
    });
    button.disabled = !state.sessionId || state.session?.state === "ENDED";
    button.addEventListener("click", () => pinProduct(product.sku));
    card.append(image, info, button);
    dom.productList.append(card);
  }
}

function renderSegments() {
  dom.segmentList.replaceChildren();
  for (const segment of state.segments) {
    const card = createElement("article", { className: "segment-card" });
    const header = createElement("div", { className: "toolbar" });
    header.append(
      createElement("strong", { text: segment.id }),
      createElement("span", { className: `badge ${segment.state === "READY" ? "ready" : ""}`, text: segment.state }),
    );
    card.append(
      header,
      createElement("p", { text: segment.prompt }),
      createElement("div", { className: "small muted mono", text: segment.fal_request_id || "not submitted" }),
    );
    if (segment.asset_url) {
      const preview = createElement("video", { attrs: { src: segment.asset_url, muted: "", controls: "", playsinline: "" } });
      card.append(preview);
    }
    if (segment.state === "READY") {
      const air = createElement("button", { className: "success", text: "Put on air now" });
      air.addEventListener("click", () => airSegment(segment.id));
      card.append(air);
    }
    dom.segmentList.append(card);
  }
}

function addEvent(event) {
  if (Number.isFinite(event.sequence)) {
    state.lastSequence = Math.max(state.lastSequence, event.sequence);
    dom.sequenceValue.textContent = String(state.lastSequence);
  }
  const line = createElement("div", { className: "event-line" });
  line.append(
    createElement("strong", { text: event.type }),
    document.createTextNode(` · #${event.sequence ?? "-"}`),
  );
  dom.eventLog.prepend(line);
  while (dom.eventLog.children.length > 80) dom.eventLog.lastElementChild.remove();
}

function handleEvent(event) {
  addEvent(event);
  const payload = event.payload || {};
  switch (event.type) {
    case "live.session.started":
    case "live.session.ended":
      state.session = payload.session;
      renderSession();
      renderProducts();
      break;
    case "product.pinned":
      state.session.pinned_sku = payload.product.sku;
      renderSession();
      renderProducts();
      break;
    case "product.unpinned":
      state.session.pinned_sku = null;
      renderSession();
      renderProducts();
      break;
    case "inventory.updated":
      state.products = state.products.map((item) => item.sku === payload.product.sku ? payload.product : item);
      renderProducts();
      break;
    case "scene.plan.created":
      upsertSegment(payload.segment);
      break;
    case "segment.ready":
    case "fal.job.failed":
      if (payload.segment) upsertSegment(payload.segment);
      else refreshSegments();
      break;
    case "segment.on_air":
      upsertSegment(payload.segment);
      previewOnAir(payload.segment);
      break;
    case "segment.fallback_activated":
      segmentStatus(`Fallback activated: ${payload.reason}`, "error");
      refreshSegments();
      break;
  }
}

function upsertSegment(segment) {
  const index = state.segments.findIndex((item) => item.id === segment.id);
  if (index >= 0) state.segments[index] = segment;
  else state.segments.unshift(segment);
  renderSegments();
}

function applySnapshot(snapshot) {
  state.session = snapshot.session;
  state.products = snapshot.products || [];
  state.segments = snapshot.segments || [];
  state.lastSequence = snapshot.last_sequence || 0;
  dom.sequenceValue.textContent = String(state.lastSequence);
  renderSession();
  renderProducts();
  renderSegments();
  for (const event of snapshot.replay || []) addEvent(event);
}

function connectSocket() {
  if (!state.sessionId) return;
  if (state.socket) state.socket.close();
  const socket = new WebSocket(wsUrl(state.sessionId, state.producerId, "producer", state.lastSequence));
  state.socket = socket;
  dom.connectionBadge.textContent = "connecting";
  socket.onopen = () => {
    dom.connectionBadge.textContent = "connected";
    dom.connectionBadge.classList.add("ready");
  };
  socket.onmessage = (message) => {
    const event = JSON.parse(message.data);
    if (event.type === "session.snapshot") applySnapshot(event.payload);
    else handleEvent(event);
  };
  socket.onclose = () => {
    dom.connectionBadge.textContent = "disconnected";
    dom.connectionBadge.classList.remove("ready");
  };
}

async function attach(sessionId) {
  try {
    const snapshot = await api(`/v1/live-sessions/${encodeURIComponent(sessionId)}/snapshot`);
    state.sessionId = sessionId;
    dom.sessionInput.value = sessionId;
    history.replaceState(null, "", `/studio?session_id=${encodeURIComponent(sessionId)}`);
    localStorage.setItem("fal-live-session-id", sessionId);
    applySnapshot(snapshot);
    connectSocket();
    status("Attached to the live session.", "success");
  } catch (error) {
    status(error.message, "error");
  }
}

async function bootstrap() {
  dom.bootstrapButton.disabled = true;
  try {
    const result = await api("/v1/demo/bootstrap", { method: "POST" });
    await attach(result.session.id);
    status("Demo room created. Open the viewer, then start the broadcast.", "success");
  } catch (error) {
    status(error.message, "error");
  } finally {
    dom.bootstrapButton.disabled = false;
  }
}

async function transition(action) {
  if (!state.sessionId) return;
  try {
    state.session = await api(`/v1/live-sessions/${encodeURIComponent(state.sessionId)}:${action}`, { method: "POST" });
    renderSession();
    status(action === "start" ? "Broadcast started." : "Broadcast ended.", "success");
  } catch (error) {
    status(error.message, "error");
  }
}

async function pinProduct(sku) {
  try {
    const result = await api(`/v1/live-sessions/${encodeURIComponent(state.sessionId)}/products/${encodeURIComponent(sku)}:pin`, {
      method: "POST",
      body: JSON.stringify({ program_time_ms: Math.round(currentProgramTime()) }),
    });
    state.session = result.session;
    renderSession();
    renderProducts();
  } catch (error) {
    status(error.message, "error");
  }
}

async function unpinProduct() {
  try {
    const result = await api(`/v1/live-sessions/${encodeURIComponent(state.sessionId)}/products:unpin`, { method: "POST" });
    state.session = result.session;
    renderSession();
    renderProducts();
  } catch (error) {
    status(error.message, "error");
  }
}

async function openPoll() {
  try {
    await api(`/v1/live-sessions/${encodeURIComponent(state.sessionId)}/polls`, {
      method: "POST",
      body: JSON.stringify({
        question: dom.pollQuestion.value.trim(),
        options: [
          { id: "option_a", label: dom.pollOptionA.value.trim() },
          { id: "option_b", label: dom.pollOptionB.value.trim() },
        ],
      }),
    });
    status("Poll opened for viewers.", "success");
  } catch (error) {
    status(error.message, "error");
  }
}

async function generateSegment() {
  if (!state.sessionId) return;
  dom.generateButton.disabled = true;
  segmentStatus("Submitting the scene plan…");
  try {
    const selectedSku = state.session?.pinned_sku;
    const segment = await api(`/v1/live-sessions/${encodeURIComponent(state.sessionId)}/segments:generate`, {
      method: "POST",
      body: JSON.stringify({
        prompt: dom.promptInput.value.trim(),
        product_skus: selectedSku ? [selectedSku] : [],
        duration_ms: 5000,
      }),
    });
    upsertSegment(segment);
    segmentStatus(`Submitted ${segment.id}. Completion will arrive through the event pipeline.`, "success");
  } catch (error) {
    segmentStatus(error.message, "error");
  } finally {
    dom.generateButton.disabled = false;
  }
}

async function refreshSegments() {
  if (!state.sessionId) return;
  state.segments = await api(`/v1/live-sessions/${encodeURIComponent(state.sessionId)}/segments`);
  renderSegments();
}

async function airSegment(segmentId) {
  try {
    const segment = await api(`/v1/segments/${encodeURIComponent(segmentId)}:air`, {
      method: "POST",
      body: JSON.stringify({ program_time_ms: Math.round(currentProgramTime()) }),
    });
    upsertSegment(segment);
    segmentStatus(`${segment.id} is now on air.`, "success");
  } catch (error) {
    segmentStatus(error.message, "error");
  }
}

function previewOnAir(segment) {
  if (!segment?.asset_url) return;
  dom.programVideo.loop = false;
  dom.programVideo.src = segment.asset_url;
  dom.programVideo.play().catch(() => {});
  dom.programVideo.onended = () => {
    dom.programVideo.loop = true;
    dom.programVideo.src = state.basePlaybackUrl;
    dom.programVideo.play().catch(() => {});
  };
}

dom.bootstrapButton.addEventListener("click", bootstrap);
dom.attachButton.addEventListener("click", () => attach(dom.sessionInput.value.trim()));
dom.startButton.addEventListener("click", () => transition("start"));
dom.endButton.addEventListener("click", () => transition("end"));
dom.unpinButton.addEventListener("click", unpinProduct);
dom.pollButton.addEventListener("click", openPoll);
dom.generateButton.addEventListener("click", generateSegment);
setInterval(() => { dom.programClock.textContent = formatClock(currentProgramTime()); }, 250);

const initialSession = queryParam("session_id") || localStorage.getItem("fal-live-session-id");
if (initialSession) {
  dom.sessionInput.value = initialSession;
  attach(initialSession);
}
