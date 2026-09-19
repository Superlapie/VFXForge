"""Bind semantic request targets to production policies."""

from __future__ import annotations

from typing import Any


TARGET_POLICY = {
    "enigma": "enigma",
    "standalone": "default",
    "generic": "default",
}


def expected_policy_for_target(target: str | None) -> str | None:
    if not target:
        return None
    return TARGET_POLICY.get(str(target))


def validate_policy_target(normalized_request: dict[str, Any], policy_id: str) -> dict[str, Any] | None:
    target = str(normalized_request.get("context", {}).get("target") or "")
    if target in {"", "generic"}:
        return None
    expected = expected_policy_for_target(target)
    if expected is None or policy_id == expected:
        return None
    return {
        "code": "POLICY_TARGET_MISMATCH",
        "message": (
            f"Request context.target '{target}' requires policy '{expected}', "
            f"but forge was invoked with policy '{policy_id}'."
        ),
        "context_target": target,
        "expected_policy": expected,
        "requested_policy": policy_id,
    }
