"""High-level forge and plan pipeline."""

from __future__ import annotations

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
    create_job_workspace,
    generation_digest,
    promote_candidate,
    production_dir,
    request_hash,
)
from .provenance import build_provenance, write_manifest
from .request import normalize_request, validate_request
from .result import ForgeStatus, make_result
from .selector import recipe_ref, select_recipe
from .semantic import validate_recipe_semantics


def _policy_requires_export(policy: dict[str, Any]) -> bool:
    return bool(policy.get("require_export_for_production", policy.get("require_godot_smoke", False)))


def _policy_requires_engine(policy: dict[str, Any]) -> bool:
    return bool(policy.get("require_engine_validation", policy.get("require_godot_smoke", False)))


def _engine_gate_result(export_mode: str, export_result: dict[str, Any] | None) -> tuple[bool, dict[str, Any], str | None]:
    if export_result is None:
        return False, {}, "REQUIRED_HOST_VALIDATION_UNAVAILABLE"
    if export_mode == "standalone":
        smoke = export_result.get("smoke_test", {})
        if smoke.get("status") == "passed":
            return True, smoke, None
        if smoke.get("status") == "skipped":
            return False, smoke, "REQUIRED_ENGINE_VALIDATION_UNAVAILABLE"
        return False, smoke, "EXPORT_SMOKE_FAILED"
    host_smoke = export_result.get("host_smoke_test", {})
    if host_smoke.get("status") == "passed":
        return True, host_smoke, None
    if host_smoke.get("status") == "skipped":
        return False, host_smoke, "REQUIRED_HOST_VALIDATION_UNAVAILABLE"
    return False, host_smoke, "HOST_LIBRARY_SMOKE_FAILED"


def plan(raw_request: dict[str, Any], policy_id: str = "default") -> dict[str, Any]:
    document, errors = validate_request(raw_request)
    if document is None:
        return make_result(ForgeStatus.FAILED, str(raw_request.get("effect_id", "unknown")), errors=errors)
    normalized = normalize_request(document)
    policy = load_policy(policy_id)
    recipe, matches, review = select_recipe(normalized)
    if recipe:
        review = review + validate_recipe_semantics(normalized, recipe, policy)
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


def validate_compiled_effect(
    document: dict[str, Any],
    policy: dict[str, Any],
    usage: str,
    project_dir: str | Path | None,
) -> dict[str, Any]:
    ceilings = policy_ceilings(policy, usage)
    return validate_document(
        document,
        project_dir=project_dir,
        strict=True,
        policy_ceilings=ceilings,
        selected_budget=allowed_budget_profile(policy, usage),
    )


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
    asset_root: str | Path | None = None,
    asset_catalog: dict[str, str] | None = None,
) -> dict[str, Any]:
    document, errors = validate_request(raw_request)
    effect_id = str(raw_request.get("effect_id", "unknown"))
    if document is None:
        return make_result(ForgeStatus.FAILED, effect_id, errors=errors)
    normalized = normalize_request(document)
    effect_id = normalized["effect_id"]
    policy = load_policy(policy_id)
    recipe, _, review = select_recipe(normalized)
    if review:
        status = ForgeStatus.NEEDS_REVIEW if review[0].get("code") in {"UNSUPPORTED_INTENT", "AMBIGUOUS_RECIPE"} else ForgeStatus.FAILED
        return make_result(status, effect_id, policy=policy_ref(policy_id), review_reasons=review, errors=review)
    if recipe is None:
        return make_result(ForgeStatus.NEEDS_REVIEW, effect_id, policy=policy_ref(policy_id), review_reasons=[{"code": "UNSUPPORTED_INTENT", "message": "No recipe selected."}])
    semantic_review = validate_recipe_semantics(normalized, recipe, policy)
    if semantic_review:
        return make_result(ForgeStatus.NEEDS_REVIEW, effect_id, policy=policy_ref(policy_id), recipe=recipe_ref(recipe), review_reasons=semantic_review)
    if dry_run:
        return plan(raw_request, policy_id)
    if _policy_requires_export(policy) and not export:
        return make_result(
            ForgeStatus.NEEDS_REVIEW,
            effect_id,
            policy=policy_ref(policy_id),
            recipe=recipe_ref(recipe),
            review_reasons=[{"code": "PRODUCTION_EXPORT_NOT_RUN", "message": "Policy requires export before production readiness."}],
        )

    gen_digest = generation_digest(
        normalized,
        recipe,
        policy,
        asset_root=asset_root,
        asset_catalog=asset_catalog,
    )
    workspace_path = Path(workspace).resolve()
    job, job_id = create_job_workspace(workspace_path, effect_id, gen_digest)
    candidate_doc_path = job / "candidate" / f"{effect_id}.vfx.json"
    compiled = compile_recipe(normalized, recipe, policy)
    usage = normalized.get("context", {}).get("usage", "normal_combat")
    ceilings = policy_ceilings(policy, usage)
    corrected, corrections, correction_review = autocorrect_document(compiled, policy, usage, normalized, recipe)
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
    write_document(candidate_doc_path, corrected)
    project_dir = Path(asset_root).resolve() if asset_root else candidate_doc_path.parent
    revalidation = validate_compiled_effect(corrected, policy, usage, project_dir)
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
                policy_ceilings=ceilings,
                project_dir=project_dir,
            )
            passed, runtime_validation, gate_code = _engine_gate_result(export_mode, export_result)
            if _policy_requires_engine(policy) and not passed:
                return make_result(
                    ForgeStatus.NEEDS_REVIEW if gate_code == "REQUIRED_HOST_VALIDATION_UNAVAILABLE" else ForgeStatus.FAILED,
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
                    review_reasons=[{"code": gate_code, "message": "Required engine validation did not pass.", "runtime_validation": runtime_validation}],
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
    provenance_payload = build_provenance(
        normalized,
        request_hash(normalized),
        gen_digest,
        recipe,
        policy,
        int(corrected.get("seed", 0)),
        corrections,
        revalidation,
        previews,
        export_result,
        export_mode=export_mode,
        resource_root=resource_root,
        shared_runtime_path=shared_runtime_path,
        asset_root=asset_root,
        asset_catalog=asset_catalog,
    )
    manifest_path = job / "forge_manifest.json"
    write_manifest(manifest_path, provenance_payload)
    promotion_metadata = {
        "request_hash": request_hash(normalized),
        "generation_digest": gen_digest,
        "effect_id": effect_id,
        "recipe_id": recipe.get("recipe_id"),
        "policy_id": policy.get("policy_id", policy_id),
        "job_id": job_id,
        "allow_replace": allow_replace,
    }
    try:
        if export and export_result:
            promote_candidate(job / "candidate" / "export", production, promotion_metadata, manifest_path)
        else:
            promote_candidate(job / "candidate", production, promotion_metadata, manifest_path)
    except RuntimeError as exc:
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
            review_reasons=[{"code": "EFFECT_ID_CONFLICT", "message": str(exc)}],
            artifacts={"candidate_document": str(candidate_doc_path), "job_workspace": str(job)},
        )
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
            "contact_sheet": previews.get("contact_sheet"),
        },
        hashes=provenance_payload.get("hashes", {}),
        reproduction=provenance_payload.get("reproduction", {}),
    )
