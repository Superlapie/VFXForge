#!/usr/bin/env python3
"""Trust-boundary regressions for autonomous production use."""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from vfxforge import resources
from vfxforge.effect_refs import resolve_effect
from vfxforge.errors import RecipeBindingError
from vfxforge.exporter import export_document
from vfxforge.model import write_document
from vfxforge.schema import default_document, make_layer
from vfxforge.schema_validate import SchemaValidationError, validate_instance
from vfxforge.service.compiler import compile_recipe, compile_recipe_with_ledger
from vfxforge.service.capabilities import capabilities
from vfxforge.service.matrix import iter_recipe_requests
from vfxforge.service.pipeline import forge
from vfxforge.service.policy import load_policy
from vfxforge.service.promotion import acquire_promotion_lock, generation_digest, release_promotion_lock
from vfxforge.service.request import normalize_request
from vfxforge.service.result import ForgeStatus
from vfxforge.property_spec import RUNTIME_ENFORCED_RELATION_IDS
from vfxforge.service.runtime_conformance import RUNTIME_CONTRACT_VERSION, RUNTIME_PRODUCTION_LAYER_TYPES, validate_runtime_conformance
from vfxforge.service.selector import list_recipes, load_recipe, select_recipe
from vfxforge.service.semantic import validate_recipe_semantics
from vfxforge.validation import validate_document
from vfxforge.version import COMPILER_CONTRACT_VERSION

from tests.test_cli import run_cli


ROOT = Path(__file__).resolve().parents[1]
REQUESTS = ROOT / "examples" / "requests"


def _read_request(name: str) -> dict:
    return json.loads((REQUESTS / name).read_text(encoding="utf-8"))


class EnigmaPolicyGateTests(unittest.TestCase):
    def test_forge_status_imports_on_python310_style_enum(self) -> None:
        self.assertEqual(ForgeStatus.READY.value, "ready")

    def test_enigma_context_with_default_policy_is_rejected(self) -> None:
        request = _read_request("fire_impact.vfxrequest.json")
        request["context"] = {"target": "enigma", "usage": "normal_combat"}
        with tempfile.TemporaryDirectory() as tmp:
            result = forge(request, policy_id="default", workspace=tmp, export=False)
        self.assertEqual(result["status"], ForgeStatus.NEEDS_REVIEW.value)
        self.assertFalse(result["production_ready"])
        self.assertTrue(any(item["code"] == "POLICY_TARGET_MISMATCH" for item in result["review_reasons"]))

    def test_enigma_default_invocation_uses_library_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            captured = {}

            def fake_export(document, source, output, **kwargs):
                captured.update(kwargs)
                dest = Path(output)
                dest.mkdir(parents=True, exist_ok=True)
                (dest / "effect.tscn").write_text("[gd_scene]\n", encoding="utf-8")
                manifest = dest / "export_manifest.json"
                manifest.write_text("{}\n", encoding="utf-8")
                return {
                    "output": str(dest),
                    "manifest": str(manifest),
                    "smoke_test": {"status": "not_requested"},
                    "host_smoke_test": {"status": "passed", "checkpoints": [0.0]},
                    "validation": {"valid": True, "errors": [], "warnings": []},
                }

            with patch("vfxforge.service.pipeline.export_document", side_effect=fake_export):
                result = forge(_read_request("fire_impact.vfxrequest.json"), policy_id="enigma", workspace=tmp, export=True)
            self.assertEqual(captured.get("mode"), "library")
            self.assertTrue(str(captured.get("resource_root", "")).startswith("res://generated/vfx/"))
            self.assertIn(result["status"], {ForgeStatus.READY.value, ForgeStatus.READY_CORRECTED.value})

    def test_enigma_explicit_standalone_is_not_production_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = forge(
                _read_request("fire_impact.vfxrequest.json"),
                policy_id="enigma",
                workspace=tmp,
                export=True,
                export_mode="standalone",
            )
            self.assertEqual(result["status"], ForgeStatus.NEEDS_REVIEW.value)
            self.assertFalse(result["production_ready"])
            self.assertTrue(any(item["code"] == "POLICY_EXPORT_MODE_MISMATCH" for item in result["review_reasons"]))


class GameplayRejectionMatrixTests(unittest.TestCase):
    def test_every_recipe_rejects_undeclared_gameplay(self) -> None:
        policy = load_policy("default")
        for recipe_id in list_recipes():
            recipe = load_recipe(recipe_id)
            request = {
                "request_version": 1,
                "effect_id": "probe_effect",
                "intent": {"kind": "impact", "element": "fire", "purpose": "damage", "intensity": "standard"},
                "gameplay": {"source_height": 3.0},
                "context": {"target": "standalone", "usage": "normal_combat"},
            }
            request["intent"]["kind"] = {
                "aura.healing": "aura",
                "beam.lightning": "beam",
                "boss.eruption_2x2": "boss_ability",
                "boss.line_sweep": "boss_ability",
                "cloud.poison": "cloud",
                "impact.dust": "impact",
                "impact.fire": "impact",
                "impact.neutral": "impact",
                "lightning.strike": "lightning_strike",
                "portal.standard": "portal",
                "telegraph.circle": "ground_telegraph",
                "telegraph.line": "ground_telegraph",
                "telegraph.rectangle": "ground_telegraph",
                "trail.projectile": "projectile_trail",
                "trail.weapon": "weapon_trail",
            }[recipe_id]
            if recipe_id == "aura.healing":
                request["intent"]["purpose"] = "healing"
                request["intent"]["element"] = "holy"
            if recipe_id == "impact.dust":
                request["intent"]["element"] = "earth"
            if recipe_id in {"telegraph.circle", "telegraph.line", "telegraph.rectangle", "boss.line_sweep", "boss.eruption_2x2"}:
                request["intent"]["purpose"] = "danger_warning"
            normalized = normalize_request(request)
            review = validate_recipe_semantics(normalized, recipe, policy)
            self.assertTrue(
                any(item["code"] == "UNSUPPORTED_SEMANTIC_PARAMETER" for item in review),
                msg=f"{recipe_id} accepted undeclared gameplay.source_height: {review}",
            )


class SemanticConsumptionTests(unittest.TestCase):
    def test_broken_binding_target_cannot_be_ready(self) -> None:
        request = normalize_request(_read_request("trail_weapon.vfxrequest.json"))
        request.setdefault("context", {})["target"] = "generic"
        recipe = load_recipe("trail.weapon")
        broken = deepcopy(recipe)
        broken["bindings"][0]["to"] = "layers.blade_tral.properties.target"
        with self.assertRaises(RecipeBindingError) as context:
            compile_recipe(request, broken, load_policy("enigma"))
        self.assertEqual(context.exception.code, "RECIPE_BINDING_TARGET_MISSING")
        with tempfile.TemporaryDirectory() as tmp:
            forged_request = _read_request("trail_weapon.vfxrequest.json")
            forged_request.setdefault("context", {})["target"] = "generic"
            with patch("vfxforge.service.pipeline.select_recipe", return_value=(broken, [broken], [])):
                result = forge(forged_request, policy_id="default", workspace=tmp, export=False)
            self.assertFalse(result["production_ready"])
            self.assertEqual(result["status"], ForgeStatus.FAILED.value)
            self.assertTrue(any(item["code"] == "RECIPE_BINDING_TARGET_MISSING" for item in result["errors"]))

    def test_weapon_trail_consumes_attachment(self) -> None:
        request = normalize_request(_read_request("trail_weapon.vfxrequest.json"))
        recipe = load_recipe("trail.weapon")
        document, ledger = compile_recipe_with_ledger(request, recipe, load_policy("enigma"))
        self.assertTrue(ledger["gameplay.attachment"]["verified"])
        trail = next(layer for layer in document["layers"] if layer["id"] == "blade_trail")
        self.assertEqual(trail["properties"]["target"], "weapon")


class LibraryCliFailureTests(unittest.TestCase):
    def test_library_export_cli_fails_when_host_smoke_fails(self) -> None:
        payload = {
            "output": "/tmp/export",
            "manifest": "/tmp/export/export_manifest.json",
            "validation": {"valid": True, "warnings": [], "errors": []},
            "smoke_test": {"status": "not_requested"},
            "host_smoke_test": {"status": "failed", "stderr": "boom"},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "effect.vfx.json"
            run_cli("create", str(path))
            with patch("vfxforge.cli.export_file", return_value=payload):
                code, result = run_cli("export", str(path), "--output", str(Path(tmp) / "out"), "--mode", "library")
            self.assertNotEqual(code, 0)
            self.assertFalse(result["success"])
            self.assertEqual(result["errors"][0]["code"], "HOST_LIBRARY_SMOKE_FAILED")


class ExportIdempotencyTests(unittest.TestCase):
    def test_repeat_export_does_not_keep_stale_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = default_document("export_one", "One", 1.0)
            first_path = root / "one.vfx.json"
            write_document(first_path, first)
            output = root / "out"
            export_document(first, first_path, output, run_smoke_test=False)
            stale = output / "textures" / "stale.png"
            stale.parent.mkdir(parents=True, exist_ok=True)
            stale.write_bytes(b"stale")
            (output / "project.godot").write_text("stale-project\n", encoding="utf-8")
            second = default_document("export_one", "Two", 1.0)
            export_document(second, first_path, output, run_smoke_test=False, mode="library", resource_root="res://generated/vfx/export_one")
            self.assertFalse(stale.exists())
            self.assertFalse((output / "project.godot").exists())
            self.assertTrue((output / "effect.tscn").exists())


class ChildEffectSafetyTests(unittest.TestCase):
    def test_nested_dependency_cycle_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            documents = {
                "root_effect": "b_effect",
                "b_effect": "c_effect",
                "c_effect": "b_effect",
            }
            for effect_id, child_id in documents.items():
                document = default_document(effect_id, effect_id, 1.0)
                document["layers"].append(make_layer("child_effect", f"to_{child_id}"))
                document["layers"][0]["properties"]["effect_id"] = child_id
                write_document(root / f"{effect_id}.vfx.json", document)
            validation = validate_document(json.loads((root / "root_effect.vfx.json").read_text(encoding="utf-8")), root)
            self.assertFalse(validation["valid"])
            self.assertIn("CHILD_EFFECT_CYCLE", {item["code"] for item in validation["errors"]})

    def test_child_path_traversal_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outside = Path(tmp) / ".." / f"outside-{Path(tmp).name}.vfx.json"
            write_document(outside, default_document("outside_effect", "Outside", 1.0))
            document = default_document("inside_effect", "Inside", 1.0)
            document["layers"].append(make_layer("child_effect", "escaped"))
            document["layers"][0]["properties"]["effect_id"] = "../outside.vfx.json"
            inside_path = root / "inside_effect.vfx.json"
            write_document(inside_path, document)
            validation = validate_document(document, root, document_path=inside_path)
            self.assertFalse(validation["valid"])
            self.assertIn("CHILD_EFFECT_OUTSIDE_PROJECT", {item["code"] for item in validation["errors"]})
            if outside.exists():
                outside.unlink()

    def test_ambiguous_stable_effect_id_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fire = default_document("spark", "Fire Spark", 1.0)
            ice = default_document("spark", "Ice Spark", 1.0)
            write_document(root / "effects" / "fire" / "spark.vfx.json", fire)
            write_document(root / "effects" / "ice" / "spark.vfx.json", ice)
            parent = default_document("parent_effect", "Parent", 1.0)
            parent["layers"].append(make_layer("child_effect", "child"))
            parent["layers"][0]["properties"]["effect_id"] = "spark"
            parent_path = root / "parent.vfx.json"
            write_document(parent_path, parent)
            validation = validate_document(parent, root, document_path=parent_path)
            self.assertFalse(validation["valid"])
            self.assertIn("AMBIGUOUS_EFFECT_ID", {item["code"] for item in validation["errors"]})

    def test_nested_relative_child_reference_resolves_across_sibling_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shared_dir = root / "effects" / "shared"
            attack_dir = root / "effects" / "attack"
            shared_dir.mkdir(parents=True)
            attack_dir.mkdir(parents=True)
            spark = default_document("shared_spark", "Shared Spark", 1.0)
            write_document(shared_dir / "spark.vfx.json", spark)
            parent = default_document("attack_parent", "Attack Parent", 1.0)
            parent["layers"].append(make_layer("child_effect", "spark_child"))
            parent["layers"][0]["properties"]["effect_id"] = "../shared/spark.vfx.json"
            parent_path = attack_dir / "parent.vfx.json"
            write_document(parent_path, parent)
            validation = validate_document(parent, root, document_path=parent_path)
            self.assertTrue(validation["valid"], msg=validation["errors"])

    def test_res_protocol_child_reference_resolves_from_project_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shared_dir = root / "effects" / "shared"
            attack_dir = root / "effects" / "attack"
            shared_dir.mkdir(parents=True)
            attack_dir.mkdir(parents=True)
            spark = default_document("shared_spark", "Shared Spark", 1.0)
            write_document(shared_dir / "spark.vfx.json", spark)
            parent = default_document("attack_parent", "Attack Parent", 1.0)
            parent["layers"].append(make_layer("child_effect", "spark_child"))
            parent["layers"][0]["properties"]["effect_id"] = "res://effects/shared/spark.vfx.json"
            parent_path = attack_dir / "parent.vfx.json"
            write_document(parent_path, parent)
            validation = validate_document(parent, root, document_path=parent_path)
            self.assertTrue(validation["valid"], msg=validation["errors"])

    def test_dependencies_effects_resolve_relative_to_document_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shared_dir = root / "effects" / "shared"
            attack_dir = root / "effects" / "attack"
            shared_dir.mkdir(parents=True)
            attack_dir.mkdir(parents=True)
            spark = default_document("shared_spark", "Shared Spark", 1.0)
            write_document(shared_dir / "spark.vfx.json", spark)
            parent = default_document("attack_parent", "Attack Parent", 1.0)
            parent.setdefault("dependencies", {}).setdefault("effects", []).append("../shared/spark.vfx.json")
            parent_path = attack_dir / "parent.vfx.json"
            write_document(parent_path, parent)
            validation = validate_document(parent, root, document_path=parent_path)
            self.assertTrue(validation["valid"], msg=validation["errors"])

    def test_production_directory_source_remains_eligible_for_stable_id_lookup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            production_dir = root / "effects" / "production"
            production_dir.mkdir(parents=True)
            spark = default_document("spark", "Production Spark", 1.0)
            spark_path = production_dir / "spark.vfx.json"
            write_document(spark_path, spark)
            resolved = resolve_effect("spark", document_dir=root, project_root=root)
            self.assertIsNone(resolved.error_code)
            self.assertEqual(resolved.path, spark_path.resolve())

    def test_hex_suffix_source_filename_remains_eligible_for_stable_id_lookup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spark_path = root / "explosion_deadbeef.vfx.json"
            write_document(spark_path, default_document("explosion", "Explosion", 1.0))
            resolved = resolve_effect("explosion", document_dir=root, project_root=root)
            self.assertIsNone(resolved.error_code)
            self.assertEqual(resolved.path, spark_path.resolve())


class PromotionLockTests(unittest.TestCase):
    def test_stale_promotion_lock_is_recovered(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lock_path = Path(tmp) / "effect.promotion.lock"
            lock_path.write_text(json.dumps({"job_id": "dead", "pid": 99999999, "time": 0}) + "\n", encoding="utf-8")
            recovered = acquire_promotion_lock(lock_path, "fresh", timeout_sec=1.0)
            self.assertEqual(recovered, lock_path)
            release_promotion_lock(recovered)

    def test_incomplete_lock_is_not_stolen_while_fresh(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lock_path = Path(tmp) / "effect.promotion.lock"
            lock_path.write_bytes(b"")
            outcome: list[str] = []

            def waiter() -> None:
                try:
                    acquire_promotion_lock(lock_path, "waiter", timeout_sec=0.4)
                    outcome.append("acquired")
                except TimeoutError:
                    outcome.append("timeout")

            thread = threading.Thread(target=waiter)
            thread.start()
            thread.join()
            self.assertEqual(outcome, ["timeout"])
            self.assertTrue(lock_path.exists())


class GeneratorIdentityTests(unittest.TestCase):
    def test_generation_digest(self) -> None:
        request = normalize_request(_read_request("fire_impact.vfxrequest.json"))
        recipe = load_recipe("impact.fire")
        policy = load_policy("default")
        digest_a = generation_digest(request, recipe, policy, tool_revision="aaa", runtime_sha256={"vfx_runtime.gd": "1"})
        digest_b = generation_digest(request, recipe, policy, tool_revision="bbb", runtime_sha256={"vfx_runtime.gd": "1"})
        digest_c = generation_digest(request, recipe, policy, tool_revision="aaa", runtime_sha256={"vfx_runtime.gd": "2"})
        digest_d = generation_digest(request, recipe, policy, tool_revision="aaa", runtime_contract_version=99)
        self.assertNotEqual(digest_a, digest_b)
        self.assertNotEqual(digest_a, digest_c)
        self.assertNotEqual(digest_a, digest_d)
        self.assertEqual(COMPILER_CONTRACT_VERSION, 2)


class RuntimeConformanceTests(unittest.TestCase):
    def test_unknown_emission_shape_blocks_forge(self) -> None:
        request = normalize_request(_read_request("fire_impact.vfxrequest.json"))
        recipe = load_recipe("impact.fire")
        broken = deepcopy(recipe)
        particle = next(layer for layer in broken["document"]["layers"] if layer["type"] == "particle")
        particle["properties"]["emission_shape"] = "hexagon"
        with tempfile.TemporaryDirectory() as tmp:
            with patch("vfxforge.service.pipeline.select_recipe", return_value=(broken, [broken], [])):
                result = forge(_read_request("fire_impact.vfxrequest.json"), policy_id="default", workspace=tmp, export=False)
        self.assertFalse(result["production_ready"])
        error_codes = {item.get("code") for item in result.get("errors", [])}
        self.assertTrue(
            "UNSUPPORTED_RUNTIME_EMISSION_SHAPE" in error_codes
            or "INVALID_EMISSION_SHAPE" in error_codes,
            msg=result.get("errors"),
        )

    def test_every_recipe_compiled_document_matches_runtime_contract(self) -> None:
        policy = load_policy("enigma")
        for recipe_id, request, recipe in iter_recipe_requests():
            document, _ledger = compile_recipe_with_ledger(normalize_request(request), recipe, policy)
            errors = validate_runtime_conformance(document)
            self.assertEqual(errors, [], msg=f"{recipe_id}: {errors}")


    def test_runtime_contract_version_affects_generation_digest(self) -> None:
        request = normalize_request(_read_request("fire_impact.vfxrequest.json"))
        recipe = load_recipe("impact.fire")
        policy = load_policy("default")
        digest_a = generation_digest(request, recipe, policy, runtime_contract_version=1)
        digest_b = generation_digest(request, recipe, policy, runtime_contract_version=2)
        self.assertNotEqual(digest_a, digest_b)

    def test_runtime_contract_version_seven_enforces_conditional_relations(self) -> None:
        self.assertEqual(RUNTIME_CONTRACT_VERSION, 7)
        self.assertIn("flipbook_requires_sprite_texture", RUNTIME_ENFORCED_RELATION_IDS)
        self.assertIn("custom_mesh_disables_primitive_selector", RUNTIME_ENFORCED_RELATION_IDS)
        self.assertIn("quad_ignores_size_z", RUNTIME_ENFORCED_RELATION_IDS)

    def test_sparse_custom_mesh_document_passes_runtime_conformance(self) -> None:
        document = default_document("sparse_mesh_probe", "Sparse Mesh Probe", 1.0)
        layer = make_layer("mesh_effect", "hero")
        properties = dict(layer["properties"])
        properties["mesh_asset"] = "assets/sword.glb"
        del properties["mesh"]
        layer["properties"] = properties
        document["layers"] = [layer]
        runtime_errors = validate_runtime_conformance(document)
        self.assertEqual(runtime_errors, [], msg=runtime_errors)

    def test_runtime_conformance_mirrors_document_mesh_particle_quad_relation(self) -> None:
        document = default_document("quad_size_probe", "Quad Size Probe", 1.0)
        layer = make_layer("mesh_particle", "particles")
        layer["properties"]["mesh"] = "quad"
        layer["properties"]["size"] = [1.0, 1.0, 999.0]
        document["layers"] = [layer]
        with tempfile.TemporaryDirectory() as tmp:
            document_validation = validate_document(document, Path(tmp))
        runtime_errors = validate_runtime_conformance(document)
        self.assertFalse(document_validation["valid"])
        self.assertIn("INVALID_PROPERTY_RELATION", {item["code"] for item in document_validation["errors"]})
        self.assertTrue(
            any(
                item["code"] == "CONDITIONAL_RUNTIME_PROPERTY" and item["relation_id"] == "quad_ignores_size_z"
                for item in runtime_errors
            ),
            msg=runtime_errors,
        )

    def test_malformed_particle_property_returns_structured_runtime_error(self) -> None:
        request = normalize_request(_read_request("fire_impact.vfxrequest.json"))
        recipe = load_recipe("impact.fire")
        broken = deepcopy(recipe)
        particle = next(layer for layer in broken["document"]["layers"] if layer["type"] == "particle")
        particle["properties"]["turbulence"] = "banana"
        with tempfile.TemporaryDirectory() as tmp:
            with patch("vfxforge.service.pipeline.select_recipe", return_value=(broken, [broken], [])):
                result = forge(_read_request("fire_impact.vfxrequest.json"), policy_id="default", workspace=tmp, export=False)
        self.assertFalse(result["production_ready"])
        self.assertEqual(result["status"], ForgeStatus.FAILED.value)
        self.assertTrue(
            any(
                item["code"]
                in {"UNSUPPORTED_RUNTIME_PROPERTY", "INVALID_PROPERTY_TYPE", "NON_FINITE_PROPERTY"}
                for item in result["errors"]
            ),
        )

    def test_plan_rejects_policy_target_mismatch(self) -> None:
        from vfxforge.service.pipeline import plan

        request = _read_request("fire_impact.vfxrequest.json")
        request["context"] = {"target": "enigma", "usage": "normal_combat"}
        result = plan(request, policy_id="default")
        self.assertEqual(result["status"], ForgeStatus.NEEDS_REVIEW.value)
        self.assertTrue(any(item["code"] == "POLICY_TARGET_MISMATCH" for item in result["review_reasons"]))

    def test_invalid_attachment_type_is_rejected(self) -> None:
        from vfxforge.service.request import validate_request

        request = _read_request("trail_weapon.vfxrequest.json")
        request["gameplay"]["attachment"] = 123
        document, errors = validate_request(request)
        self.assertIsNone(document)
        self.assertTrue(any(item["code"] == "INVALID_GAMEPLAY_ATTACHMENT" for item in errors))

    def test_light_material_blend_mode_is_not_production_ready(self) -> None:
        request = normalize_request(_read_request("fire_impact.vfxrequest.json"))
        recipe = load_recipe("impact.fire")
        broken = deepcopy(recipe)
        light = next(layer for layer in broken["document"]["layers"] if layer["type"] == "light")
        light["material"]["blend_mode"] = "multiply"
        with tempfile.TemporaryDirectory() as tmp:
            with patch("vfxforge.service.pipeline.select_recipe", return_value=(broken, [broken], [])):
                result = forge(_read_request("fire_impact.vfxrequest.json"), policy_id="default", workspace=tmp, export=False)
        self.assertFalse(result["production_ready"])
        self.assertTrue(any(item["code"] == "UNSUPPORTED_RUNTIME_MATERIAL" for item in result["errors"]))

    def test_canonical_layer_defaults_pass_strict_and_runtime_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            for layer_type in sorted(RUNTIME_PRODUCTION_LAYER_TYPES):
                layer = make_layer(layer_type, "probe")
                document = default_document(f"probe_{layer_type}", f"Probe {layer_type}", 1.0)
                document["layers"] = [layer]
                path = project / f"{layer_type}.vfx.json"
                write_document(path, document)
                validation = validate_document(document, project, strict=True)
                self.assertTrue(validation["valid"], msg=f"{layer_type}: {validation['errors']}")
                runtime_errors = validate_runtime_conformance(document)
                self.assertEqual(runtime_errors, [], msg=f"{layer_type}: {runtime_errors}")

    def test_whitespace_attachment_is_rejected(self) -> None:
        from vfxforge.service.request import validate_request

        request = _read_request("trail_weapon.vfxrequest.json")
        request["gameplay"]["attachment"] = "   "
        document, errors = validate_request(request)
        self.assertIsNone(document)
        self.assertTrue(any(item["code"] == "INVALID_GAMEPLAY_ATTACHMENT" for item in errors))

    def test_string_boolean_property_is_rejected(self) -> None:
        document = default_document("typed_probe", "Typed Probe", 1.0)
        layer = make_layer("particle", "sparks")
        layer["properties"]["one_shot"] = "false"
        document["layers"] = [layer]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "typed_probe.vfx.json"
            write_document(path, document)
            validation = validate_document(document, Path(tmp), document_path=path)
        self.assertFalse(validation["valid"])
        self.assertIn("INVALID_PROPERTY_TYPE", {item["code"] for item in validation["errors"]})

    def test_non_finite_numeric_property_is_rejected(self) -> None:
        document = default_document("finite_probe", "Finite Probe", 1.0)
        layer = make_layer("light", "glow")
        layer["properties"]["energy"] = float("nan")
        document["layers"] = [layer]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "finite_probe.vfx.json"
            validation = validate_document(document, Path(tmp), document_path=path)
        self.assertFalse(validation["valid"])
        self.assertIn("NON_FINITE_PROPERTY", {item["code"] for item in validation["errors"]})
        with self.assertRaises(ValueError):
            write_document(path, document)

    def test_out_of_range_property_is_rejected(self) -> None:
        document = default_document("range_probe", "Range Probe", 1.0)
        layer = make_layer("light", "glow")
        layer["properties"]["energy"] = -5.0
        document["layers"] = [layer]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "range_probe.vfx.json"
            write_document(path, document)
            validation = validate_document(document, Path(tmp), document_path=path)
        self.assertFalse(validation["valid"])
        self.assertIn("PROPERTY_OUT_OF_RANGE", {item["code"] for item in validation["errors"]})

    def test_flipbook_relation_constraints_are_rejected(self) -> None:
        document = default_document("flipbook_relation_probe", "Flipbook Relation Probe", 1.0)
        layer = make_layer("sprite", "atlas")
        layer["properties"]["flipbook_columns"] = 1
        layer["properties"]["flipbook_rows"] = 1
        layer["properties"]["flipbook_frames"] = 100
        layer["properties"]["flipbook_start_frame"] = 80
        document["layers"] = [layer]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "flipbook_relation_probe.vfx.json"
            write_document(path, document)
            validation = validate_document(document, Path(tmp), document_path=path)
        self.assertFalse(validation["valid"])
        self.assertIn("INVALID_PROPERTY_RELATION", {item["code"] for item in validation["errors"]})

    def test_sprite_flipbook_requires_properties_texture(self) -> None:
        document = default_document("sprite_flipbook_probe", "Sprite Flipbook Probe", 1.0)
        layer = make_layer("sprite", "atlas")
        layer["properties"]["flipbook_frames"] = 4
        document["layers"] = [layer]
        with tempfile.TemporaryDirectory() as tmp:
            validation = validate_document(document, Path(tmp))
        self.assertFalse(validation["valid"])
        self.assertIn("INVALID_PROPERTY_RELATION", {item["code"] for item in validation["errors"]})

    def test_mesh_particle_mesh_sphere_passes_runtime_conformance(self) -> None:
        document = default_document("mesh_particle_sphere", "Mesh Particle Sphere", 1.0)
        layer = make_layer("mesh_particle", "particles")
        layer["properties"]["mesh"] = "sphere"
        document["layers"] = [layer]
        runtime_errors = validate_runtime_conformance(document)
        self.assertEqual(runtime_errors, [], msg=runtime_errors)

    def test_extremely_large_integer_returns_structured_validation_error(self) -> None:
        document = default_document("large_int_probe", "Large Int Probe", 1.0)
        layer = make_layer("trail", "trail")
        layer["properties"]["segments"] = 10**1000
        document["layers"] = [layer]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "large_int_probe.vfx.json"
            validation = validate_document(document, Path(tmp), document_path=path)
        self.assertFalse(validation["valid"])
        self.assertIn("PROPERTY_OUT_OF_RANGE", {item["code"] for item in validation["errors"]})

    def test_huge_duration_does_not_raise_validate_document(self) -> None:
        document = default_document("duration_probe", "Duration Probe", 1.0)
        document["duration"] = 10**1000
        with tempfile.TemporaryDirectory() as tmp:
            validation = validate_document(document, Path(tmp))
        self.assertFalse(validation["valid"])
        self.assertIn("NUMBER_TOO_LARGE", {item["code"] for item in validation["errors"]})

    def test_malformed_particle_amount_does_not_raise_validate_document(self) -> None:
        document = default_document("amount_probe", "Amount Probe", 1.0)
        layer = make_layer("particle", "sparks")
        layer["properties"]["amount"] = "banana"
        document["layers"] = [layer]
        with tempfile.TemporaryDirectory() as tmp:
            validation = validate_document(document, Path(tmp))
        self.assertFalse(validation["valid"])
        self.assertIn("INVALID_PROPERTY_TYPE", {item["code"] for item in validation["errors"]})

    def test_spoofed_provenance_on_ordinary_source_is_rejected(self) -> None:
        document = default_document("spoof_probe", "Spoof Probe", 1.0)
        document["metadata"] = {"vfxforge_provenance": "export"}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "spoof_probe.vfx.json"
            write_document(path, document)
            validation = validate_document(document, Path(tmp), document_path=path)
        self.assertFalse(validation["valid"])
        self.assertIn("RESERVED_METADATA_FIELD", {item["code"] for item in validation["errors"]})

    def test_invalid_metadata_object_is_rejected(self) -> None:
        document = default_document("metadata_probe", "Metadata Probe", 1.0)
        document["metadata"] = "legacy"
        with tempfile.TemporaryDirectory() as tmp:
            validation = validate_document(document, Path(tmp))
        self.assertFalse(validation["valid"])
        self.assertIn("INVALID_METADATA", {item["code"] for item in validation["errors"]})

    def test_reserved_metadata_provenance_is_rejected_on_source_documents(self) -> None:
        document = default_document("reserved_probe", "Reserved Probe", 1.0)
        document["metadata"] = {"vfxforge_provenance": "export"}
        with tempfile.TemporaryDirectory() as tmp:
            validation = validate_document(document, Path(tmp), document_role="source")
        self.assertFalse(validation["valid"])
        self.assertIn("RESERVED_METADATA_FIELD", {item["code"] for item in validation["errors"]})

    def test_non_finite_object_payload_is_rejected(self) -> None:
        document = default_document("payload_probe", "Payload Probe", 1.0)
        layer = make_layer("event_marker", "marker")
        layer["properties"]["payload"] = {"damage": float("nan")}
        document["layers"] = [layer]
        with tempfile.TemporaryDirectory() as tmp:
            validation = validate_document(document, Path(tmp))
        self.assertFalse(validation["valid"])
        self.assertIn("NON_FINITE_PROPERTY", {item["code"] for item in validation["errors"]})

    def test_vector_non_finite_component_reports_non_finite_property(self) -> None:
        document = default_document("vector_probe", "Vector Probe", 1.0)
        layer = make_layer("mesh_particle", "particles")
        layer["properties"]["size"] = [1.0, float("nan"), 1.0]
        document["layers"] = [layer]
        with tempfile.TemporaryDirectory() as tmp:
            validation = validate_document(document, Path(tmp))
        self.assertFalse(validation["valid"])
        self.assertIn("NON_FINITE_PROPERTY", {item["code"] for item in validation["errors"]})

    def test_particle_billboard_enum_is_validated_even_when_emulated(self) -> None:
        document = default_document("billboard_probe", "Billboard Probe", 1.0)
        layer = make_layer("particle", "sparks")
        layer["material"]["billboard"] = "banana"
        document["layers"] = [layer]
        errors = validate_runtime_conformance(document)
        self.assertTrue(any(item["code"] == "UNSUPPORTED_RUNTIME_MATERIAL" for item in errors))


class CapabilitiesDiscoveryTests(unittest.TestCase):
    def test_agent_can_discover_enigma_requirements_from_json(self) -> None:
        payload = capabilities("enigma")
        self.assertEqual(payload["policy"]["required_export_mode"], "library")
        self.assertEqual(payload["policy"]["runtime_gate"], "host_project")
        self.assertTrue(payload["policy"]["require_export_for_production"])
        boss = next(item for item in payload["recipes"] if item["id"] == "boss.line_sweep")
        self.assertIn("gameplay.tell_ms", boss["required"])
        self.assertTrue(boss["unsupported_parameters_are_errors"])
        self.assertEqual(payload["capabilities_version"], 6)
        self.assertIn("reference_semantics", payload)
        self.assertIn("field_specs", payload)
        self.assertIn("property_relations", payload)
        self.assertIn("flipbook_requires_sprite_texture", {item["id"] for item in payload["property_relations"]["sprite"]})
        self.assertIn("flipbook_frames_capacity", {item["id"] for item in payload["property_relations"]["sprite"]})
        self.assertIn("one_shot", payload["field_specs"]["layers"]["particle"]["properties"])
        self.assertIn("request_contract", payload)
        self.assertIn("target_policy_bindings", payload)
        self.assertEqual(payload["target_policy_bindings"]["enigma"], "enigma")
        self.assertIsNone(payload["target_policy_bindings"]["generic"])
        self.assertIn("layer_support", payload)
        self.assertIn("mesh_particle", payload["runtime"]["layers"])
        self.assertIn("schema_authorable_properties", payload["runtime"]["layers"]["mesh_particle"])
        self.assertIn("rotation_speed", payload["runtime"]["layers"]["mesh_particle"]["schema_authorable_properties"])
        self.assertNotIn("fixed_fps", payload["runtime"]["layers"]["mesh_particle"]["properties"])
        self.assertIn("audio_marker", payload["layer_support"]["schema_only_layer_types"])
        radius = payload["request_contract"]["gameplay"]["radius_tiles"]
        self.assertEqual(radius["minimum"], 0.25)
        self.assertEqual(radius["maximum"], 64.0)
        self.assertIn("required", payload["request_contract"])
        self.assertIn("recipe_templates", payload)
        self.assertIn("runtime", payload)
        self.assertGreaterEqual(len(payload["recipe_templates"]), 15)
        code, result = run_cli("capabilities", "--policy", "enigma")
        self.assertEqual(code, 0)
        self.assertEqual(result["data"]["policy"]["required_export_mode"], "library")


class ManagedMutationTests(unittest.TestCase):
    def test_create_force_and_add_texture_refuse_managed_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = forge(_read_request("fire_impact.vfxrequest.json"), policy_id="default", workspace=tmp, export=False)
            production = Path(result["artifacts"]["production"])
            documents = list(production.glob("*.vfx.json"))
            self.assertTrue(documents)
            target = documents[0]
            code, created = run_cli("create", str(target), "--force")
            self.assertNotEqual(code, 0)
            self.assertEqual(created["errors"][0]["code"], "MANAGED_DOCUMENT")
            source = Path(tmp) / "probe.png"
            source.write_bytes(b"\x89PNG\r\n")
            before = list((target.parent / "assets" / "textures").glob("*")) if (target.parent / "assets" / "textures").exists() else []
            code, added = run_cli("add-texture", str(target), "--source", str(source))
            self.assertNotEqual(code, 0)
            self.assertEqual(added["errors"][0]["code"], "MANAGED_DOCUMENT")
            after = list((target.parent / "assets" / "textures").glob("*")) if (target.parent / "assets" / "textures").exists() else []
            self.assertEqual(before, after)


class PackagedResourceTests(unittest.TestCase):
    def tearDown(self) -> None:
        resources.install_root.cache_clear()

    def test_target_layout_resolves_host_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp)
            share = site / "share" / "vfxforge"
            (share / "recipes").mkdir(parents=True)
            (share / "policies").mkdir()
            host = share / "godot" / "host_smoke"
            host.mkdir(parents=True)
            (host / "host_smoke.gd").write_text("extends Node\n", encoding="utf-8")
            (host / "project.godot").write_text("[application]\n", encoding="utf-8")
            fake_pkg = site / "vfxforge"
            fake_pkg.mkdir()
            resources.install_root.cache_clear()
            with patch.object(resources, "PKG_ROOT", fake_pkg):
                self.assertEqual(resources.install_root(), share)
                self.assertEqual(resources.host_smoke_dir(), host)


class SchemaTypoTests(unittest.TestCase):
    def test_policy_and_recipe_typos_fail_schema(self) -> None:
        from vfxforge.schema_validate import SchemaValidationError, validate_instance

        policy = load_policy("enigma")
        policy["defaults"]["max_particels"] = 4000
        with self.assertRaises(SchemaValidationError):
            validate_instance(policy, "vfx.policy.schema.json")
        recipe = load_recipe("boss.line_sweep")
        recipe["priorityy"] = 1
        with self.assertRaises(SchemaValidationError):
            validate_instance(recipe, "vfx.recipe.schema.json")


if __name__ == "__main__":
    unittest.main()
