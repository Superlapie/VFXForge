"""Job workspaces, locks, and transactional promotion."""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from ..version import SCHEMA_VERSION, TOOL_VERSION, generator_identity
from .assets import hash_assets
from .paths import assert_safe_id


MANAGED_MARKER = ".vfxforge-managed"
LOCK_NAME = ".promotion.lock"
FORGE_MANIFEST = "forge_manifest.json"
STALE_LOCK_SEC = 120.0


def request_hash(normalized_request: dict[str, Any]) -> str:
    serialized = json.dumps(normalized_request, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _dependency_asset_hashes(
    recipe: dict[str, Any],
    *,
    asset_root: str | Path | None = None,
    catalog: dict[str, str] | None = None,
) -> dict[str, str]:
    document = recipe.get("document", {})
    if not isinstance(document, dict):
        return {}
    return hash_assets(document, asset_root=asset_root, catalog=catalog)


def generation_digest(
    normalized_request: dict[str, Any],
    recipe: dict[str, Any],
    policy: dict[str, Any],
    *,
    tool_version: str = TOOL_VERSION,
    schema_version: int = SCHEMA_VERSION,
    asset_root: str | Path | None = None,
    asset_catalog: dict[str, str] | None = None,
    tool_revision: str | None = None,
    compiler_contract_version: int | None = None,
    runtime_contract_version: int | None = None,
    runtime_sha256: dict[str, str] | None = None,
) -> str:
    asset_hashes = _dependency_asset_hashes(recipe, asset_root=asset_root, catalog=asset_catalog)
    identity = generator_identity(
        tool_version=tool_version,
        revision=tool_revision,
        compiler_contract_version=compiler_contract_version,
        runtime_contract_version=runtime_contract_version,
    )
    if runtime_sha256 is not None:
        identity["runtime_sha256"] = runtime_sha256
    payload = {
        "request_hash": request_hash(normalized_request),
        "recipe_id": recipe.get("recipe_id"),
        "recipe_version": recipe.get("recipe_version", 1),
        "recipe_sha256": hashlib.sha256(json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "policy_id": policy.get("policy_id"),
        "policy_version": policy.get("policy_version", 1),
        "policy_sha256": hashlib.sha256(json.dumps(policy, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "asset_hashes": asset_hashes,
        "schema_version": schema_version,
        **identity,
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def create_job_workspace(base_dir: Path, effect_id: str, generation_id: str) -> tuple[Path, str]:
    assert_safe_id(effect_id, "effect_id")
    jobs_root = base_dir / "jobs"
    jobs_root.mkdir(parents=True, exist_ok=True)
    job_id = f"{effect_id}__{uuid.uuid4().hex[:12]}"
    workspace = jobs_root / job_id
    workspace.mkdir(parents=True, exist_ok=False)
    (workspace / "candidate").mkdir(exist_ok=True)
    (workspace / "previews").mkdir(exist_ok=True)
    meta = {"effect_id": effect_id, "generation_digest": generation_id, "job_id": job_id, "created_at": time.time()}
    (workspace / "job.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return workspace, job_id


def production_dir(base_dir: Path, effect_id: str) -> Path:
    assert_safe_id(effect_id, "effect_id")
    return base_dir / "production" / effect_id


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _lock_age_sec(lock_path: Path) -> float:
    try:
        return max(0.0, time.time() - lock_path.stat().st_mtime)
    except FileNotFoundError:
        return 0.0


def _lock_is_stale(lock_path: Path) -> bool:
    age = _lock_age_sec(lock_path)
    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return False
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        # A live acquirer can have created the file but not finished writing it.
        return age > STALE_LOCK_SEC
    pid = payload.get("pid")
    created = float(payload.get("time", 0.0) or 0.0)
    if created:
        age = max(age, time.time() - created)
    if isinstance(pid, int) and not _pid_alive(pid):
        return True
    if age > STALE_LOCK_SEC and not isinstance(pid, int):
        return True
    return False


def acquire_promotion_lock(lock_path: Path, job_id: str, timeout_sec: float = 30.0) -> Path:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.time() + timeout_sec
    payload = json.dumps({"job_id": job_id, "pid": os.getpid(), "time": time.time()}) + "\n"
    encoded = payload.encode("utf-8")
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            try:
                os.write(fd, encoded)
                os.fsync(fd)
            finally:
                os.close(fd)
            return lock_path
        except FileExistsError:
            if _lock_is_stale(lock_path):
                lock_path.unlink(missing_ok=True)
                continue
            if time.time() > deadline:
                raise TimeoutError(f"Promotion lock held too long: {lock_path}")
            time.sleep(0.05)


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


def check_promotion_conflict(production: Path, generation_id: str, allow_replace: bool) -> dict[str, Any] | None:
    marker = production / MANAGED_MARKER
    if not marker.exists():
        return None
    existing = json.loads(marker.read_text(encoding="utf-8"))
    previous = existing.get("generation_digest")
    if previous and previous != generation_id and not allow_replace:
        return {
            "code": "EFFECT_ID_CONFLICT",
            "message": "Production asset for this effect_id was generated from a different generation digest.",
            "existing_generation_digest": previous,
            "incoming_generation_digest": generation_id,
        }
    return None


def promote_candidate(candidate_dir: Path, production_dir: Path, metadata: dict[str, Any], manifest_path: Path | None = None) -> Path:
    import shutil

    job_token = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(metadata.get("job_id", "promote")))[:64] or "promote"
    lock = acquire_promotion_lock(production_dir.with_name(production_dir.name + ".promotion.lock"), job_token)
    staging = production_dir.with_name(production_dir.name + f".staging-{job_token}")
    backup = production_dir.with_name(production_dir.name + ".bak")
    promoted = False
    try:
        conflict = check_promotion_conflict(production_dir, str(metadata.get("generation_digest", "")), bool(metadata.get("allow_replace", False)))
        if conflict:
            raise RuntimeError(conflict["message"])
        if staging.exists():
            shutil.rmtree(staging)
        shutil.copytree(candidate_dir, staging)
        if manifest_path is not None and manifest_path.exists():
            shutil.copy2(manifest_path, staging / FORGE_MANIFEST)
        mark_managed(staging, metadata)
        had_production = production_dir.exists()
        if had_production:
            if backup.exists():
                shutil.rmtree(backup)
            production_dir.rename(backup)
        try:
            staging.rename(production_dir)
            promoted = True
        except Exception:
            if had_production and backup.exists() and not production_dir.exists():
                backup.rename(production_dir)
            raise
        if backup.exists():
            shutil.rmtree(backup, ignore_errors=True)
        return production_dir
    except Exception:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        if not promoted and backup.exists() and not production_dir.exists():
            backup.rename(production_dir)
        raise
    finally:
        release_promotion_lock(lock)
