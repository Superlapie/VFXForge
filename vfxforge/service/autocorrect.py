"""Bounded deterministic auto-correction for service production output."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from ..validation import estimate_metrics
from .policy import policy_ceilings


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


def _reduce_particles(document: dict[str, Any], ceiling: int) -> list[dict[str, Any]]:
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
        properties = layer.get("properties", {})
        amount = properties.get("amount", 0)
        if isinstance(amount, int) and amount > 1:
            reducible.append(layer)
    reducible.sort(key=lambda item: item.get("properties", {}).get("amount", 0), reverse=True)
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
                "Reduce particle amount to satisfy policy ceiling.",
                "",
            ))
            remaining -= before - after
    return entries


def _reduce_lights(document: dict[str, Any], ceiling: int) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    lights = [layer for layer in document.get("layers", []) if isinstance(layer, dict) and layer.get("enabled", True) and layer.get("type") == "light"]
    if len(lights) <= ceiling:
        return entries
    for layer in lights[ceiling:]:
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
    return entries


def _trim_layer_duration(document: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    duration = float(document.get("duration", 0.0))
    for layer in document.get("layers", []):
        if not isinstance(layer, dict):
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
                f"layers.{layer['id']}.duration",
                before,
                after,
                "Trim visual layer duration to effect duration.",
                "",
            ))
    return entries


def autocorrect_document(
    document: dict[str, Any],
    policy: dict[str, Any],
    usage: str,
    request: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """Return corrected document, ledger entries, and review reasons."""
    policy_id = str(policy.get("policy_id", "default"))
    ceilings = policy_ceilings(policy, usage)
    corrected = deepcopy(document)
    ledger: list[dict[str, Any]] = []
    review: list[dict[str, Any]] = []
    for _ in range(MAX_CORRECTION_PASSES):
        pass_entries: list[dict[str, Any]] = []
        pass_entries.extend(_reduce_particles(corrected, ceilings["max_particles"]))
        pass_entries.extend(_reduce_lights(corrected, ceilings["max_lights"]))
        pass_entries.extend(_trim_layer_duration(corrected))
        metrics = estimate_metrics(corrected)
        if metrics["draw_calls_estimate"] > ceilings["max_draw_calls"]:
            optional = [layer for layer in corrected.get("layers", []) if isinstance(layer, dict) and layer.get("enabled", True) and layer.get("type") in {"particle", "sprite"}]
            if optional:
                layer = optional[-1]
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
