# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Completeness of the help registry and its generated reference page."""

from pathlib import Path

from openconex.help import HELP_ITEMS, render_shear_help_markdown, shear_fields, shear_menus
from openconex.io.shear_project import (
    BoltInput,
    CopeInput,
    DoublerPlateInput,
    LongitudinalStiffenerInput,
    ShearConnectionInput,
)

ROOT = Path(__file__).parents[1]
DOC = ROOT / "docs" / "usuario" / "10-referencia-conexion-corte.md"


def test_every_shear_field_has_help():
    keys = set(ShearConnectionInput.model_fields)
    nested = {f"bolt.{name}" for name in BoltInput.model_fields}
    nested |= {f"cope.{name}" for name in CopeInput.model_fields}
    nested |= {f"cope.doubler.{name}" for name in DoublerPlateInput.model_fields}
    nested |= {f"cope.stiffener.{name}" for name in LongitudinalStiffenerInput.model_fields}
    missing = sorted((keys | nested) - set(HELP_ITEMS))
    assert not missing, f"fields without help: {missing}"


def test_every_help_item_answers_the_three_questions():
    for item in HELP_ITEMS.values():
        assert item.what.strip(), item.key
        assert item.how.strip(), item.key
        assert item.effect.strip(), item.key


def test_menus_and_checks_have_help():
    keys = {item.key for item in shear_menus()}
    assert {"menu.file.new", "menu.calc.run", "menu.export.html",
            "menu.help.fields", "action.calculate"} <= keys
    checks = {item.key for item in HELP_ITEMS.values() if item.group == "Verificaciones"}
    assert {"checks.summary", "checks.ratio", "checks.status", "checks.clause"} <= checks


def test_generated_document_is_current():
    assert DOC.read_text(encoding="utf-8") == render_shear_help_markdown()


def test_all_fields_are_in_the_document():
    text = DOC.read_text(encoding="utf-8")
    for item in shear_fields():
        assert f"`{item.key}`" in text, item.key
