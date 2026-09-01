#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="$ROOT/apps/live-commerce"
OUT="$ROOT/releases"
mkdir -p "$OUT"
if [[ -f "$APP/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$APP/.venv/bin/activate"
fi
rm -rf "$APP/build" "$APP/dist" "$APP"/src/*.egg-info
cd "$APP"
if python -c 'import build' >/dev/null 2>&1; then
  python -m build --wheel --outdir "$OUT"
else
  # Offline-safe fallback using the already installed setuptools/wheel backend.
  python -m pip wheel . --no-deps --no-build-isolation --wheel-dir "$OUT"
fi
