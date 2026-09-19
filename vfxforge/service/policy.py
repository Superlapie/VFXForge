"""Versioned data-only policy definitions for target environments."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ..resources import policies_dir
from .paths import resolve_contained_file


POLICY_ROOT = policies_dir()


def _sha256_payload(data: dict[str, Any]) -> str:
    serialized = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def policy_dir() -> Path:
    return POLICY_ROOT


def list_policies() -> list[str]:
    if not POLICY_ROOT.exists():
        return []
    return sorted(path.stem for path in POLICY_ROOT.glob("*.json"))


def load_policy(policy_id: str) -> dict[str, Any]:
    path = resolve_contained_file(POLICY_ROOT, policy_id, ".json")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Policy file must contain a JSON object: {path}")
    return data


def policy_ref(policy_id: str) -> dict[str, Any]:
    data = load_policy(policy_id)
    return {
        "id": data.get("policy_id", policy_id),
        "version": data.get("policy_version", 1),
        "sha256": _sha256_payload(data),
    }


def resolve_context_limits(policy: dict[str, Any], usage: str) -> dict[str, Any]:
    defaults = policy.get("defaults", {})
    contexts = policy.get("contexts", {})
    context = contexts.get(usage, {})
    merged = dict(defaults)
    merged.update(context)
    return merged


def allowed_budget_profile(policy: dict[str, Any], usage: str) -> str:
    limits = resolve_context_limits(policy, usage)
    return str(limits.get("budget_profile", policy.get("defaults", {}).get("budget_profile", "Medium")))


def policy_ceilings(policy: dict[str, Any], usage: str) -> dict[str, Any]:
    limits = resolve_context_limits(policy, usage)
    return {
        "max_particles": int(limits.get("max_particles", 5000)),
        "max_lights": int(limits.get("max_lights", 4)),
        "max_draw_calls": int(limits.get("max_draw_calls", 48)),
        "max_layers": int(limits.get("max_layers", 32)),
        "max_transparent_layers": int(limits.get("max_transparent_layers", 6)),
        "max_trail_segments": int(limits.get("max_trail_segments", 24)),
        "max_beam_segments": int(limits.get("max_beam_segments", 24)),
        "max_duration_sec": float(limits.get("max_duration_sec", 30.0)),
        "max_texture_dimension": int(limits.get("max_texture_dimension", 1024)),
        "max_child_effect_depth": int(limits.get("max_child_effect_depth", 4)),
        "allowed_layer_types": list(limits.get("allowed_layer_types", policy.get("allowed_layer_types", []))),
        "world_units_per_tile": float(limits.get("world_units_per_tile", policy.get("defaults", {}).get("world_units_per_tile", 1.0))),
    }


def world_units_per_tile(policy: dict[str, Any]) -> float:
    return float(policy.get("defaults", {}).get("world_units_per_tile", 1.0))
