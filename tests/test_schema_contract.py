#!/usr/bin/env python3
"""JSON Schema contract tests for service data and results."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from vfxforge.schema_validate import validate_file, validate_instance
from vfxforge.service.pipeline import forge
from vfxforge.service.result import ForgeStatus, make_result


ROOT = Path(__file__).resolve().parents[1]


class SchemaContractTests(unittest.TestCase):
    def test_every_recipe_validates(self) -> None:
        for path in sorted((ROOT / "recipes").glob("*.json")):
            with self.subTest(path=path.name):
                validate_file(path, "vfx.recipe.schema.json")

    def test_every_policy_validates(self) -> None:
        for path in sorted((ROOT / "policies").glob("*.json")):
            with self.subTest(path=path.name):
                validate_file(path, "vfx.policy.schema.json")

    def test_every_example_request_validates(self) -> None:
        for path in sorted((ROOT / "examples" / "requests").glob("*.json")):
            with self.subTest(path=path.name):
                validate_file(path, "vfx.request.schema.json")

    def test_result_states_validate(self) -> None:
        request = json.loads((ROOT / "examples" / "requests" / "fire_impact.vfxrequest.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            ready = forge(request, policy_id="default", workspace=tmp, export=False)
            failed = forge({"effect_id": "bad"}, policy_id="default", workspace=tmp, export=False)
            review = forge(request, policy_id="enigma", workspace=tmp, export=False)
        for label, payload in {
            "ready": ready,
            "failed": failed,
            "needs_review": review,
        }.items():
            with self.subTest(state=label):
                validate_instance(payload, "vfx.result.schema.json")
        corrected = make_result(ForgeStatus.READY_CORRECTED, "demo", seed=1, corrections=[{"code": "TEST"}])
        validate_instance(corrected, "vfx.result.schema.json")


if __name__ == "__main__":
    unittest.main()
