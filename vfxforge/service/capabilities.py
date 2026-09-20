"""Agent-facing capability discovery for recipes and policies."""

from __future__ import annotations

from typing import Any

from ..property_spec import describe_property_registry, describe_property_relations
from ..schema import LAYER_TYPES
from .matrix import load_canonical_request, load_recipe_matrix
from .policy_target import target_policy_bindings
from .request import request_contract_dict
from .policy import list_policies, load_policy
from .runtime_conformance import RUNTIME_PRODUCTION_LAYER_TYPES, SCHEMA_ONLY_LAYER_TYPES, runtime_capability_contract
from .selector import list_recipes, load_recipe


def _recipe_capability(recipe: dict[str, Any]) -> dict[str, Any]:
    matcher = recipe.get("matcher", {}) if isinstance(recipe.get("matcher"), dict) else {}
    required = [item for item in (recipe.get("required_gameplay") or []) if isinstance(item, str)]
    supported = [item for item in (recipe.get("supported_gameplay") or []) if isinstance(item, str)]
    consumed = [item for item in (recipe.get("consumed_gameplay") or []) if isinstance(item, str)]
    optional = [item for item in supported if item not in required]
    return {
        "id": recipe.get("recipe_id"),
        "version": recipe.get("recipe_version", 1),
        "description": recipe.get("description", ""),
        "matches": matcher,
        "required": required,
        "optional": optional,
        "consumed": consumed,
        "unsupported_parameters_are_errors": not bool(recipe.get("allow_extra_gameplay", False)),
        "timing": recipe.get("timing", {}) if isinstance(recipe.get("timing"), dict) else {},
        "bindings": recipe.get("bindings", []) if isinstance(recipe.get("bindings"), list) else [],
    }


def _policy_capability(policy: dict[str, Any]) -> dict[str, Any]:
    runtime_gate = str(policy.get("runtime_gate") or "")
    required_mode = policy.get("required_export_mode")
    if not required_mode and runtime_gate == "host_project":
        required_mode = "library"
    return {
        "id": policy.get("policy_id"),
        "version": policy.get("policy_version", 1),
        "description": policy.get("description", ""),
        "defaults": policy.get("defaults", {}),
        "contexts": policy.get("contexts", {}),
        "semantic_bounds": policy.get("semantic_bounds", {}),
        "require_export_for_production": bool(policy.get("require_export_for_production", policy.get("require_godot_smoke", False))),
        "require_engine_validation": bool(policy.get("require_engine_validation", policy.get("require_godot_smoke", False))),
        "runtime_gate": runtime_gate or ("host_project" if required_mode == "library" else "standalone"),
        "required_export_mode": required_mode or "standalone",
        "resource_root_template": policy.get("resource_root_template"),
        "shared_runtime_path": policy.get("shared_runtime_path"),
        "preview_cameras": policy.get("preview_cameras", ["mmo"]),
    }


def _request_contract() -> dict[str, Any]:
    return request_contract_dict()


def _recipe_templates() -> list[dict[str, Any]]:
    templates: list[dict[str, Any]] = []
    for recipe_id, filename in sorted(load_recipe_matrix().items()):
        templates.append({
            "recipe_id": recipe_id,
            "request_file": f"templates/requests/{filename}",
            "request": load_canonical_request(recipe_id),
        })
    return templates


def capabilities(policy_id: str | None = None) -> dict[str, Any]:
    policy_ids = [policy_id] if policy_id else list_policies()
    policies = [_policy_capability(load_policy(item)) for item in policy_ids]
    recipes = [_recipe_capability(load_recipe(item)) for item in list_recipes()]
    selected = policies[0] if policy_id and policies else None
    return {
        "capabilities_version": 6,
        "field_specs": describe_property_registry(),
        "property_relations": describe_property_relations(),
        "reference_semantics": {
            "child_effects": {
                "res://": "project_root",
                "relative_path": "referencing_document_directory",
                "stable_id": "unique_search_under_project_root_non_generated_source_documents",
            },
            "dependencies_effects": {
                "res://": "project_root",
                "relative_path": "referencing_document_directory",
                "stable_id": "unique_search_under_project_root_non_generated_source_documents",
            },
            "textures": "project_root_relative",
            "meshes": "project_root_relative",
        },
        "request_contract": _request_contract(),
        "target_policy_bindings": target_policy_bindings(),
        "layer_support": {
            "schema_layer_types": list(LAYER_TYPES),
            "runtime_production_layer_types": sorted(RUNTIME_PRODUCTION_LAYER_TYPES),
            "schema_only_layer_types": sorted(SCHEMA_ONLY_LAYER_TYPES),
        },
        "runtime": runtime_capability_contract(),
        "recipe_templates": _recipe_templates(),
        "policy": selected,
        "policies": policies,
        "recipes": recipes,
    }
