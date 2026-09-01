import { api, createElement, formatClock, money, queryParam, randomId, wsUrl } from "/static/common.js";

const dom = {
  sessionInput: document.querySelector("#sessionInput"),
  joinButton: document.querySelector("#joinButton"),
  statusLine: document.querySelector("#statusLine"),
  connectionBadge: document.querySelector("#connectionBadge"),
  sessionBadge: document.querySelector("#sessionBadge"),
  programVideo: document.querySelector("#programVideo"),
  liveChip: document.querySelector("#liveChip"),
  programClock: document.querySelector("#programClock"),
  productToast: document.querySelector("#productToast"),
  toastImage: document.querySelector("#toastImage"),
  toastTitle: document.querySelector("#toastTitle"),
  toastPrice: document.querySelector("#toastPrice"),
  toastInventory: document.querySelector("#toastInventory"),
  pollState: document.querySelector("#pollState"),
  pollContainer: document.querySelector("#pollContainer"),
  chatList: document.querySelector("#chatList"),
  chatForm: document.querySelector("#chatForm"),
  chatInput: document.querySelector("#chatInput"),
  featuredProduct: document.querySelector("#featuredProduct"),
  productList: document.querySelector("#productList"),
  cartBadge: document.querySelector("#cartBadge"),
  checkoutButton: document.querySelector("#checkoutButton"),
  commerceStatus: document.querySelector("#commerceStatus"),
  sequenceValue: document.querySelector("#sequenceValue"),
  viewerIdentity: document.querySelector("#viewerIdentity"),
};

const state = {
  sessionId: null,
  session: null,
  products: [],
  pinnedProduct: null,
  activePoll: null,
  socket: null,
  reconnectTimer: null,
  reconnectAttempt: 0,
  lastSequence: 0,
  viewerId: localStorage.getItem("fal-live-viewer-id") || randomId("viewer"),
  cart: null,
  basePlaybackUrl: "/static/demo-program.mp4",
  segmentPlaying: false,
};
localStorage.setItem("fal-live-viewer-id", state.viewerId);
dom.viewerIdentity.textContent = state.viewerId;

function setStatus(message, kind = "") {
  dom.statusLine.textContent = message;
  dom.statusLine.className = `status-line small ${kind}`;
}
function setCommerceStatus(message, kind = "") {
  dom.commerceStatus.textContent = message;
  dom.commerceStatus.className = `status-line small ${kind}`;
}

function currentProgramTime() {
  if (!state.session?.program_started_at) return 0;
  return Math.max(0, Date.now() - Date.parse(state.session.program_started_at));
}

function renderSession() {
  if (!state.session) return;
  dom.sessionBadge.textContent = state.session.id;
  dom.liveChip.textContent = state.session.state === "LIVE" ? "LIVE" : state.session.state;
  dom.liveChip.classList.toggle("live", state.session.state === "LIVE");
  state.basePlaybackUrl = state.session.playback_url || "/static/demo-program.mp4";
  if (!state.segmentPlaying && dom.programVideo.getAttribute("src") !== state.basePlaybackUrl) {
    dom.programVideo.src = state.basePlaybackUrl;
    dom.programVideo.play().catch(() => {});
  }
}

function renderProduct(product) {
  state.pinnedProduct = product || null;
  dom.featuredProduct.replaceChildren();
  if (!product) {
    dom.featuredProduct.textContent = "The host has not pinned a product.";
    dom.productToast.hidden = true;
    return;
  }
  const card = createElement("div", { className: "product-card" });
  const image = createElement("img", { attrs: { src: product.image_url || "", alt: product.title } });
  const info = createElement("div");
  info.append(
    createElement("strong", { text: product.title }),
    createElement("p", { text: product.description }),
    createElement("div", { className: "price", text: money(product.price_minor, product.currency) }),
    createElement("div", { className: "small muted", text: `${product.inventory} available` }),
  );
  const add = createElement("button", { text: "Add" });
  add.addEventListener("click", () => addToCart(product.sku));
  card.append(image, info, add);
  dom.featuredProduct.append(card);

  dom.toastImage.src = product.image_url || "";
  dom.toastImage.alt = product.title;
  dom.toastTitle.textContent = product.title;
  dom.toastPrice.textContent = money(product.price_minor, product.currency);
  dom.toastInventory.textContent = `${product.inventory} available`;
  dom.productToast.hidden = false;
}

function renderProducts() {
  dom.productList.replaceChildren();
  for (const product of state.products) {
    const card = createElement("div", { className: "product-card" });
    const image = createElement("img", { attrs: { src: product.image_url || "", alt: product.title } });
    const info = createElement("div");
    info.append(
      createElement("strong", { text: product.title }),
      createElement("p", { text: money(product.price_minor, product.currency) }),
      createElement("div", { className: "small muted", text: `${product.inventory} available` }),
    );
    const add = createElement("button", { className: "secondary", text: "Add" });
    add.disabled = product.inventory < 1;
    add.addEventListener("click", () => addToCart(product.sku));
    card.append(image, info, add);
    dom.productList.append(card);
  }
}

function renderPoll(poll) {
  state.activePoll = poll || null;
  dom.pollContainer.replaceChildren();
  if (!poll) {
    dom.pollState.textContent = "none";
    dom.pollContainer.textContent = "No poll is open.";
    return;
  }
  dom.pollState.textContent = poll.state;
  dom.pollContainer.append(createElement("strong", { text: poll.question }));
  for (const option of poll.options) {
    const row = createElement("div", { className: "poll-option" });
    const button = createElement("button", { className: "secondary", text: option.label });
    button.addEventListener("click", () => {
      sendSocket("vote.cast", { poll_id: poll.id, option_id: option.id });
    });
    row.append(button, createElement("span", { className: "count", text: poll.counts?.[option.id] || 0 }));
    dom.pollContainer.append(row);
  }
}

function appendChat(payload) {
  const line = createElement("div", { className: "chat-line" });
  line.append(
    createElement("strong", { text: `${payload.user_id}: ` }),
    document.createTextNode(payload.content),
  );
  dom.chatList.append(line);
  dom.chatList.scrollTop = dom.chatList.scrollHeight;
}

function applyTimedEvent(event, callback) {
  const effective = event.program_time_ms;
  if (effective == null) {
    callback();
    return;
  }
  const delay = effective - currentProgramTime();
  if (delay <= 0) callback();
  else setTimeout(callback, Math.min(delay, 60_000));
}

function handleEvent(event) {
  if (Number.isFinite(event.sequence)) {
    state.lastSequence = Math.max(state.lastSequence, event.sequence);
    dom.sequenceValue.textContent = String(state.lastSequence);
  }
  const payload = event.payload || {};
  switch (event.type) {
    case "live.session.started":
    case "live.session.ended":
      state.session = payload.session;
      renderSession();
      break;
    case "product.pinned":
      applyTimedEvent(event, () => renderProduct(payload.product));
      break;
    case "product.unpinned":
      applyTimedEvent(event, () => renderProduct(null));
      break;
    case "inventory.updated": {
      const updated = payload.product;
      state.products = state.products.map((item) => item.sku === updated.sku ? updated : item);
      if (state.pinnedProduct?.sku === updated.sku) renderProduct(updated);
      renderProducts();
      break;
    }
    case "poll.opened":
    case "poll.updated":
      renderPoll(payload.poll);
      break;
    case "chat.message.published":
      appendChat(payload);
      break;
    case "segment.on_air":
      applyTimedEvent(event, () => playSegment(payload.segment));
      break;
    case "checkout.completed":
      setCommerceStatus("Order completed. Inventory was committed atomically.", "success");
      break;
  }
}

function applySnapshot(snapshot) {
  state.session = snapshot.session;
  state.products = snapshot.products || [];
  state.lastSequence = snapshot.last_sequence || 0;
  dom.sequenceValue.textContent = String(state.lastSequence);
  renderSession();
  renderProducts();
  renderProduct(snapshot.pinned_product);
  renderPoll(snapshot.active_poll);
  for (const event of snapshot.replay || []) handleEvent(event);
}

function playSegment(segment) {
  if (!segment?.asset_url) return;
  state.segmentPlaying = true;
  dom.programVideo.loop = false;
  dom.programVideo.src = segment.asset_url;
  dom.programVideo.play().catch(() => {});
  dom.programVideo.onended = () => {
    state.segmentPlaying = false;
    dom.programVideo.loop = true;
    dom.programVideo.src = state.basePlaybackUrl;
    dom.programVideo.play().catch(() => {});
  };
}

function sendSocket(type, payload) {
  if (!state.socket || state.socket.readyState !== WebSocket.OPEN) {
    setStatus("Realtime connection is not open.", "error");
    return;
  }
  state.socket.send(JSON.stringify({ type, payload }));
}

function connectSocket() {
  if (!state.sessionId) return;
  if (state.socket) state.socket.close();
  dom.connectionBadge.textContent = "connecting";
  const socket = new WebSocket(wsUrl(state.sessionId, state.viewerId, "viewer", state.lastSequence));
  state.socket = socket;
  socket.onopen = () => {
    state.reconnectAttempt = 0;
    dom.connectionBadge.textContent = "connected";
    dom.connectionBadge.classList.add("ready");
  };
  socket.onmessage = (message) => {
    const event = JSON.parse(message.data);
    if (event.type === "session.snapshot") applySnapshot(event.payload);
    else if (event.type === "error") setStatus(event.payload?.detail || "Realtime error", "error");
    else handleEvent(event);
  };
  socket.onclose = () => {
    dom.connectionBadge.textContent = "reconnecting";
    dom.connectionBadge.classList.remove("ready");
    if (!state.sessionId) return;
    const delay = Math.min(10_000, 500 * 2 ** state.reconnectAttempt++);
    clearTimeout(state.reconnectTimer);
    state.reconnectTimer = setTimeout(connectSocket, delay);
  };
}

async function joinSession() {
  const sessionId = dom.sessionInput.value.trim();
  if (!sessionId) return setStatus("Enter a session ID.", "error");
  try {
    const snapshot = await api(`/v1/live-sessions/${encodeURIComponent(sessionId)}/snapshot`);
    state.sessionId = sessionId;
    localStorage.setItem("fal-live-session-id", sessionId);
    history.replaceState(null, "", `/viewer?session_id=${encodeURIComponent(sessionId)}`);
    applySnapshot(snapshot);
    connectSocket();
    setStatus("Joined the live room.", "success");
  } catch (error) {
    setStatus(error.message, "error");
  }
}

async function ensureCart() {
  if (state.cart) return state.cart;
  state.cart = await api("/v1/carts", {
    method: "POST",
    body: JSON.stringify({ user_id: state.viewerId }),
  });
  return state.cart;
}

async function addToCart(sku) {
  try {
    const cart = await ensureCart();
    state.cart = await api(`/v1/carts/${encodeURIComponent(cart.id)}/items`, {
      method: "POST",
      body: JSON.stringify({ sku, quantity: 1 }),
    });
    const count = state.cart.items.reduce((sum, item) => sum + item.quantity, 0);
    dom.cartBadge.textContent = `${count} item${count === 1 ? "" : "s"}`;
    dom.checkoutButton.disabled = count === 0;
    setCommerceStatus(`Cart total: ${money(state.cart.total_minor, state.cart.currency)}`, "success");
    sendSocket("product.click", { sku });
  } catch (error) {
    setCommerceStatus(error.message, "error");
  }
}

async function checkout() {
  if (!state.cart || !state.sessionId) return;
  dom.checkoutButton.disabled = true;
  try {
    const result = await api("/v1/checkout-sessions", {
      method: "POST",
      body: JSON.stringify({
        cart_id: state.cart.id,
        session_id: state.sessionId,
        idempotency_key: randomId("checkout"),
      }),
    });
    setCommerceStatus(`Checkout ${result.id} completed for ${money(result.total_minor, result.currency)}.`, "success");
    state.cart = null;
    dom.cartBadge.textContent = "0 items";
  } catch (error) {
    setCommerceStatus(error.message, "error");
    dom.checkoutButton.disabled = false;
  }
}

dom.joinButton.addEventListener("click", joinSession);
dom.sessionInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") joinSession();
});
dom.chatForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const content = dom.chatInput.value.trim();
  if (!content) return;
  sendSocket("chat.send", { content });
  dom.chatInput.value = "";
});
dom.checkoutButton.addEventListener("click", checkout);

setInterval(() => {
  dom.programClock.textContent = formatClock(currentProgramTime());
  if (state.socket?.readyState === WebSocket.OPEN) {
    state.socket.send(JSON.stringify({ type: "presence.heartbeat", payload: {} }));
  }
}, 5_000);
setInterval(() => { dom.programClock.textContent = formatClock(currentProgramTime()); }, 250);

const initialSession = queryParam("session_id") || localStorage.getItem("fal-live-session-id");
if (initialSession) {
  dom.sessionInput.value = initialSession;
  joinSession();
}
