"""Semantic VFX request contract validation and normalization."""

from __future__ import annotations

import re
from typing import Any

from ..model import is_stable_id
from .paths import resolve_contained_file


REQUEST_VERSION = 1

INTENT_KINDS = frozenset({
    "impact", "lightning_strike", "cloud", "ground_telegraph", "projectile",
    "projectile_trail", "weapon_trail", "aura", "beam", "portal", "boss_ability",
})
INTENT_ELEMENTS = frozenset({
    "neutral", "fire", "lightning", "poison", "frost", "arcane", "shadow", "holy", "earth", "water",
})
INTENT_PURPOSES = frozenset({
    "damage", "danger_warning", "healing", "buff", "debuff", "ambience", "travel", "cosmetic",
})
INTENT_INTENSITIES = frozenset({"subtle", "standard", "strong", "boss"})
CONTEXT_TARGETS = frozenset({"standalone", "enigma", "generic"})
CONTEXT_USAGES = frozenset({
    "normal_combat", "boss_combat", "ground_telegraph", "ambient_world", "cinematic_preview",
})
GAMEPLAY_SHAPES = frozenset({"circle", "rectangle", "line", "point"})

ALLOWED_ROOT_KEYS = frozenset({
    "request_version", "effect_id", "intent", "gameplay", "context", "seed",
})
ALLOWED_INTENT_KEYS = frozenset({"kind", "element", "purpose", "intensity"})
ALLOWED_GAMEPLAY_KEYS = frozenset({
    "shape", "radius_tiles", "width_tiles", "length_tiles", "source_height", "target_distance",
    "tell_ms", "active_ms", "duration_ms", "loop", "attachment",
})
ALLOWED_CONTEXT_KEYS = frozenset({"target", "usage"})

GAMEPLAY_BOUNDS = {
    "radius_tiles": (0.25, 64.0),
    "width_tiles": (0.25, 64.0),
    "length_tiles": (0.25, 64.0),
    "source_height": (0.1, 64.0),
    "target_distance": (0.1, 256.0),
    "tell_ms": (50.0, 15000.0),
    "active_ms": (0.0, 30000.0),
    "duration_ms": (50.0, 30000.0),
}


def _issue(code: str, path: str, message: str, value: Any = None) -> dict[str, Any]:
    item: dict[str, Any] = {"code": code, "path": path, "message": message}
    if value is not None:
        item["value"] = value
    return item


def _reject_unknown_keys(data: dict[str, Any], allowed: frozenset[str], path: str, errors: list[dict[str, Any]]) -> None:
    for key in data:
        if key not in allowed:
            errors.append(_issue("UNKNOWN_FIELD", f"{path}.{key}", f"Unknown field '{key}' is not allowed.", key))


def validate_request(raw: Any) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    errors: list[dict[str, Any]] = []
    if not isinstance(raw, dict):
        return None, [_issue("INVALID_ROOT", "", "Request must be a JSON object.")]
    _reject_unknown_keys(raw, ALLOWED_ROOT_KEYS, "", errors)
    version = raw.get("request_version")
    if version != REQUEST_VERSION:
        errors.append(_issue("INVALID_REQUEST_VERSION", "request_version", f"request_version must be {REQUEST_VERSION}.", version))
    effect_id = raw.get("effect_id")
    if not is_stable_id(effect_id):
        errors.append(_issue("INVALID_EFFECT_ID", "effect_id", "effect_id must be a stable identifier.", effect_id))
    intent = raw.get("intent")
    if not isinstance(intent, dict):
        errors.append(_issue("MISSING_INTENT", "intent", "intent object is required."))
        intent = {}
    else:
        _reject_unknown_keys(intent, ALLOWED_INTENT_KEYS, "intent", errors)
        kind = intent.get("kind")
        if kind not in INTENT_KINDS:
            errors.append(_issue("INVALID_INTENT_KIND", "intent.kind", f"Unsupported intent kind '{kind}'.", kind))
        element = intent.get("element")
        if element not in INTENT_ELEMENTS:
            errors.append(_issue("INVALID_INTENT_ELEMENT", "intent.element", f"Unsupported element '{element}'.", element))
        purpose = intent.get("purpose")
        if purpose not in INTENT_PURPOSES:
            errors.append(_issue("INVALID_INTENT_PURPOSE", "intent.purpose", f"Unsupported purpose '{purpose}'.", purpose))
        intensity = intent.get("intensity", "standard")
        if intensity not in INTENT_INTENSITIES:
            errors.append(_issue("INVALID_INTENT_INTENSITY", "intent.intensity", f"Unsupported intensity '{intensity}'.", intensity))
    context = raw.get("context", {})
    if context is None:
        context = {}
    if not isinstance(context, dict):
        errors.append(_issue("INVALID_CONTEXT", "context", "context must be an object."))
        context = {}
    else:
        _reject_unknown_keys(context, ALLOWED_CONTEXT_KEYS, "context", errors)
        target = context.get("target", "generic")
        if target not in CONTEXT_TARGETS:
            errors.append(_issue("INVALID_CONTEXT_TARGET", "context.target", f"Unsupported target '{target}'.", target))
        usage = context.get("usage", "normal_combat")
        if usage not in CONTEXT_USAGES:
            errors.append(_issue("INVALID_CONTEXT_USAGE", "context.usage", f"Unsupported usage '{usage}'.", usage))
    gameplay = raw.get("gameplay", {})
    if gameplay is None:
        gameplay = {}
    if not isinstance(gameplay, dict):
        errors.append(_issue("INVALID_GAMEPLAY", "gameplay", "gameplay must be an object."))
        gameplay = {}
    else:
        _reject_unknown_keys(gameplay, ALLOWED_GAMEPLAY_KEYS, "gameplay", errors)
        shape = gameplay.get("shape")
        if shape is not None and shape not in GAMEPLAY_SHAPES:
            errors.append(_issue("INVALID_GAMEPLAY_SHAPE", "gameplay.shape", f"Unsupported shape '{shape}'.", shape))
        for key in ("radius_tiles", "width_tiles", "length_tiles", "source_height", "target_distance"):
            value = gameplay.get(key)
            if value is not None and (not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0):
                errors.append(_issue("INVALID_GAMEPLAY_NUMBER", f"gameplay.{key}", f"{key} must be a positive number.", value))
            elif value is not None and key in GAMEPLAY_BOUNDS:
                minimum, maximum = GAMEPLAY_BOUNDS[key]
                numeric = float(value)
                if numeric < minimum or numeric > maximum:
                    errors.append(_issue("SEMANTIC_OUT_OF_BOUNDS", f"gameplay.{key}", f"{key} must be between {minimum} and {maximum}.", value))
        for key in ("tell_ms", "active_ms", "duration_ms"):
            value = gameplay.get(key)
            if value is not None and (not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0):
                errors.append(_issue("INVALID_GAMEPLAY_TIMING", f"gameplay.{key}", f"{key} must be a non-negative number.", value))
            elif value is not None and key in GAMEPLAY_BOUNDS:
                minimum, maximum = GAMEPLAY_BOUNDS[key]
                numeric = float(value)
                if numeric < minimum or numeric > maximum:
                    errors.append(_issue("SEMANTIC_OUT_OF_BOUNDS", f"gameplay.{key}", f"{key} must be between {minimum} and {maximum}.", value))
        loop = gameplay.get("loop")
        if loop is not None and not isinstance(loop, bool):
            errors.append(_issue("INVALID_GAMEPLAY_LOOP", "gameplay.loop", "loop must be boolean.", loop))
    seed = raw.get("seed")
    if seed is not None and (not isinstance(seed, int) or isinstance(seed, bool)):
        errors.append(_issue("INVALID_SEED", "seed", "seed must be an integer.", seed))
    if errors:
        return None, errors
    return raw, []


def normalize_request(raw: dict[str, Any]) -> dict[str, Any]:
    intent = raw.get("intent", {})
    context = raw.get("context") or {}
    gameplay = raw.get("gameplay") or {}
    normalized = {
        "request_version": REQUEST_VERSION,
        "effect_id": str(raw["effect_id"]),
        "intent": {
            "kind": str(intent["kind"]),
            "element": str(intent["element"]),
            "purpose": str(intent["purpose"]),
            "intensity": str(intent.get("intensity", "standard")),
        },
        "context": {
            "target": str(context.get("target", "generic")),
            "usage": str(context.get("usage", "normal_combat")),
        },
        "gameplay": {},
    }
    for key, value in sorted(gameplay.items()):
        if isinstance(value, bool):
            normalized["gameplay"][key] = value
        elif isinstance(value, float) and value.is_integer():
            normalized["gameplay"][key] = int(value)
        else:
            normalized["gameplay"][key] = value
    if "seed" in raw:
        normalized["seed"] = int(raw["seed"])
    return normalized


def request_contract_dict() -> dict[str, Any]:
    return {
        "request_version": REQUEST_VERSION,
        "intent": {
            "kind": sorted(INTENT_KINDS),
            "element": sorted(INTENT_ELEMENTS),
            "purpose": sorted(INTENT_PURPOSES),
            "intensity": sorted(INTENT_INTENSITIES),
        },
        "context": {
            "target": sorted(CONTEXT_TARGETS),
            "usage": sorted(CONTEXT_USAGES),
        },
        "gameplay": {
            "shape": sorted(GAMEPLAY_SHAPES),
            "radius_tiles": "number > 0",
            "width_tiles": "number > 0",
            "length_tiles": "number > 0",
            "source_height": "number > 0",
            "target_distance": "number > 0",
            "tell_ms": "number >= 50",
            "active_ms": "number >= 0",
            "duration_ms": "number >= 50",
            "loop": "boolean",
            "attachment": "string",
        },
    }


def request_lookup_path(request: dict[str, Any], dotted: str) -> Any:
    current: Any = request
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def gameplay_critical_paths(request: dict[str, Any]) -> set[str]:
    critical = set()
    kind = request.get("intent", {}).get("kind")
    if kind == "ground_telegraph":
        critical.update({"gameplay.shape", "gameplay.radius_tiles", "gameplay.width_tiles", "gameplay.length_tiles", "gameplay.tell_ms"})
    if kind == "boss_ability":
        critical.update({"gameplay.shape", "gameplay.width_tiles", "gameplay.length_tiles", "gameplay.tell_ms", "gameplay.active_ms"})
    if request.get("gameplay", {}).get("tell_ms") is not None:
        critical.add("gameplay.tell_ms")
    return critical
