#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/apps/live-commerce"
if [[ -f .venv/bin/activate ]]; then
  source .venv/bin/activate
fi
pytest
