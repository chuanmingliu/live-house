#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DOCS="$ROOT/apps/live-commerce/docs"

for name in ARCHITECTURE.md EVENT_CONTRACTS.md IMPLEMENTATION_STATUS.md ROADMAP.md SECURITY.md openapi.json; do
  cp "$APP_DOCS/$name" "$ROOT/docs/$name"
  cp "$APP_DOCS/$name" "$ROOT/docs/architecture/$name"
done
cp "$ROOT/docs/HANDOFF.md" "$ROOT/docs/DEVELOPMENT_HANDOFF.md"
cp "$ROOT/docs/demos/interactive-live-commerce-architecture.html" "$ROOT/docs/interactive-architecture.html"
cp "$ROOT/docs/demos/interactive-live-commerce-architecture.html" "$ROOT/docs/assets/interactive-architecture-standalone.html"
echo "Project documentation aliases synchronized."
