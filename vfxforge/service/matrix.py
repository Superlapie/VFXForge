"""Canonical request coverage for every advertised recipe."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..resources import install_root
from .selector import list_recipes, load_recipe, select_recipe


def request_dir() -> Path:
    return install_root() / "examples" / "requests"


def load_recipe_matrix() -> dict[str, str]:
    path = request_dir() / "recipe_matrix.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("recipe_matrix.json must be an object mapping recipe_id to request filename.")
    return {str(key): str(value) for key, value in payload.items()}


def load_canonical_request(recipe_id: str) -> dict[str, Any]:
    filename = load_recipe_matrix()[recipe_id]
    path = request_dir() / filename
    return json.loads(path.read_text(encoding="utf-8"))


def uncovered_recipes() -> list[str]:
    matrix = load_recipe_matrix()
    return sorted(recipe_id for recipe_id in list_recipes() if recipe_id not in matrix)


def iter_recipe_requests() -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    rows: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    missing = uncovered_recipes()
    if missing:
        raise FileNotFoundError(f"Recipes missing canonical requests: {', '.join(missing)}")
    for recipe_id, filename in sorted(load_recipe_matrix().items()):
        request = json.loads((request_dir() / filename).read_text(encoding="utf-8"))
        rows.append((recipe_id, request, load_recipe(recipe_id)))
    return rows


def assert_request_selects_recipe(request: dict[str, Any], recipe_id: str) -> None:
    from .request import normalize_request, validate_request

    document, errors = validate_request(request)
    if document is None:
        raise ValueError(f"Canonical request for {recipe_id} is invalid: {errors}")
    recipe, _, review = select_recipe(normalize_request(document))
    if review or recipe is None or recipe.get("recipe_id") != recipe_id:
        raise ValueError(f"Canonical request does not select {recipe_id}: {review or recipe}")
