from __future__ import annotations

import hashlib
import json
import os
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXCLUDED_DIRS = {".git", ".venv", ".pytest_cache", "__pycache__", "build", "dist"}
EXCLUDED_FROM_INVENTORY = {"PROJECT_MANIFEST.json", "PROJECT_FILES.sha256"}


def included(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if any(part in EXCLUDED_DIRS or part.endswith(".egg-info") for part in rel.parts):
        return False
    if path.name in EXCLUDED_FROM_INVENTORY or path.suffix in {".pyc", ".pyo"}:
        return False
    if path.name.endswith((".db", ".db-wal", ".db-shm")):
        return False
    return path.is_file()


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


files = sorted((p for p in ROOT.rglob("*") if included(p)), key=lambda p: p.as_posix())
rows = [
    {
        "path": p.relative_to(ROOT).as_posix(),
        "size_bytes": p.stat().st_size,
        "sha256": digest(p),
    }
    for p in files
]
manifest = {
    "project": {
        "name": "Live House",
        "slug": "live-house",
        "version": "0.1.0",
        "status": "development",
        "phase": "increment_0_1_complete",
        "generated_at": date.today().isoformat(),
        "timezone_context": "Asia/Tokyo",
    },
    "canonical_application": "apps/live-commerce",
    "verified_test_result": os.environ.get("VERIFIED_TEST_RESULT", "run make verify"),
    "next_increment": {
        "id": "0.2",
        "name": "real_fal_staging_integration",
        "backlog": "docs/NEXT_SPRINT_0.2.md",
    },
    "entrypoints": {
        "cli": "live-commerce",
        "application": "livecommerce.main:app",
        "studio": "/studio",
        "viewer": "/viewer",
        "architecture": "/architecture",
        "openapi": "/docs",
    },
    "key_artifacts": {
        "overall_architecture": "docs/assets/live-house-overall-architecture.png",
        "interactive_architecture": "docs/interactive-architecture.html",
        "master_architecture": "docs/MASTER_ARCHITECTURE.md",
        "development_handoff": "docs/HANDOFF.md",
        "project_status": "PROJECT_STATUS.yaml",
        "application_wheel": "releases/fal_live_commerce_starter-0.1.0-py3-none-any.whl",
    },
    "file_count": len(rows),
    "files": rows,
}
manifest_path = ROOT / "PROJECT_MANIFEST.json"
manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

# The checksum set includes the generated manifest but excludes the checksum file itself.
checksum_rows = rows + [
    {
        "path": manifest_path.relative_to(ROOT).as_posix(),
        "sha256": digest(manifest_path),
    }
]
checksum_rows.sort(key=lambda row: row["path"])
(ROOT / "PROJECT_FILES.sha256").write_text(
    "".join(f"{row['sha256']}  {row['path']}\n" for row in checksum_rows),
    encoding="utf-8",
)
print(f"wrote manifest for {len(rows)} files plus manifest checksum")
