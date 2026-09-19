"""Job workspaces, locks, and transactional promotion."""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from ..resources import install_root
from ..version import SCHEMA_VERSION, TOOL_VERSION
from .paths import assert_safe_id


MANAGED_MARKER = ".vfxforge-managed"
LOCK_NAME = ".promotion.lock"
FORGE_MANIFEST = "forge_manifest.json"


def request_hash(normalized_request: dict[str, Any]) -> str:
    serialized = json.dumps(normalized_request, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _dependency_asset_hashes(recipe: dict[str, Any]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    document = recipe.get("document", {})
    if not isinstance(document, dict):
        return hashes
    root = install_root()
    candidates: list[Path] = []
    dependencies = document.get("dependencies", {})
    if isinstance(dependencies, dict):
        for key in ("textures", "meshes", "effects"):
            for reference in dependencies.get(key, []):
                if isinstance(reference, str) and reference:
                    candidates.append(root / reference)
                    candidates.append(root / "examples" / reference.removeprefix("examples/"))
    for layer in document.get("layers", []):
        if not isinstance(layer, dict):
            continue
        for container in (layer.get("properties", {}), layer.get("material", {})):
            if isinstance(container, dict):
                texture = container.get("texture")
                if isinstance(texture, str) and texture:
                    candidates.append(root / texture)
                    candidates.append(root / "examples" / texture.removeprefix("examples/"))
        properties = layer.get("properties", {})
        if isinstance(properties, dict):
            mesh = properties.get("mesh_asset")
            if isinstance(mesh, str) and mesh:
                candidates.append(root / mesh)
                candidates.append(root / "examples" / mesh.removeprefix("examples/"))
    seen: set[str] = set()
    for path in candidates:
        resolved = path.resolve()
        key = str(resolved)
        if key in seen or not resolved.is_file():
            continue
        seen.add(key)
        relative = resolved.relative_to(root.resolve()) if str(resolved).startswith(str(root.resolve())) else resolved.name
        hashes[str(relative).replace("\\", "/")] = hashlib.sha256(resolved.read_bytes()).hexdigest()
    return dict(sorted(hashes.items()))


def generation_digest(
    normalized_request: dict[str, Any],
    recipe: dict[str, Any],
    policy: dict[str, Any],
    *,
    tool_version: str = TOOL_VERSION,
    schema_version: int = SCHEMA_VERSION,
) -> str:
    asset_hashes = _dependency_asset_hashes(recipe)
    payload = {
        "request_hash": request_hash(normalized_request),
        "recipe_id": recipe.get("recipe_id"),
        "recipe_version": recipe.get("recipe_version", 1),
        "recipe_sha256": hashlib.sha256(json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "policy_id": policy.get("policy_id"),
        "policy_version": policy.get("policy_version", 1),
        "policy_sha256": hashlib.sha256(json.dumps(policy, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "asset_hashes": asset_hashes,
        "tool_version": tool_version,
        "schema_version": schema_version,
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


def acquire_promotion_lock(target: Path, job_id: str, timeout_sec: float = 30.0) -> Path:
    target.mkdir(parents=True, exist_ok=True)
    lock_path = target / LOCK_NAME
    deadline = time.time() + timeout_sec
    payload = json.dumps({"job_id": job_id, "pid": os.getpid(), "time": time.time()}) + "\n"
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
            return lock_path
        except FileExistsError:
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

    lock = acquire_promotion_lock(production_dir.parent, str(metadata.get("job_id", "promote")))
    staging = production_dir.with_name(production_dir.name + ".staging")
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
