#!/usr/bin/env python3
"""Comprehensive service-layer tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from vfxforge.model import set_path, write_document
from vfxforge.presets import make_preset
from vfxforge.service.autocorrect import autocorrect_document
from vfxforge.service.compiler import compile_recipe
from vfxforge.service.pipeline import forge, plan
from vfxforge.service.policy import load_policy
from vfxforge.service.request import normalize_request, validate_request
from vfxforge.service.result import ForgeStatus, production_ready
from vfxforge.service.selector import select_recipe
from vfxforge.validation import validate_document


ROOT = Path(__file__).resolve().parents[1]


def _fire_request(**overrides: object) -> dict:
    request = {
        "request_version": 1,
        "effect_id": "combat_fire_impact",
        "intent": {
            "kind": "impact",
            "element": "fire",
            "purpose": "damage",
            "intensity": "standard",
        },
        "context": {"target": "generic", "usage": "normal_combat"},
    }
    request.update(overrides)
    return request


class RequestContractTests(unittest.TestCase):
    def test_minimal_valid_fire_impact_request(self) -> None:
        doc, errors = validate_request(_fire_request())
        self.assertIsNotNone(doc)
        self.assertEqual(errors, [])

    def test_unknown_field_fails(self) -> None:
        bad = _fire_request(particles=64)
        doc, errors = validate_request(bad)
        self.assertIsNone(doc)
        self.assertTrue(any(item["code"] == "UNKNOWN_FIELD" for item in errors))

    def test_unknown_enum_fails(self) -> None:
        bad = _fire_request(intent={"kind": "impact", "element": "fire", "purpose": "damage", "intensity": "mega"})
        doc, errors = validate_request(bad)
        self.assertIsNone(doc)


class SelectionTests(unittest.TestCase):
    def test_same_request_selects_same_recipe(self) -> None:
        normalized = normalize_request(_fire_request())
        first, _, _ = select_recipe(normalized)
        second, _, _ = select_recipe(normalized)
        self.assertEqual(first["recipe_id"], second["recipe_id"])

    def test_unsupported_intent_needs_review(self) -> None:
        normalized = normalize_request(_fire_request(intent={"kind": "boss_ability", "element": "shadow", "purpose": "damage", "intensity": "boss"}))
        recipe, _, review = select_recipe(normalized)
        self.assertIsNone(recipe)
        self.assertEqual(review[0]["code"], "UNSUPPORTED_INTENT")


class StrictValidationTests(unittest.TestCase):
    def test_typoed_property_fails_strict(self) -> None:
        document = make_preset("fire_impact")
        for layer in document["layers"]:
            if layer.get("id") == "embers":
                layer.setdefault("properties", {})["intial_velocity_min"] = 1.0
        result = validate_document(document, strict=True)
        self.assertFalse(result["valid"])
        self.assertTrue(any(item["code"] == "UNKNOWN_LAYER_PROPERTY" for item in result["errors"]))

    def test_budget_overflow_blocks_strict(self) -> None:
        document = make_preset("fire_impact")
        set_path(document, "layers.embers.properties.amount", 50000)
        result = validate_document(document, strict=True)
        self.assertFalse(result["valid"])
        self.assertTrue(any(item["code"] == "PARTICLE_BUDGET_EXCEEDED" for item in result["errors"]))


class AutocorrectTests(unittest.TestCase):
    def test_particle_reduction_is_idempotent(self) -> None:
        document = make_preset("fire_impact")
        set_path(document, "layers.embers.properties.amount", 9000)
        policy = load_policy("default")
        first, ledger, _ = autocorrect_document(document, policy, "normal_combat")
        second, ledger2, _ = autocorrect_document(first, policy, "normal_combat")
        self.assertTrue(ledger)
        self.assertEqual(ledger2, [])


class ForgePipelineTests(unittest.TestCase):
    def test_forge_fire_impact_default_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = forge(_fire_request(), policy_id="default", workspace=tmp, export=False)
            self.assertIn(result["status"], {ForgeStatus.READY.value, ForgeStatus.READY_CORRECTED.value})
            self.assertTrue(result["production_ready"])

    def test_malformed_request_failed(self) -> None:
        result = forge({"effect_id": "bad"}, policy_id="default", workspace=tempfile.mkdtemp(), export=False)
        self.assertEqual(result["status"], ForgeStatus.FAILED.value)
        self.assertFalse(result["production_ready"])

    def test_plan_resolves_recipe(self) -> None:
        data = plan(_fire_request(), "default")
        self.assertEqual(data["recipe"]["id"], "impact.fire")


class ResultContractTests(unittest.TestCase):
    def test_production_ready_only_for_ready_states(self) -> None:
        self.assertTrue(production_ready(ForgeStatus.READY))
        self.assertTrue(production_ready(ForgeStatus.READY_CORRECTED))
        self.assertFalse(production_ready(ForgeStatus.NEEDS_REVIEW))
        self.assertFalse(production_ready(ForgeStatus.FAILED))


if __name__ == "__main__":
    unittest.main()
