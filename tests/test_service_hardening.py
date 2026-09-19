#!/usr/bin/env python3
"""Hardening regression tests for the VFX Forge service layer."""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path

from vfxforge.service.compiler import compile_recipe
from vfxforge.service.pipeline import forge, plan
from vfxforge.service.policy import load_policy
from vfxforge.service.promotion import generation_digest, promote_candidate, request_hash
from vfxforge.service.request import normalize_request, validate_request
from vfxforge.service.result import ForgeStatus
from vfxforge.service.selector import load_recipe, select_recipe
from vfxforge.service.semantic import document_semantic_metrics, validate_recipe_semantics


ROOT = Path(__file__).resolve().parents[1]
REQUESTS = ROOT / "examples" / "requests"


def _read_request(name: str) -> dict:
    return json.loads((REQUESTS / name).read_text(encoding="utf-8"))


class GameplaySemanticsTests(unittest.TestCase):
    def test_enigma_boss_line_sweep_compiles_world_units_and_tell(self) -> None:
        request = normalize_request(_read_request("boss_line_sweep.vfxrequest.json"))
        policy = load_policy("enigma")
        recipe, _, review = select_recipe(request)
        self.assertIsNotNone(recipe)
        self.assertEqual(review, [])
        document = compile_recipe(request, recipe, policy)
        metrics = document_semantic_metrics(document)
        primary = metrics.get("primary_decal_size")
        self.assertIsNotNone(primary)
        self.assertAlmostEqual(primary[0], 1.5, places=3)
        self.assertAlmostEqual(primary[1], 6.0, places=3)
        self.assertAlmostEqual(metrics["resolve_time_sec"], 0.9, places=3)
        self.assertAlmostEqual(metrics["duration_sec"], 1.1, places=3)

    def test_unsupported_semantic_parameter_needs_review(self) -> None:
        request = normalize_request(_read_request("boss_line_sweep.vfxrequest.json"))
        request["gameplay"]["source_height"] = 2.0
        recipe, _, _ = select_recipe(request)
        self.assertIsNotNone(recipe)
        review = validate_recipe_semantics(request, recipe, load_policy("enigma"))
        self.assertTrue(any(item["code"] == "UNSUPPORTED_SEMANTIC_PARAMETER" for item in review))

    def test_absurd_radius_rejected(self) -> None:
        request = normalize_request(_read_request("ground_telegraph.vfxrequest.json"))
        request["gameplay"]["radius_tiles"] = 1000000
        recipe, _, _ = select_recipe(request)
        self.assertIsNotNone(recipe)
        review = validate_recipe_semantics(request, recipe, load_policy("enigma"))
        self.assertTrue(any(item["code"] == "SEMANTIC_OUT_OF_BOUNDS" for item in review))


class ProductionGateTests(unittest.TestCase):
    def test_enigma_no_export_not_production_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = forge(_read_request("boss_line_sweep.vfxrequest.json"), policy_id="enigma", workspace=tmp, export=False)
            self.assertEqual(result["status"], ForgeStatus.NEEDS_REVIEW.value)
            self.assertFalse(result["production_ready"])
            self.assertTrue(any(item["code"] == "PRODUCTION_EXPORT_NOT_RUN" for item in result["review_reasons"]))

    def test_default_no_export_can_be_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = forge(_read_request("fire_impact.vfxrequest.json"), policy_id="default", workspace=tmp, export=False)
            self.assertIn(result["status"], {ForgeStatus.READY.value, ForgeStatus.READY_CORRECTED.value})
            self.assertTrue(result["production_ready"])


class RecipeQualityTests(unittest.TestCase):
    def test_lightning_not_fire_composition(self) -> None:
        request = normalize_request({
            "request_version": 1,
            "effect_id": "lightning_test",
            "intent": {"kind": "lightning_strike", "element": "lightning", "purpose": "damage", "intensity": "standard"},
            "context": {"target": "generic", "usage": "normal_combat"},
        })
        recipe, _, _ = select_recipe(request)
        self.assertIsNotNone(recipe)
        document = compile_recipe(request, recipe, load_policy("default"))
        layer_ids = {layer.get("id") for layer in document.get("layers", [])}
        self.assertIn("bolt", layer_ids)
        self.assertNotIn("fireball", layer_ids)
        self.assertNotIn("scorch", layer_ids)
        colors = []
        for layer in document.get("layers", []):
            color = layer.get("properties", {}).get("color")
            if isinstance(color, str):
                colors.append(color.lower())
        self.assertTrue(any("ff" not in color or "6a" not in color for color in colors))

    def test_poison_cloud_loop_coverage(self) -> None:
        request = normalize_request({
            "request_version": 1,
            "effect_id": "poison_test",
            "intent": {"kind": "cloud", "element": "poison", "purpose": "debuff", "intensity": "standard"},
            "context": {"target": "generic", "usage": "ambient_world"},
            "gameplay": {"loop": True, "duration_ms": 3000},
        })
        recipe, _, _ = select_recipe(request)
        self.assertIsNotNone(recipe)
        document = compile_recipe(request, recipe, load_policy("default"))
        self.assertTrue(document.get("loop"))
        self.assertAlmostEqual(float(document.get("duration", 0.0)), 3.0, places=3)
        for layer in document.get("layers", []):
            if layer.get("type") in {"particle", "decal", "light"} and layer.get("enabled", True):
                self.assertGreaterEqual(float(layer.get("duration", 0.0)), 2.5)


class SecurityAndDigestTests(unittest.TestCase):
    def test_policy_traversal_rejected(self) -> None:
        with self.assertRaises(ValueError):
            load_policy("../recipes/impact_fire")

    def test_generation_digest_changes_with_recipe(self) -> None:
        request = normalize_request(_read_request("fire_impact.vfxrequest.json"))
        policy = load_policy("default")
        recipe_a = load_recipe("impact.fire")
        recipe_b = json.loads(json.dumps(recipe_a))
        recipe_b["recipe_version"] = 2
        digest_a = generation_digest(request, recipe_a, policy)
        digest_b = generation_digest(request, recipe_b, policy)
        self.assertNotEqual(digest_a, digest_b)


class ConcurrencyTests(unittest.TestCase):
    def test_promotion_lock_serializes_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            production = base / "production" / "shared_effect"
            candidate_a = base / "job_a" / "candidate"
            candidate_b = base / "job_b" / "candidate"
            candidate_a.mkdir(parents=True)
            candidate_b.mkdir(parents=True)
            (candidate_a / "document.vfx.json").write_text("{}\n", encoding="utf-8")
            (candidate_b / "document.vfx.json").write_text("{}\n", encoding="utf-8")
            meta_a = {"job_id": "job_a", "generation_digest": "digest_a", "allow_replace": False}
            meta_b = {"job_id": "job_b", "generation_digest": "digest_b", "allow_replace": False}
            errors: list[str] = []

            def promote(meta, candidate):
                try:
                    promote_candidate(candidate, production, meta)
                except RuntimeError as exc:
                    errors.append(str(exc))

            threads = [
                threading.Thread(target=promote, args=(meta_a, candidate_a)),
                threading.Thread(target=promote, args=(meta_b, candidate_b)),
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(len(errors), 1)


if __name__ == "__main__":
    unittest.main()
