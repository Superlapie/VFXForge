from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from vfxforge.exporter import export_document
from vfxforge.model import write_document
from vfxforge.presets import make_preset
from vfxforge.schema import default_document, make_layer
from vfxforge.renderer import render_preview


class RendererExportTests(unittest.TestCase):
    def test_preview_is_deterministic(self) -> None:
        document = make_preset("arcane_impact")
        with tempfile.TemporaryDirectory() as temporary:
            first = Path(temporary) / "first.png"
            second = Path(temporary) / "second.png"
            render_preview(document, first, time=0.45)
            render_preview(document, second, time=0.45)
            digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(digest(first), digest(second))
            self.assertGreater(first.stat().st_size, 1000)

    def test_export_manifest_and_scene_exist(self) -> None:
        document = make_preset("lightning_beam")
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "lightning_beam.vfx.json"
            output = Path(temporary) / "export"
            write_document(source, document)
            exported = export_document(document, source, output, run_smoke_test=False)
            self.assertTrue((output / "effect.tscn").exists())
            self.assertTrue((output / "effect.gd").exists())
            self.assertTrue((output / "vfx_runtime.gd").exists())
            self.assertTrue((output / "export_manifest.json").exists())
            self.assertEqual(exported["smoke_test"]["status"], "not_requested")

    def test_child_effects_are_copied_with_relative_references(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            child = make_preset("dust_burst")
            child_path = root / "child.vfx.json"
            write_document(child_path, child)
            parent = default_document("parent_effect", "Parent", 1.0)
            child_layer = make_layer("child_effect", "child")
            child_layer["properties"]["effect_id"] = "dust_burst"
            parent["layers"].append(child_layer)
            parent_path = root / "parent.vfx.json"
            write_document(parent_path, parent)
            output = root / "export"
            exported = export_document(parent, parent_path, output, run_smoke_test=False)
            self.assertEqual(len(exported["copied_effects"]), 1)
            self.assertTrue(exported["copied_effects"][0].startswith("effects/child_"))
            self.assertTrue(exported["copied_effects"][0].endswith(".vfx.json"))
            exported_child = output / exported["copied_effects"][0]
            self.assertTrue(exported_child.is_file())
            exported_doc = (output / "document.vfx.json").read_text(encoding="utf-8")
            self.assertIn(f'"effect_id": "{exported["copied_effects"][0]}"', exported_doc)

    def test_nested_child_effect_resolves_relative_to_parent_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            attack_dir = root / "effects" / "attack"
            attack_dir.mkdir(parents=True)
            spark = make_preset("dust_burst")
            spark["id"] = "attack_spark"
            spark_path = attack_dir / "spark.vfx.json"
            write_document(spark_path, spark)
            parent = default_document("attack_parent", "Attack Parent", 1.0)
            child_layer = make_layer("child_effect", "spark_child")
            child_layer["properties"]["effect_id"] = "spark.vfx.json"
            parent["layers"].append(child_layer)
            parent_path = attack_dir / "parent.vfx.json"
            write_document(parent_path, parent)
            output = root / "export"
            exported = export_document(parent, parent_path, output, run_smoke_test=False)
            self.assertEqual(len(exported["copied_effects"]), 1)
            exported_doc = (output / "document.vfx.json").read_text(encoding="utf-8")
            self.assertIn('"effect_id": "effects/spark_', exported_doc)
            self.assertTrue((output / exported["copied_effects"][0]).is_file())

    def test_distinct_child_basenames_do_not_collide_in_export(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fire_dir = root / "effects" / "fire"
            ice_dir = root / "effects" / "ice"
            fire_dir.mkdir(parents=True)
            ice_dir.mkdir(parents=True)
            fire_child = default_document("fire_common", "Fire Common", 1.0)
            ice_child = default_document("ice_common", "Ice Common", 1.0)
            write_document(fire_dir / "common.vfx.json", fire_child)
            write_document(ice_dir / "common.vfx.json", ice_child)
            parent = default_document("dual_parent", "Dual Parent", 1.0)
            fire_layer = make_layer("child_effect", "fire")
            fire_layer["properties"]["effect_id"] = "effects/fire/common.vfx.json"
            ice_layer = make_layer("child_effect", "ice")
            ice_layer["properties"]["effect_id"] = "effects/ice/common.vfx.json"
            parent["layers"].extend([fire_layer, ice_layer])
            parent_path = root / "parent.vfx.json"
            write_document(parent_path, parent)
            output = root / "export"
            exported = export_document(parent, parent_path, output, run_smoke_test=False)
            self.assertEqual(len(exported["copied_effects"]), 2)
            self.assertEqual(len(set(exported["copied_effects"])), 2)

    def test_nested_sibling_child_reference_exports_from_shared_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shared_dir = root / "effects" / "shared"
            attack_dir = root / "effects" / "attack"
            shared_dir.mkdir(parents=True)
            attack_dir.mkdir(parents=True)
            spark = make_preset("dust_burst")
            spark["id"] = "shared_spark"
            write_document(shared_dir / "spark.vfx.json", spark)
            parent = default_document("attack_parent", "Attack Parent", 1.0)
            child_layer = make_layer("child_effect", "spark_child")
            child_layer["properties"]["effect_id"] = "../shared/spark.vfx.json"
            parent["layers"].append(child_layer)
            parent_path = attack_dir / "parent.vfx.json"
            write_document(parent_path, parent)
            exported = export_document(parent, parent_path, root / "export", run_smoke_test=False)
            self.assertEqual(len(exported["copied_effects"]), 1)
            self.assertTrue((root / "export" / exported["copied_effects"][0]).is_file())

    def test_stable_id_child_can_be_reexported_without_ambiguity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            child = default_document("spark", "Spark", 1.0)
            write_document(root / "child.vfx.json", child)
            parent = default_document("parent_effect", "Parent", 1.0)
            child_layer = make_layer("child_effect", "spark_child")
            child_layer["properties"]["effect_id"] = "spark"
            parent["layers"].append(child_layer)
            parent_path = root / "parent.vfx.json"
            write_document(parent_path, parent)
            output = root / "export"
            export_document(parent, parent_path, output, run_smoke_test=False)
            export_document(parent, parent_path, output, run_smoke_test=False)
            self.assertTrue((output / "effect.tscn").is_file())
