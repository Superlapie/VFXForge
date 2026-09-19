from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from vfxforge.errors import DocumentError
from vfxforge.model import migrate_document, read_document, set_path, write_document
from vfxforge.schema import default_document, make_layer
from vfxforge.validation import validate_document


class ModelTests(unittest.TestCase):
    def test_round_trip_and_layer_path_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "effect.vfx.json"
            document = default_document("round_trip", "Round Trip", 1.25, seed=77)
            document["layers"].append(make_layer("particle", "sparks"))
            set_path(document, "layers.sparks.amount", 64)
            write_document(path, document)
            loaded = read_document(path)
            self.assertEqual(loaded["seed"], 77)
            self.assertEqual(loaded["layers"][0]["properties"]["amount"], 64)
            validation = validate_document(loaded, path.parent)
            self.assertTrue(validation["valid"], validation)

    def test_migrates_legacy_effects_shape(self) -> None:
        migrated = migrate_document(
            {
                "id": "legacy_effect",
                "name": "Legacy",
                "duration": 1,
                "effects": [],
            }
        )
        self.assertEqual(migrated["schema_version"], 1)
        self.assertEqual(migrated["layers"], [])
        self.assertFalse(migrated["loop"])
        self.assertEqual(migrated["seed"], 12345)

    def test_invalid_fields_are_actionable(self) -> None:
        document = default_document("bad_effect", "Bad", 1)
        document["layers"].append(make_layer("particle", "sparks"))
        document["layers"][0]["properties"]["amount"] = -4
        document["layers"][0]["gradient"][1]["position"] = -1
        validation = validate_document(document)
        codes = {item["code"] for item in validation["errors"]}
        self.assertIn("NUMBER_TOO_SMALL", codes)
        self.assertIn("INVALID_GRADIENT_POSITION", codes)

    def test_malformed_containers_return_structured_validation_errors(self) -> None:
        document = default_document("malformed_effect", "Malformed", 1.0)
        document["layers"] = [make_layer("particle", "sparks")]
        document["layers"][0]["properties"] = "not an object"
        document["layers"][0]["material"] = ["not an object"]
        document["budgets"] = "not an object"
        validation = validate_document(document)
        self.assertFalse(validation["valid"])
        codes = {item["code"] for item in validation["errors"]}
        self.assertIn("INVALID_PROPERTIES", codes)
        self.assertIn("INVALID_MATERIAL", codes)

    def test_atomic_write_keeps_backup(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "effect.vfx.json"
            write_document(path, default_document("atomic_effect"))
            updated = default_document("atomic_effect", "Updated")
            write_document(path, updated)
            self.assertTrue(path.with_name(path.name + ".bak").exists())
            self.assertEqual(json.loads(path.read_text())["name"], "Updated")

    def test_child_effect_cycle_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = default_document("first_effect", "First", 1.0)
            first["layers"].append(make_layer("child_effect", "to_second"))
            first["layers"][0]["properties"]["effect_id"] = "second_effect"
            second = default_document("second_effect", "Second", 1.0)
            second["layers"].append(make_layer("child_effect", "to_first"))
            second["layers"][0]["properties"]["effect_id"] = "first_effect"
            first_path = root / "first_effect.vfx.json"
            second_path = root / "second_effect.vfx.json"
            write_document(first_path, first)
            write_document(second_path, second)
            validation = validate_document(first, root)
            self.assertFalse(validation["valid"])
            self.assertIn("CHILD_EFFECT_CYCLE", {item["code"] for item in validation["errors"]})

    def test_future_schema_is_rejected_without_mutation(self) -> None:
        with self.assertRaises(DocumentError) as context:
            migrate_document({"schema_version": 99, "id": "future_effect"})
        self.assertEqual(context.exception.code, "FUTURE_SCHEMA")
