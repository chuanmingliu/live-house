#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/apps/live-commerce"
if [[ -f .venv/bin/activate ]]; then
  source .venv/bin/activate
fi
exec uvicorn livecommerce.main:app --reload --host 0.0.0.0 --port "${PORT:-8000}"
