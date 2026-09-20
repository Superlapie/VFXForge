from __future__ import annotations

import base64
import os
import shutil
import struct
import subprocess
import tempfile
import unittest
import zlib
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


def rgba_png(width: int, height: int, rgba: tuple[int, int, int, int] = (255, 64, 64, 255)) -> bytes:
    row = bytes(rgba) * width
    raw = b"".join(b"\x00" + row for _ in range(height))
    compressed = zlib.compress(raw, 9)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", compressed)
        + chunk(b"IEND", b"")
    )


SPRITE_PROBE_TEXTURE = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

SPRITE_FLIPBOOK_PROBE = """extends SceneTree

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
    var sprite := instance.get_node_or_null("flipbook") as Sprite3D
    if sprite == null:
        _fail("Expected Sprite3D layer node 'flipbook'")
        return
    if abs(sprite.pixel_size - 1.0) > 0.05:
        _fail("Expected flipbook frame width to drive pixel_size, got " + str(sprite.pixel_size))
        return
    quit(0)
"""

def mesh_effect_probe(layer_id: str, expected_class: str, size: tuple[float, float, float]) -> str:
    return f"""extends SceneTree

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
    var mesh_node := instance.get_node_or_null("{layer_id}") as MeshInstance3D
    if mesh_node == null or mesh_node.mesh == null:
        _fail("Expected mesh_effect node '{layer_id}'")
        return
    if not mesh_node.mesh is {expected_class}:
        _fail("Expected mesh_effect to instantiate {expected_class}, got " + str(mesh_node.mesh))
        return
    if abs(mesh_node.scale.x - {size[0]}) > 0.05 or abs(mesh_node.scale.y - {size[1]}) > 0.05 or abs(mesh_node.scale.z - {size[2]}) > 0.05:
        _fail("Expected authored mesh_effect size reflected in node scale, got " + str(mesh_node.scale))
        return
    quit(0)
"""


def mesh_particle_probe(layer_id: str, expected_class: str) -> str:
    return f"""extends SceneTree

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
    var particles := instance.get_node_or_null("{layer_id}") as GPUParticles3D
    if particles == null or particles.draw_pass_1 == null:
        _fail("Expected mesh_particle node '{layer_id}'")
        return
    if not particles.draw_pass_1 is {expected_class}:
        _fail("Expected mesh_particle to use {expected_class} draw pass, got " + str(particles.draw_pass_1))
        return
    quit(0)
"""

MESH_EFFECT_PRIMITIVES = (
    ("box", "BoxMesh", (2.0, 3.0, 1.0)),
    ("quad", "QuadMesh", (2.0, 3.0, 1.0)),
    ("sphere", "SphereMesh", (1.0, 1.0, 1.0)),
    ("torus", "TorusMesh", (1.0, 1.0, 1.0)),
)

MESH_PARTICLE_PRIMITIVES = (
    ("box", "BoxMesh"),
    ("quad", "QuadMesh"),
    ("sphere", "SphereMesh"),
    ("torus", "TorusMesh"),
)

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
        return
    if abs(sprite.scale.y - 2.5) > 0.05:
        _fail("Expected authored sprite height reflected in scale.y, got " + str(sprite.scale.y))
        return
    if sprite.modulate.a < 0.99:
        _fail("Expected sprite modulate alpha to remain visible with vertex_color_use_as_albedo")
        return
    quit(0)
"""


@unittest.skipUnless(godot_command() is not None, "Godot 4.x is required for runtime behavior probes")
class RuntimeBehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.godot = godot_command()
        assert cls.godot is not None

    def _run_export_probe(
        self,
        document: dict,
        source_name: str,
        probe_name: str,
        probe_script: str,
        *,
        assets: dict[str, bytes] | None = None,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for relative, data in (assets or {}).items():
                asset_path = root / relative
                asset_path.parent.mkdir(parents=True, exist_ok=True)
                asset_path.write_bytes(data)
            source = root / source_name
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
            probe = output / probe_name
            probe.write_text(probe_script, encoding="utf-8")
            result = subprocess.run(
                [self.godot, "--headless", "--path", str(output), "--script", f"res://{probe_name}"],
                cwd=output,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            self.assertEqual(result.returncode, 0, msg=(result.stdout or "") + (result.stderr or ""))

    def test_textured_sprite_runtime_matches_authored_material_and_size(self) -> None:
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
        self._run_export_probe(
            document,
            "sprite_probe.vfx.json",
            "sprite_probe.gd",
            SPRITE_PROBE,
            assets={"assets/textures/card.png": SPRITE_PROBE_TEXTURE},
        )

    def test_flipbook_sprite_uses_frame_dimensions_for_sizing(self) -> None:
        document = default_document("flipbook_probe", "Flipbook Probe", 1.0)
        layer = make_layer("sprite", "flipbook")
        layer["properties"]["texture"] = "assets/textures/atlas.png"
        layer["properties"]["size"] = [1.0, 1.0]
        layer["properties"]["flipbook_columns"] = 4
        layer["properties"]["flipbook_rows"] = 1
        layer["properties"]["flipbook_frames"] = 4
        layer["curves"]["scale"] = {
            "interpolation": "linear",
            "points": [{"x": 0.0, "y": 1.0}, {"x": 1.0, "y": 1.0}],
        }
        document["layers"] = [layer]
        self._run_export_probe(
            document,
            "flipbook_probe.vfx.json",
            "flipbook_probe.gd",
            SPRITE_FLIPBOOK_PROBE,
            assets={"assets/textures/atlas.png": rgba_png(4, 1)},
        )

    def test_mesh_effect_primitives_match_authored_size_and_class(self) -> None:
        for mesh_name, expected_class, size in MESH_EFFECT_PRIMITIVES:
            with self.subTest(mesh=mesh_name):
                document = default_document(f"mesh_effect_{mesh_name}", f"Mesh Effect {mesh_name}", 1.0)
                layer = make_layer("mesh_effect", "mesh_probe")
                layer["properties"]["mesh"] = mesh_name
                layer["properties"]["size"] = list(size)
                layer["curves"]["scale"] = {
                    "interpolation": "linear",
                    "points": [{"x": 0.0, "y": 1.0}, {"x": 1.0, "y": 1.0}],
                }
                document["layers"] = [layer]
                self._run_export_probe(
                    document,
                    f"mesh_effect_{mesh_name}.vfx.json",
                    f"mesh_effect_{mesh_name}_probe.gd",
                    mesh_effect_probe("mesh_probe", expected_class, size),
                )

    def test_mesh_particle_primitives_use_expected_draw_pass(self) -> None:
        for mesh_name, expected_class in MESH_PARTICLE_PRIMITIVES:
            with self.subTest(mesh=mesh_name):
                document = default_document(f"mesh_particle_{mesh_name}", f"Mesh Particle {mesh_name}", 1.0)
                layer = make_layer("mesh_particle", "mesh_particles")
                if mesh_name != "box":
                    layer["properties"]["mesh"] = mesh_name
                document["layers"] = [layer]
                self._run_export_probe(
                    document,
                    f"mesh_particle_{mesh_name}.vfx.json",
                    f"mesh_particle_{mesh_name}_probe.gd",
                    mesh_particle_probe("mesh_particles", expected_class),
                )
