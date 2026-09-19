"""Job workspaces, locks, and atomic promotion."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any


MANAGED_MARKER = ".vfxforge-managed"
LOCK_NAME = ".promotion.lock"


def request_hash(normalized_request: dict[str, Any]) -> str:
    serialized = json.dumps(normalized_request, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def create_job_workspace(base_dir: Path, effect_id: str, req_hash: str) -> Path:
    jobs_root = base_dir / "jobs"
    jobs_root.mkdir(parents=True, exist_ok=True)
    workspace = jobs_root / f"{effect_id}__{req_hash[:12]}"
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "candidate").mkdir(exist_ok=True)
    (workspace / "previews").mkdir(exist_ok=True)
    meta = {"effect_id": effect_id, "request_hash": req_hash, "created_at": time.time()}
    (workspace / "job.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return workspace


def production_dir(base_dir: Path, effect_id: str) -> Path:
    return base_dir / "production" / effect_id


def acquire_promotion_lock(target: Path, job_id: str, timeout_sec: float = 30.0) -> Path:
    target.mkdir(parents=True, exist_ok=True)
    lock_path = target / LOCK_NAME
    deadline = time.time() + timeout_sec
    while lock_path.exists():
        if time.time() > deadline:
            raise TimeoutError(f"Promotion lock held too long: {lock_path}")
        time.sleep(0.05)
    lock_path.write_text(json.dumps({"job_id": job_id, "pid": os.getpid(), "time": time.time()}) + "\n", encoding="utf-8")
    return lock_path


def release_promotion_lock(lock_path: Path) -> None:
    lock_path.unlink(missing_ok=True)


def mark_managed(directory: Path, metadata: dict[str, Any]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    payload = {"managed": True, **metadata}
    (directory / MANAGED_MARKER).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def is_managed(path: Path) -> bool:
    target = path if path.is_dir() else path.parent
    return (target / MANAGED_MARKER).exists()


def is_managed_document(path: Path) -> bool:
    return (path.parent / MANAGED_MARKER).exists()


def check_promotion_conflict(production: Path, req_hash: str, allow_replace: bool) -> dict[str, Any] | None:
    marker = production / MANAGED_MARKER
    if not marker.exists():
        return None
    existing = json.loads(marker.read_text(encoding="utf-8"))
    previous_hash = existing.get("request_hash")
    if previous_hash and previous_hash != req_hash and not allow_replace:
        return {
            "code": "EFFECT_ID_CONFLICT",
            "message": f"Production asset for this effect_id was generated from a different request hash.",
            "existing_request_hash": previous_hash,
            "incoming_request_hash": req_hash,
        }
    return None


def promote_candidate(candidate_dir: Path, production_dir: Path, metadata: dict[str, Any]) -> Path:
    import shutil
    production_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = production_dir.with_name(production_dir.name + ".staging")
    if staging.exists():
        shutil.rmtree(staging)
    shutil.copytree(candidate_dir, staging)
    mark_managed(staging, metadata)
    if production_dir.exists():
        backup = production_dir.with_name(production_dir.name + ".bak")
        if backup.exists():
            shutil.rmtree(backup)
        production_dir.rename(backup)
    staging.rename(production_dir)
    return production_dir
