from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
CLI = REPO / "bin" / "vfxforge"
MODEL_FIXTURE = REPO / "tests" / "fixtures" / "models" / "forge_totem.obj"
E2E_DIR = REPO / "tests" / "e2e"


def godot_command() -> str | None:
    configured = os.environ.get("VFXFORGE_GODOT")
    if configured and Path(configured).is_file():
        return configured
    for candidate in ("godot", "godot4"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    bundled = REPO / ".tools" / "godot" / "Godot_v4.7.2-stable_linux.x86_64"
    return str(bundled) if bundled.is_file() else None


def run_cli(*arguments: str, cwd: Path | None = None) -> dict:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(REPO)
    completed = subprocess.run(
        [str(CLI), *arguments, "--json"],
        cwd=str(cwd or REPO),
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"CLI did not return JSON. stdout={completed.stdout!r} stderr={completed.stderr!r}") from exc
    payload["_exit_code"] = completed.returncode
    return payload


def run_godot(command: str, *arguments: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [command, *arguments],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


class UserFacingE2ETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.godot = godot_command()
        if cls.godot is not None:
            imported = run_godot(cls.godot, "--headless", "--editor", "--path", str(REPO), "--quit", cwd=REPO)
            combined = imported.stdout + imported.stderr
            if imported.returncode != 0 or "SCRIPT ERROR" in combined or "Parse Error" in combined:
                raise AssertionError(f"Godot project import failed:\n{combined[-6000:]}")

    def test_real_user_cli_workflow_with_mesh_export(self) -> None:
        self.assertTrue(MODEL_FIXTURE.is_file())
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            source = workspace / "forge_totem.vfx.json"
            preview = workspace / "forge_totem.png"
            export_dir = workspace / "ForgeTotem"

            created = run_cli("create", str(source), "--name", "Forge Totem", "--duration", "1.5", "--seed", "9001")
            self.assertTrue(created["success"], created)
            added_mesh = run_cli("add-mesh", str(source), "--source", str(MODEL_FIXTURE))
            self.assertTrue(added_mesh["success"], added_mesh)
            self.assertTrue((workspace / "assets/models/forge_totem.obj").is_file())
            self.assertEqual(added_mesh["data"]["reference"], "assets/models/forge_totem.obj")

            for layer_type, layer_id in (("mesh_effect", "totem"), ("mesh_particle", "totem_particles")):
                added = run_cli("add-layer", str(source), "--type", layer_type, "--id", layer_id)
                self.assertTrue(added["success"], added)
            changed = run_cli(
                "set",
                str(source),
                "layers.totem.properties.mesh_asset=assets/models/forge_totem.obj",
                "layers.totem.properties.size=[1.2,1.2,1.2]",
                "layers.totem_particles.properties.mesh_asset=assets/models/forge_totem.obj",
                "layers.totem_particles.properties.amount=3",
                "layers.totem_particles.properties.lifetime=0.9",
            )
            self.assertTrue(changed["success"], changed)
            event = run_cli("add-event", str(source), "--event-id", "impact", "--time", "0.42", "--data", '{"camera_shake":0.25}')
            self.assertTrue(event["success"], event)

            layers = run_cli("list-layers", str(source))
            self.assertTrue(layers["success"], layers)
            self.assertEqual([item["id"] for item in layers["data"]["layers"]], ["totem", "totem_particles"])
            inspected = run_cli("inspect", str(source))
            self.assertTrue(inspected["success"], inspected)
            document = inspected["data"]["document"]
            self.assertEqual(document["dependencies"]["meshes"], ["assets/models/forge_totem.obj"])
            self.assertEqual(document["layers"][0]["properties"]["mesh_asset"], "assets/models/forge_totem.obj")

            validated = run_cli("validate", str(source), "--budget", "Medium")
            self.assertTrue(validated["success"], validated)
            self.assertEqual(validated["errors"], [])
            self.assertGreater(validated["items"][0]["metrics"]["triangles_estimate"], 0)

            rendered = run_cli("render-preview", str(source), "--time", "0.55", "--camera", "mmo", "--output", str(preview))
            self.assertTrue(rendered["success"], rendered)
            self.assertTrue(preview.is_file())
            self.assertGreater(preview.stat().st_size, 1000)
            preview_hash = hashlib.sha256(preview.read_bytes()).hexdigest()
            rendered_again = run_cli("render-preview", str(source), "--time", "0.55", "--camera", "mmo", "--output", str(workspace / "again.png"))
            self.assertTrue(rendered_again["success"], rendered_again)
            self.assertEqual(preview_hash, hashlib.sha256((workspace / "again.png").read_bytes()).hexdigest())

            exported = run_cli("export", str(source), "--output", str(export_dir))
            self.assertTrue(exported["success"], exported)
            self.assertTrue((export_dir / "effect.tscn").is_file())
            self.assertTrue((export_dir / "document.vfx.json").is_file())
            self.assertTrue((export_dir / "meshes/forge_totem.obj").is_file())
            manifest = json.loads((export_dir / "export_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["copied_meshes"], ["meshes/forge_totem.obj"])
            self.assertIn("meshes/forge_totem.obj", [entry["path"] for entry in manifest["files"]])
            exported_document_text = (export_dir / "document.vfx.json").read_text(encoding="utf-8")
            self.assertNotIn(str(workspace), exported_document_text)

            if self.godot is not None:
                imported = run_godot(self.godot, "--headless", "--editor", "--path", str(export_dir), "--quit", cwd=export_dir)
                self.assertEqual(imported.returncode, 0, imported.stdout + imported.stderr)
                smoke_script = export_dir / "user_e2e_smoke.gd"
                shutil.copy2(E2E_DIR / "export_runtime_smoke.gd", smoke_script)
                smoke = run_godot(self.godot, "--headless", "--path", str(export_dir), "--script", "res://user_e2e_smoke.gd", cwd=export_dir)
                self.assertEqual(smoke.returncode, 0, smoke.stdout + smoke.stderr)
                self.assertIn("USER_E2E_EXPORT_PASS", smoke.stdout)
                self.assertNotIn("SCRIPT ERROR", smoke.stdout + smoke.stderr)
                self.assertNotIn("ERROR:", smoke.stdout + smoke.stderr)

    def test_invalid_mesh_is_actionable_and_does_not_overwrite_project(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "safe_effect.vfx.json"
            self.assertTrue(run_cli("create", str(source))["success"])
            self.assertTrue(run_cli("add-layer", str(source), "--type", "mesh_effect", "--id", "totem")["success"])
            failed = run_cli("set", str(source), "layers.totem.properties.mesh_asset=assets/models/missing.obj")
            self.assertFalse(failed["success"])
            self.assertEqual(failed["errors"][0]["code"], "MISSING_MESH")
            validated = run_cli("validate", str(source))
            self.assertTrue(validated["success"], validated)
            self.assertEqual(validated["items"][0]["document_id"], "safe_effect")

    @unittest.skipUnless(godot_command() is not None, "Godot 4.x is required for the GUI E2E")
    def test_gui_user_workflow_uses_same_canonical_mesh_document(self) -> None:
        assert self.godot is not None
        result = run_godot(
            self.godot,
            "--headless",
            "--path",
            str(REPO),
            "--script",
            "res://tests/e2e/gui_user_smoke.gd",
            cwd=REPO,
        )
        combined = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, combined[-10000:])
        self.assertIn("USER_E2E_GUI_PASS", result.stdout)
        self.assertNotIn("SCRIPT ERROR", combined)
        self.assertNotIn("Parse Error", combined)
        self.assertNotIn("ERROR:", combined)


if __name__ == "__main__":
    unittest.main()
