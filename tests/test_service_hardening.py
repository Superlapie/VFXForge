#!/usr/bin/env python3
"""Hardening regression tests for the VFX Forge service layer."""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from copy import deepcopy
from pathlib import Path

from vfxforge.model import set_path
from vfxforge.presets import make_preset
from vfxforge.service.autocorrect import autocorrect_document
from vfxforge.service.compiler import compile_recipe
from vfxforge.service.pipeline import forge, plan
from vfxforge.service.policy import load_policy
from vfxforge.service.promotion import generation_digest, promote_candidate, request_hash
from vfxforge.service.request import normalize_request, validate_request
from vfxforge.service.result import ForgeStatus
from vfxforge.service.selector import load_recipe, select_recipe
from vfxforge.service.semantic import document_semantic_metrics, protected_document_paths, validate_recipe_semantics


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

    def test_boss_resolve_flash_occurs_at_tell(self) -> None:
        request = normalize_request(_read_request("boss_line_sweep.vfxrequest.json"))
        recipe = load_recipe("boss.line_sweep")
        document = compile_recipe(request, recipe, load_policy("enigma"))
        timings = document_semantic_metrics(document)["layer_timings"]
        warning = timings["warning_line"]
        resolve_flash = timings["resolve_flash"]
        self.assertAlmostEqual(warning["start"], 0.0, places=3)
        self.assertAlmostEqual(warning["end"], 0.9, places=3)
        self.assertAlmostEqual(resolve_flash["start"], 0.9, places=3)
        self.assertLessEqual(resolve_flash["end"], 1.1 + 1e-3)
        self.assertGreaterEqual(resolve_flash["end"], 1.0)

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


class AutocorrectProtectionTests(unittest.TestCase):
    def test_autocorrect_preserves_gameplay_semantics(self) -> None:
        request = normalize_request(_read_request("boss_line_sweep.vfxrequest.json"))
        recipe = load_recipe("boss.line_sweep")
        policy = load_policy("enigma")
        document = compile_recipe(request, recipe, policy)
        stressed = deepcopy(document)
        set_path(stressed, "layers.edge_sparks.properties.amount", 90000)
        stressed["duration"] = 0.5
        before_metrics = document_semantic_metrics(document)
        corrected, _, review = autocorrect_document(stressed, policy, "boss_combat", request, recipe)
        self.assertEqual(review, [])
        after_metrics = document_semantic_metrics(corrected)
        self.assertEqual(before_metrics["primary_decal_size"], after_metrics["primary_decal_size"])
        self.assertEqual(before_metrics["resolve_time_sec"], after_metrics["resolve_time_sec"])
        self.assertEqual(before_metrics["layer_timings"]["warning_line"], after_metrics["layer_timings"]["warning_line"])
        self.assertEqual(before_metrics["layer_timings"]["resolve_flash"], after_metrics["layer_timings"]["resolve_flash"])


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

    def test_generation_digest_changes_with_asset(self) -> None:
        request = normalize_request(_read_request("fire_impact.vfxrequest.json"))
        policy = load_policy("default")
        recipe = load_recipe("impact.fire")
        digest_a = generation_digest(request, recipe, policy)
        mutated = json.loads(json.dumps(recipe))
        mutated.setdefault("document", {}).setdefault("dependencies", {}).setdefault("textures", []).append("examples/assets/textures/nonexistent_probe.png")
        digest_b = generation_digest(request, mutated, policy)
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

    def test_identical_requests_use_unique_job_workspaces(self) -> None:
        request = _read_request("fire_impact.vfxrequest.json")
        with tempfile.TemporaryDirectory() as tmp:
            first = forge(request, policy_id="default", workspace=tmp, export=False)
            second = forge(request, policy_id="default", workspace=tmp, export=False)
            self.assertNotEqual(first["job_id"], second["job_id"])


class PromotionSafetyTests(unittest.TestCase):
    def test_failed_promotion_restores_previous_production(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            production = base / "production" / "effect"
            first_candidate = base / "first" / "candidate"
            second_candidate = base / "second" / "candidate"
            first_candidate.mkdir(parents=True)
            second_candidate.mkdir(parents=True)
            (first_candidate / "marker.txt").write_text("first\n", encoding="utf-8")
            (second_candidate / "broken").write_text("ok\n", encoding="utf-8")
            promote_candidate(first_candidate, production, {"job_id": "job1", "generation_digest": "a", "allow_replace": True})
            self.assertTrue(production.exists())
            with self.assertRaises(Exception):
                promote_candidate(second_candidate / "missing", production, {"job_id": "job2", "generation_digest": "b", "allow_replace": True})
            self.assertTrue(production.exists())
            self.assertTrue((production / "marker.txt").exists())


if __name__ == "__main__":
    unittest.main()
