#!/usr/bin/env python3
"""Data-driven coverage for every advertised service recipe."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from vfxforge.service.compiler import compile_recipe
from vfxforge.service.matrix import assert_request_selects_recipe, iter_recipe_requests, uncovered_recipes
from vfxforge.service.pipeline import validate_compiled_effect
from vfxforge.service.policy import load_policy
from vfxforge.service.preview_suite import render_preview_suite
from vfxforge.service.request import normalize_request


class RecipeMatrixTests(unittest.TestCase):
    def test_every_recipe_has_canonical_request(self) -> None:
        self.assertEqual(uncovered_recipes(), [])

    def test_every_recipe_selects_compiles_validates_and_previews(self) -> None:
        policy = load_policy("default")
        for recipe_id, raw_request, recipe in iter_recipe_requests():
            with self.subTest(recipe_id=recipe_id):
                assert_request_selects_recipe(raw_request, recipe_id)
                request = normalize_request(raw_request)
                document = compile_recipe(request, recipe, policy)
                usage = request.get("context", {}).get("usage", "normal_combat")
                with tempfile.TemporaryDirectory() as tmp:
                    validation = validate_compiled_effect(document, policy, usage, tmp)
                    self.assertTrue(validation["valid"], validation.get("errors"))
                    previews = render_preview_suite(document, Path(tmp) / "previews", ["mmo"])
                    self.assertTrue(Path(previews["manifest"]).exists())
                    self.assertTrue(previews.get("contact_sheet"))
