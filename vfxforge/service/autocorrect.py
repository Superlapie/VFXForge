"""Bounded deterministic auto-correction for service production output."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from ..validation import estimate_metrics
from .policy import policy_ceilings
from .semantic import is_document_path_protected, protected_document_paths


MAX_CORRECTION_PASSES = 4


def _ledger_entry(code: str, path: str, before: Any, after: Any, reason: str, policy_id: str) -> dict[str, Any]:
    return {
        "code": code,
        "path": path,
        "before": before,
        "after": after,
        "reason": reason,
        "policy": policy_id,
    }


def _layer_roles(recipe: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    roles: dict[str, dict[str, Any]] = {}
    if not recipe:
        return roles
    for entry in recipe.get("layer_roles", []):
        if isinstance(entry, dict) and entry.get("id"):
            roles[str(entry["id"])] = entry
    return roles


def _is_required_layer(layer_id: str, roles: dict[str, dict[str, Any]]) -> bool:
    role = roles.get(layer_id, {})
    return bool(role.get("required", False))


def _correction_priority(layer_id: str, roles: dict[str, dict[str, Any]], default: int = 50) -> int:
    role = roles.get(layer_id, {})
    return int(role.get("correction_priority", default))


def _reduce_particles(document: dict[str, Any], ceiling: int, roles: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    metrics = estimate_metrics(document)
    overflow = metrics["peak_particles_estimate"] - ceiling
    if overflow <= 0:
        return entries
    reducible = []
    for layer in document.get("layers", []):
        if not isinstance(layer, dict) or not layer.get("enabled", True):
            continue
        if layer.get("type") not in {"particle", "mesh_particle"}:
            continue
        layer_id = str(layer.get("id", ""))
        if _is_required_layer(layer_id, roles):
            continue
        properties = layer.get("properties", {})
        amount = properties.get("amount", 0)
        if isinstance(amount, int) and amount > 1:
            reducible.append(layer)
    reducible.sort(key=lambda item: (_correction_priority(str(item.get("id", "")), roles), item.get("properties", {}).get("amount", 0)), reverse=True)
    remaining = overflow
    for layer in reducible:
        if remaining <= 0:
            break
        properties = layer["properties"]
        before = properties["amount"]
        reduction = min(before - 1, max(1, remaining // max(len(reducible), 1)))
        after = max(1, before - reduction)
        if after != before:
            properties["amount"] = after
            entries.append(_ledger_entry(
                "REDUCE_PARTICLE_AMOUNT",
                f"layers.{layer['id']}.properties.amount",
                before,
                after,
                "Reduce optional particle amount to satisfy policy ceiling.",
                "",
            ))
            remaining -= before - after
    return entries


def _reduce_lights(document: dict[str, Any], ceiling: int, roles: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    lights = [layer for layer in document.get("layers", []) if isinstance(layer, dict) and layer.get("enabled", True) and layer.get("type") == "light"]
    if len(lights) <= ceiling:
        return entries
    optional = [layer for layer in lights if not _is_required_layer(str(layer.get("id", "")), roles)]
    optional.sort(key=lambda item: _correction_priority(str(item.get("id", "")), roles), reverse=True)
    to_disable = optional or lights[ceiling:]
    for layer in to_disable[len(to_disable) - max(0, len(lights) - ceiling):]:
        before = layer.get("enabled", True)
        layer["enabled"] = False
        entries.append(_ledger_entry(
            "DISABLE_OPTIONAL_LIGHT",
            f"layers.{layer['id']}.enabled",
            before,
            False,
            "Disable optional dynamic lights beyond policy ceiling.",
            "",
        ))
        if len([item for item in document.get("layers", []) if isinstance(item, dict) and item.get("enabled", True) and item.get("type") == "light"]) <= ceiling:
            break
    return entries


def _trim_layer_duration(document: dict[str, Any], protected_paths: set[str]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    duration = float(document.get("duration", 0.0))
    for layer in document.get("layers", []):
        if not isinstance(layer, dict):
            continue
        layer_path = f"layers.{layer.get('id')}.duration"
        if is_document_path_protected(layer_path, protected_paths):
            continue
        start = float(layer.get("start", 0.0))
        layer_duration = float(layer.get("duration", 0.0))
        end = start + layer_duration
        if end > duration + 1e-6:
            before = layer_duration
            after = max(0.001, duration - start)
            layer["duration"] = after
            entries.append(_ledger_entry(
                "TRIM_LAYER_DURATION",
                layer_path,
                before,
                after,
                "Trim visual layer duration to effect duration.",
                "",
            ))
    return entries


def _disable_optional_layer(document: dict[str, Any], roles: dict[str, dict[str, Any]], protected_paths: set[str]) -> dict[str, Any] | None:
    optional = [
        layer for layer in document.get("layers", [])
        if isinstance(layer, dict)
        and layer.get("enabled", True)
        and layer.get("type") in {"particle", "sprite"}
        and not _is_required_layer(str(layer.get("id", "")), roles)
        and not is_document_path_protected(f"layers.{layer.get('id')}.enabled", protected_paths)
    ]
    optional.sort(key=lambda item: _correction_priority(str(item.get("id", "")), roles), reverse=True)
    return optional[0] if optional else None


def autocorrect_document(
    document: dict[str, Any],
    policy: dict[str, Any],
    usage: str,
    request: dict[str, Any] | None = None,
    recipe: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """Return corrected document, ledger entries, and review reasons."""
    policy_id = str(policy.get("policy_id", "default"))
    ceilings = policy_ceilings(policy, usage)
    corrected = deepcopy(document)
    ledger: list[dict[str, Any]] = []
    review: list[dict[str, Any]] = []
    roles = _layer_roles(recipe)
    protected_paths = protected_document_paths(recipe, corrected)
    for _ in range(MAX_CORRECTION_PASSES):
        pass_entries: list[dict[str, Any]] = []
        pass_entries.extend(_reduce_particles(corrected, ceilings["max_particles"], roles))
        pass_entries.extend(_reduce_lights(corrected, ceilings["max_lights"], roles))
        pass_entries.extend(_trim_layer_duration(corrected, protected_paths))
        metrics = estimate_metrics(corrected)
        if metrics["draw_calls_estimate"] > ceilings["max_draw_calls"]:
            layer = _disable_optional_layer(corrected, roles, protected_paths)
            if layer is not None:
                before = layer.get("enabled", True)
                layer["enabled"] = False
                pass_entries.append(_ledger_entry(
                    "DISABLE_OPTIONAL_LAYER",
                    f"layers.{layer['id']}.enabled",
                    before,
                    False,
                    "Disable optional visual layer to reduce draw calls.",
                    policy_id,
                ))
        for entry in pass_entries:
            entry["policy"] = policy_id
        if not pass_entries:
            break
        ledger.extend(pass_entries)
    metrics = estimate_metrics(corrected)
    if metrics["peak_particles_estimate"] > ceilings["max_particles"]:
        review.append({"code": "PARTICLE_BUDGET_UNCORRECTABLE", "message": "Particle budget still exceeded after correction."})
    if metrics["lights"] > ceilings["max_lights"]:
        review.append({"code": "LIGHT_BUDGET_UNCORRECTABLE", "message": "Light budget still exceeded after correction."})
    if metrics["draw_calls_estimate"] > ceilings["max_draw_calls"]:
        review.append({"code": "DRAW_CALL_BUDGET_UNCORRECTABLE", "message": "Draw call budget still exceeded after correction."})
    if float(corrected.get("duration", 0.0)) > ceilings["max_duration_sec"]:
        review.append({"code": "DURATION_POLICY_EXCEEDED", "message": "Effect duration exceeds policy maximum and cannot be silently reduced."})
    return corrected, ledger, review
