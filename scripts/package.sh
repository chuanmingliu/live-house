#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PARENT="$(dirname "$ROOT")"
NAME="$(basename "$ROOT")"
DATE="${SOURCE_DATE:-$(date +%Y-%m-%d)}"

cd "$ROOT"
python scripts/update_manifest.py

cd "$PARENT"
ZIP="${NAME}-${DATE}.zip"
TGZ="${NAME}-${DATE}.tar.gz"
SUM="${NAME}-${DATE}.sha256"
rm -f "$ZIP" "$TGZ" "$SUM"
zip -qr "$ZIP" "$NAME" \
  -x '*/.git/*' '*/.venv/*' '*/.pytest_cache/*' '*/__pycache__/*' '*.pyc' \
     '*/build/*' '*/dist/*' '*/*.egg-info/*' '*/data/*.db*'
tar --exclude='.git' --exclude='.venv' --exclude='.pytest_cache' \
    --exclude='__pycache__' --exclude='*.pyc' --exclude='build' --exclude='dist' --exclude='*.egg-info' \
    --exclude='data/*.db*' -czf "$TGZ" "$NAME"
sha256sum "$ZIP" "$TGZ" > "$SUM"
cat "$SUM"
