#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="$ROOT/apps/live-commerce"

if [[ -f "$APP/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$APP/.venv/bin/activate"
fi

cd "$ROOT"
python -m compileall -q "$APP/src"

if command -v node >/dev/null 2>&1; then
  for file in "$APP"/src/livecommerce/static/*.js; do
    node --check "$file"
  done
fi

python - <<'PY'
from __future__ import annotations

import json
import re
from pathlib import Path

root = Path.cwd()
required = [
    root / "PROJECT.md",
    root / "PROJECT_CONTEXT.md",
    root / "AGENTS.md",
    root / "PROJECT_STATUS.yaml",
    root / "project.yaml",
    root / "docs/MASTER_ARCHITECTURE.md",
    root / "docs/NEXT_SPRINT_0.2.md",
    root / "docs/interactive-architecture.html",
    root / "docs/assets/live-house-overall-architecture.png",
    root / "apps/live-commerce/src/livecommerce/static/architecture.html",
    root / "apps/live-commerce/docs/openapi.json",
]
for path in required:
    if not path.is_file() or path.stat().st_size == 0:
        raise SystemExit(f"missing or empty required artifact: {path.relative_to(root)}")

for path in [root / "apps/live-commerce/docs/openapi.json"]:
    json.loads(path.read_text(encoding="utf-8"))

# Validate relative Markdown links that resolve to local files. Ignore anchors and URLs.
link_pattern = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
missing: list[str] = []
for md in root.rglob("*.md"):
    if any(part in {".venv", "build", "dist"} for part in md.parts):
        continue
    text = md.read_text(encoding="utf-8")
    for target in link_pattern.findall(text):
        target = target.strip().split("#", 1)[0]
        if not target or "://" in target or target.startswith(("mailto:", "#")):
            continue
        resolved = (md.parent / target).resolve()
        if not resolved.exists():
            missing.append(f"{md.relative_to(root)} -> {target}")
if missing:
    raise SystemExit("broken local Markdown links:\n" + "\n".join(missing))

print("project artifacts and local documentation links: ok")
PY

cd "$APP"
pytest
