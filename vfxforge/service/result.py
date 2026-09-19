"""ForgeResult contract and status invariants."""

from __future__ import annotations

from enum import Enum
from typing import Any

from ..version import SCHEMA_VERSION, TOOL_VERSION


RESULT_VERSION = 1


class ForgeStatus(str, Enum):
    READY = "ready"
    READY_CORRECTED = "ready_corrected"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"


EXIT_OK = 0
EXIT_FAILED = 1
EXIT_NEEDS_REVIEW = 4


def production_ready(status: ForgeStatus) -> bool:
    return status in {ForgeStatus.READY, ForgeStatus.READY_CORRECTED}


def make_result(
    status: ForgeStatus,
    effect_id: str,
    *,
    job_id: str | None = None,
    recipe: dict[str, Any] | None = None,
    policy: dict[str, Any] | None = None,
    seed: int | None = None,
    corrections: list[dict[str, Any]] | None = None,
    validation: dict[str, Any] | None = None,
    metrics: dict[str, Any] | None = None,
    previews: dict[str, Any] | None = None,
    runtime_validation: dict[str, Any] | None = None,
    export_validation: dict[str, Any] | None = None,
    artifacts: dict[str, Any] | None = None,
    hashes: dict[str, Any] | None = None,
    reproduction: dict[str, Any] | None = None,
    review_reasons: list[dict[str, Any]] | None = None,
    errors: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    ready = production_ready(status)
    return {
        "result_version": RESULT_VERSION,
        "status": status.value,
        "success": ready,
        "production_ready": ready,
        "effect_id": effect_id,
        "job_id": job_id,
        "tool_version": TOOL_VERSION,
        "schema_version": SCHEMA_VERSION,
        "recipe": recipe or {},
        "policy": policy or {},
        "seed": seed,
        "corrections": corrections or [],
        "validation": validation or {},
        "metrics": metrics or {},
        "previews": previews or {},
        "runtime_validation": runtime_validation or {},
        "export_validation": export_validation or {},
        "artifacts": artifacts or {},
        "hashes": hashes or {},
        "reproduction": reproduction or {},
        "review_reasons": review_reasons or [],
        "errors": errors or [],
    }


def exit_code_for(result: dict[str, Any]) -> int:
    status = result.get("status")
    if status == ForgeStatus.NEEDS_REVIEW.value:
        return EXIT_NEEDS_REVIEW
    if result.get("production_ready"):
        return EXIT_OK
    return EXIT_FAILED
