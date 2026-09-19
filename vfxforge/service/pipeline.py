"""High-level forge and plan pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..exporter import export_document
from ..model import write_document
from ..validation import validate_document
from .autocorrect import autocorrect_document
from .compiler import compile_recipe
from .policy import allowed_budget_profile, load_policy, policy_ceilings, policy_ref
from .preview_suite import render_preview_suite
from .promotion import (
    check_promotion_conflict,
    create_job_workspace,
    production_dir,
    promote_candidate,
    request_hash,
)
from .provenance import build_provenance, write_manifest
from .request import normalize_request, validate_request
from .result import ForgeStatus, make_result
from .selector import recipe_ref, select_recipe


def plan(raw_request: dict[str, Any], policy_id: str = "default") -> dict[str, Any]:
    document, errors = validate_request(raw_request)
    if document is None:
        return make_result(ForgeStatus.FAILED, str(raw_request.get("effect_id", "unknown")), errors=errors)
    normalized = normalize_request(document)
    policy = load_policy(policy_id)
    recipe, matches, review = select_recipe(normalized)
    usage = normalized.get("context", {}).get("usage", "normal_combat")
    return {
        "plan_version": 1,
        "normalized_request": normalized,
        "request_hash": request_hash(normalized),
        "policy": policy_ref(policy_id),
        "recipe": recipe_ref(recipe) if recipe else None,
        "match_count": len(matches),
        "expected_budget_profile": allowed_budget_profile(policy, usage) if recipe else None,
        "review_reasons": review,
        "status": ForgeStatus.NEEDS_REVIEW.value if review else (ForgeStatus.READY.value if recipe else ForgeStatus.FAILED.value),
    }


def forge(
    raw_request: dict[str, Any],
    *,
    policy_id: str = "default",
    workspace: str | Path = "build/service",
    export: bool = True,
    export_mode: str = "standalone",
    resource_root: str | None = None,
    shared_runtime_path: str | None = None,
    allow_replace: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    document, errors = validate_request(raw_request)
    effect_id = str(raw_request.get("effect_id", "unknown"))
    if document is None:
        return make_result(ForgeStatus.FAILED, effect_id, errors=errors)
    normalized = normalize_request(document)
    effect_id = normalized["effect_id"]
    req_hash = request_hash(normalized)
    policy = load_policy(policy_id)
    recipe, _, review = select_recipe(normalized)
    if review:
        status = ForgeStatus.NEEDS_REVIEW if review[0].get("code") in {"UNSUPPORTED_INTENT", "AMBIGUOUS_RECIPE"} else ForgeStatus.FAILED
        return make_result(status, effect_id, policy=policy_ref(policy_id), review_reasons=review, errors=review)
    if recipe is None:
        return make_result(ForgeStatus.NEEDS_REVIEW, effect_id, policy=policy_ref(policy_id), review_reasons=[{"code": "UNSUPPORTED_INTENT", "message": "No recipe selected."}])
    if dry_run:
        return plan(raw_request, policy_id)

    workspace_path = Path(workspace).resolve()
    job = create_job_workspace(workspace_path, effect_id, req_hash)
    job_id = job.name
    candidate_doc_path = job / "candidate" / f"{effect_id}.vfx.json"
    compiled = compile_recipe(normalized, recipe, policy)
    usage = normalized.get("context", {}).get("usage", "normal_combat")
    ceilings = policy_ceilings(policy, usage)
    validation = validate_document(compiled, strict=True, policy_ceilings=ceilings, selected_budget=allowed_budget_profile(policy, usage))
    corrected, corrections, correction_review = autocorrect_document(compiled, policy, usage, normalized)
    if correction_review:
        return make_result(
            ForgeStatus.NEEDS_REVIEW,
            effect_id,
            job_id=job_id,
            recipe=recipe_ref(recipe),
            policy=policy_ref(policy_id),
            seed=corrected.get("seed"),
            corrections=corrections,
            review_reasons=correction_review,
        )
    revalidation = validate_document(
        corrected,
        strict=True,
        policy_ceilings=ceilings,
        selected_budget=allowed_budget_profile(policy, usage),
    )
    if not revalidation["valid"]:
        return make_result(
            ForgeStatus.FAILED,
            effect_id,
            job_id=job_id,
            recipe=recipe_ref(recipe),
            policy=policy_ref(policy_id),
            seed=corrected.get("seed"),
            corrections=corrections,
            validation=revalidation,
            errors=revalidation["errors"],
        )
    write_document(candidate_doc_path, corrected)
    preview_cameras = policy.get("preview_cameras", ["mmo"])
    previews = render_preview_suite(corrected, job / "previews", preview_cameras)
    export_result: dict[str, Any] | None = None
    runtime_validation: dict[str, Any] = {}
    if export:
        export_output = job / "candidate" / "export"
        try:
            export_result = export_document(
                corrected,
                candidate_doc_path,
                export_output,
                run_smoke_test=True,
                mode=export_mode,
                resource_root=resource_root,
                shared_runtime_path=shared_runtime_path,
            )
            smoke = export_result.get("smoke_test", {})
            runtime_validation = smoke
            require_smoke = bool(policy.get("require_godot_smoke", False)) and export_mode == "standalone"
            if require_smoke and smoke.get("status") != "passed":
                code = "REQUIRED_ENGINE_VALIDATION_UNAVAILABLE" if smoke.get("status") == "skipped" else "EXPORT_SMOKE_FAILED"
                return make_result(
                    ForgeStatus.NEEDS_REVIEW if smoke.get("status") == "skipped" else ForgeStatus.FAILED,
                    effect_id,
                    job_id=job_id,
                    recipe=recipe_ref(recipe),
                    policy=policy_ref(policy_id),
                    seed=corrected.get("seed"),
                    corrections=corrections,
                    validation=revalidation,
                    metrics=revalidation.get("metrics"),
                    previews=previews,
                    runtime_validation=runtime_validation,
                    export_validation=export_result,
                    review_reasons=[{"code": code, "message": "Godot runtime validation did not pass.", "smoke_test": smoke}],
                )
        except Exception as exc:
            return make_result(
                ForgeStatus.FAILED,
                effect_id,
                job_id=job_id,
                recipe=recipe_ref(recipe),
                policy=policy_ref(policy_id),
                errors=[{"code": "EXPORT_FAILED", "message": str(exc)}],
            )
    production = production_dir(workspace_path, effect_id)
    conflict = check_promotion_conflict(production, req_hash, allow_replace)
    if conflict:
        return make_result(
            ForgeStatus.NEEDS_REVIEW,
            effect_id,
            job_id=job_id,
            recipe=recipe_ref(recipe),
            policy=policy_ref(policy_id),
            seed=corrected.get("seed"),
            corrections=corrections,
            validation=revalidation,
            previews=previews,
            review_reasons=[conflict],
            artifacts={"candidate_document": str(candidate_doc_path), "job_workspace": str(job)},
        )
    promoted_from = job / "candidate" / "export" if export else job / "candidate"
    provenance_payload = build_provenance(
        normalized,
        req_hash,
        recipe,
        policy,
        int(corrected.get("seed", 0)),
        corrections,
        revalidation,
        previews,
        export_result,
    )
    manifest_path = job / "forge_manifest.json"
    write_manifest(manifest_path, provenance_payload)
    if export and export_result:
        promote_candidate(job / "candidate" / "export", production, {"request_hash": req_hash, "effect_id": effect_id, "recipe_id": recipe.get("recipe_id")})
    else:
        promote_candidate(job / "candidate", production, {"request_hash": req_hash, "effect_id": effect_id, "recipe_id": recipe.get("recipe_id")})
    status = ForgeStatus.READY_CORRECTED if corrections else ForgeStatus.READY
    return make_result(
        status,
        effect_id,
        job_id=job_id,
        recipe=recipe_ref(recipe),
        policy=policy_ref(policy_id),
        seed=corrected.get("seed"),
        corrections=corrections,
        validation=revalidation,
        metrics=revalidation.get("metrics"),
        previews=previews,
        runtime_validation=runtime_validation,
        export_validation=export_result or {},
        artifacts={
            "document": str(candidate_doc_path),
            "manifest": str(manifest_path),
            "production": str(production),
            "preview_manifest": previews.get("manifest"),
        },
        hashes=provenance_payload.get("hashes", {}),
        reproduction=provenance_payload.get("reproduction", {}),
    )
