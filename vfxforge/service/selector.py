"""Deterministic recipe loading and selection."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .request import request_lookup_path


RECIPE_ROOT = Path(__file__).resolve().parents[2] / "recipes"


def _sha256_payload(data: dict[str, Any]) -> str:
    serialized = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def recipe_dir() -> Path:
    return RECIPE_ROOT


def _recipe_files() -> list[Path]:
    if not RECIPE_ROOT.exists():
        return []
    return sorted(RECIPE_ROOT.glob("*.json"))


def list_recipes() -> list[str]:
    ids: list[str] = []
    for path in _recipe_files():
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("recipe_id"):
            ids.append(str(data["recipe_id"]))
    return sorted(ids)


def load_recipe(recipe_id: str) -> dict[str, Any]:
    for path in _recipe_files():
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("recipe_id") == recipe_id:
            return data
    raise FileNotFoundError(f"Unknown recipe '{recipe_id}'. Available: {', '.join(list_recipes())}")


def recipe_ref(recipe: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": recipe.get("recipe_id"),
        "version": recipe.get("recipe_version", 1),
        "sha256": _sha256_payload(recipe),
    }


def _matcher_matches(request: dict[str, Any], matcher: dict[str, Any]) -> bool:
    for path, expected in matcher.items():
        actual = request_lookup_path(request, path)
        if isinstance(expected, list):
            if actual not in expected:
                return False
        elif actual != expected:
            return False
    return True


def select_recipe(request: dict[str, Any]) -> tuple[dict[str, Any] | None, list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (recipe, matches, review_reasons)."""
    matches: list[dict[str, Any]] = []
    for path in _recipe_files():
        recipe = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(recipe, dict):
            continue
        matcher = recipe.get("matcher", {})
        if isinstance(matcher, dict) and _matcher_matches(request, matcher):
            matches.append(recipe)
    if not matches:
        return None, [], [{"code": "UNSUPPORTED_INTENT", "message": "No recipe matches the normalized request."}]
    matches.sort(key=lambda item: (-int(item.get("priority", 0)), str(item.get("recipe_id", ""))))
    top_priority = int(matches[0].get("priority", 0))
    top = [item for item in matches if int(item.get("priority", 0)) == top_priority]
    if len(top) > 1:
        ids = [str(item.get("recipe_id")) for item in top]
        return None, matches, [{
            "code": "AMBIGUOUS_RECIPE",
            "message": f"Multiple recipes tie at priority {top_priority}: {', '.join(ids)}.",
            "candidates": ids,
        }]
    return top[0], matches, []
