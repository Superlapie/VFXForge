"""Shared export/runtime gate selection for service and CLI."""

from __future__ import annotations

from typing import Any


def engine_gate_result(export_mode: str, export_result: dict[str, Any] | None) -> tuple[bool, dict[str, Any], str | None]:
    if export_result is None:
        return False, {}, "REQUIRED_HOST_VALIDATION_UNAVAILABLE"
    if export_mode == "library":
        host_smoke = export_result.get("host_smoke_test") or {}
        status = host_smoke.get("status")
        if status == "passed":
            return True, host_smoke, None
        if status == "skipped":
            return False, host_smoke, "REQUIRED_HOST_VALIDATION_UNAVAILABLE"
        return False, host_smoke, "HOST_LIBRARY_SMOKE_FAILED"
    smoke = export_result.get("smoke_test") or {}
    status = smoke.get("status")
    if status == "passed":
        return True, smoke, None
    if status == "skipped":
        return False, smoke, "REQUIRED_ENGINE_VALIDATION_UNAVAILABLE"
    if status == "not_requested":
        return False, smoke, "REQUIRED_ENGINE_VALIDATION_UNAVAILABLE"
    return False, smoke, "EXPORT_SMOKE_FAILED"


def runtime_validation_for_mode(export_mode: str, export_result: dict[str, Any] | None) -> dict[str, Any]:
    _passed, payload, _code = engine_gate_result(export_mode, export_result)
    return payload
