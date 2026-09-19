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
            self.assertEqual(exported["copied_effects"], ["effects/child.vfx.json"])
            self.assertTrue((output / "effects/child.vfx.json").exists())
            exported_doc = (output / "document.vfx.json").read_text(encoding="utf-8")
            self.assertIn('"effect_id": "effects/child.vfx.json"', exported_doc)
