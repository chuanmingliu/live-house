# Security notes

## Present controls

- fal API credentials are read only by the backend.
- Only the configured `FAL_MODEL_ID` can be invoked.
- Queue webhooks use raw-body ED25519 verification against fal JWKS.
- Timestamps older or newer than five minutes are rejected.
- Webhook request IDs are processed once.
- Checkout uses an idempotency key and a database transaction.
- Browser rendering uses `textContent` for chat and user-visible event content.
- Product values come from the catalog, not model output.

## Deliberate demo limitations

The host and viewer identities are not authenticated. Any caller can use producer REST endpoints. Do not expose the starter publicly without adding an identity provider, role authorization, rate limits, CSRF/origin policy, and network controls.

The minimal prompt blocklist and media URL check are architecture seams, not production moderation. A real deployment requires policy engines and human controls appropriate to the product category and jurisdiction.

## Secret handling

Use a separate API-scoped fal key for each environment. Store it in a cloud secret manager and inject it at runtime. Never commit `.env`, log the key, put it in browser JavaScript, or accept an arbitrary model ID from a client.
