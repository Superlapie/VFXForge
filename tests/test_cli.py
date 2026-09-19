from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from vfxforge.cli import main
from vfxforge.model import write_document
from vfxforge.schema import default_document


def run_cli(*arguments: str) -> tuple[int, dict]:
    stream = io.StringIO()
    with redirect_stdout(stream):
        code = main(list(arguments) + ["--json"])
    return code, json.loads(stream.getvalue())


class CLITests(unittest.TestCase):
    def test_add_texture_does_not_leave_asset_when_document_stays_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "broken.vfx.json"
            texture = Path(temporary) / "spark.png"
            texture.write_bytes(b"\x89PNG\r\n\x1a\n")
            invalid = default_document("broken", "Broken", -1.0)
            write_document(path, invalid)
            code, added = run_cli("add-texture", str(path), "--source", str(texture))
            self.assertNotEqual(code, 0)
            self.assertFalse(added["success"])
            self.assertFalse((path.parent / "assets" / "textures" / "spark.png").exists())

    def test_create_modify_validate_inspect_and_diff(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "cli_effect.vfx.json"
            code, created = run_cli("create", str(path))
            self.assertEqual(code, 0)
            self.assertTrue(created["success"])
            code, added = run_cli("add-layer", str(path), "--type", "particle", "--id", "sparks")
            self.assertEqual(code, 0)
            self.assertTrue(added["success"])
            code, updated = run_cli("set", str(path), "layers.sparks.amount=96")
            self.assertEqual(code, 0)
            self.assertTrue(updated["success"])
            code, validated = run_cli("validate", str(path))
            self.assertEqual(code, 0)
            self.assertTrue(validated["success"])
            code, inspected = run_cli("inspect", str(path))
            self.assertEqual(code, 0)
            self.assertEqual(inspected["data"]["document"]["layers"][0]["properties"]["amount"], 96)
            second = Path(temporary) / "second.vfx.json"
            run_cli("create", str(second))
            run_cli("set", str(second), "duration=2.0")
            code, diff = run_cli("diff", str(second), str(path))
            self.assertEqual(code, 0)
            self.assertGreater(diff["data"]["change_count"], 0)

    def test_bad_json_is_machine_readable_and_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "broken.vfx.json"
            path.write_text("{not valid", encoding="utf-8")
            code, result = run_cli("validate", str(path))
            self.assertNotEqual(code, 0)
            self.assertFalse(result["success"])
            self.assertEqual(result["errors"][0]["code"], "INVALID_JSON")

    def test_batch_validation_reports_individual_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            run_cli("create", str(directory / "one.vfx.json"))
            run_cli("create", str(directory / "two.vfx.json"))
            code, result = run_cli("validate", str(directory))
            self.assertEqual(code, 0)
            self.assertEqual(len(result["items"]), 2)

    def test_render_and_export_commands_return_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "render_effect.vfx.json"
            run_cli("create", str(path))
            preview = root / "preview.png"
            code, rendered = run_cli("render-preview", str(path), "--output", str(preview))
            self.assertEqual(code, 0)
            self.assertTrue(rendered["success"])
            self.assertTrue(preview.exists())
            export_dir = root / "export"
            code, exported = run_cli("export", str(path), "--output", str(export_dir), "--no-smoke-test")
            self.assertEqual(code, 0)
            self.assertTrue(exported["success"])
            self.assertTrue((export_dir / "effect.tscn").exists())

    def test_bad_arguments_use_usage_exit_code(self) -> None:
        code, result = run_cli("not-a-command")
        self.assertEqual(code, 2)
        self.assertFalse(result["success"])
