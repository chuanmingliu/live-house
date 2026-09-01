export async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (options.body && !headers.has("content-type")) {
    headers.set("content-type", "application/json");
  }
  const response = await fetch(path, { ...options, headers });
  const text = await response.text();
  let payload = null;
  try {
    payload = text ? JSON.parse(text) : null;
  } catch {
    payload = text;
  }
  if (!response.ok) {
    const detail = payload?.detail || payload || `${response.status} ${response.statusText}`;
    throw new Error(String(detail));
  }
  return payload;
}

export function wsUrl(sessionId, clientId, role = "viewer", afterSequence = 0) {
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  const params = new URLSearchParams({
    client_id: clientId,
    role,
    after_sequence: String(afterSequence),
  });
  return `${protocol}//${location.host}/v1/live-sessions/${encodeURIComponent(sessionId)}/ws?${params}`;
}

export function money(minor, currency) {
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: currency || "USD",
  }).format((minor || 0) / 100);
}

export function queryParam(name) {
  return new URLSearchParams(location.search).get(name);
}

export function randomId(prefix) {
  const id = globalThis.crypto?.randomUUID?.() || Math.random().toString(16).slice(2);
  return `${prefix}_${id}`;
}

export function createElement(tag, options = {}) {
  const node = document.createElement(tag);
  if (options.className) node.className = options.className;
  if (options.text != null) node.textContent = String(options.text);
  if (options.attrs) {
    for (const [key, value] of Object.entries(options.attrs)) {
      if (value != null) node.setAttribute(key, String(value));
    }
  }
  return node;
}

export function formatClock(milliseconds) {
  const totalSeconds = Math.max(0, Math.floor(milliseconds / 1000));
  const minutes = String(Math.floor(totalSeconds / 60)).padStart(2, "0");
  const seconds = String(totalSeconds % 60).padStart(2, "0");
  return `${minutes}:${seconds}`;
}
