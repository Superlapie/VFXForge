from __future__ import annotations

import base64
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from vfxforge.exporter import export_document
from vfxforge.model import write_document
from vfxforge.schema import default_document, make_layer


REPO = Path(__file__).resolve().parents[1]


def godot_command() -> str | None:
    configured = os.environ.get("VFXFORGE_GODOT")
    if configured and Path(configured).exists():
        return configured
    for candidate in ("godot", "godot4"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    bundled = REPO / ".tools" / "godot" / "Godot_v4.7.2-stable_linux.x86_64"
    if bundled.exists():
        return str(bundled)
    return None


SPRITE_PROBE = """extends SceneTree

func _fail(message: String) -> void:
    push_error(message)
    quit(4)

func _initialize() -> void:
    var scene: PackedScene = load("res://effect.tscn")
    if scene == null:
        _fail("Could not load effect.tscn")
        return
    var instance: Node = scene.instantiate()
    root.add_child(instance)
    await process_frame
    await process_frame
    var sprite := instance.get_node_or_null("card") as Sprite3D
    if sprite == null:
        _fail("Expected Sprite3D layer node 'card'")
        return
    if sprite.material_override == null:
        _fail("Expected material_override on textured Sprite3D")
        return
    var material := sprite.material_override as StandardMaterial3D
    if material == null:
        _fail("Expected StandardMaterial3D material_override")
        return
    if not material.vertex_color_use_as_albedo:
        _fail("Expected vertex_color_use_as_albedo on sprite material_override")
        return
    if sprite.billboard != BaseMaterial3D.BILLBOARD_DISABLED:
        _fail("Expected disabled billboard mode from authored material")
        return
    if material.blend_mode != BaseMaterial3D.BLEND_MODE_MUL:
        _fail("Expected multiply blend mode from authored material")
        return
    var base_scale_value: Variant = sprite.get_meta("vfx_base_scale", Vector3.ONE)
    if not base_scale_value is Vector3 or abs((base_scale_value as Vector3).y - 2.5) > 0.05:
        _fail("Expected authored sprite height reflected in base scale, got " + str(base_scale_value))
    if abs(sprite.scale.y - 2.5) > 0.05:
        _fail("Expected authored sprite height reflected in scale.y, got " + str(sprite.scale.y))
        return
    if sprite.modulate.a < 0.99:
        _fail("Expected sprite modulate alpha to remain visible with vertex_color_use_as_albedo")
        return
    quit(0)
"""


SPRITE_PROBE_TEXTURE = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


@unittest.skipUnless(godot_command() is not None, "Godot 4.x is required for runtime behavior probes")
class RuntimeBehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.godot = godot_command()
        assert cls.godot is not None

    def test_textured_sprite_runtime_matches_authored_material_and_size(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            texture_dir = root / "assets" / "textures"
            texture_dir.mkdir(parents=True)
            texture_path = texture_dir / "card.png"
            texture_path.write_bytes(SPRITE_PROBE_TEXTURE)
            document = default_document("sprite_probe", "Sprite Probe", 1.0)
            layer = make_layer("sprite", "card")
            layer["properties"]["texture"] = "assets/textures/card.png"
            layer["properties"]["size"] = [1.0, 2.5]
            layer["material"]["billboard"] = "disabled"
            layer["material"]["blend_mode"] = "multiply"
            layer["curves"]["scale"] = {
                "interpolation": "linear",
                "points": [{"x": 0.0, "y": 1.0}, {"x": 1.0, "y": 1.0}],
            }
            document["layers"] = [layer]
            source = root / "sprite_probe.vfx.json"
            write_document(source, document)
            output = root / "export"
            export_document(document, source, output, run_smoke_test=False)
            import_result = subprocess.run(
                [self.godot, "--headless", "--editor", "--path", str(output), "--quit"],
                cwd=output,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            self.assertEqual(import_result.returncode, 0, msg=(import_result.stdout or "") + (import_result.stderr or ""))
            probe = output / "sprite_probe.gd"
            probe.write_text(SPRITE_PROBE, encoding="utf-8")
            result = subprocess.run(
                [self.godot, "--headless", "--path", str(output), "--script", "res://sprite_probe.gd"],
                cwd=output,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            self.assertEqual(
                result.returncode,
                0,
                msg=(result.stdout or "") + (result.stderr or ""),
            )
