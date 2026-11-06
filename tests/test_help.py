# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Completeness of the help registry and its generated reference page."""

from pathlib import Path

from openconex.help import (
    HELP_ITEMS,
    render_base_help_markdown,
    render_shear_help_markdown,
    shear_fields,
    shear_menus,
)
from openconex.help_base import BASE_ITEMS
from openconex.io.project import (
    BasePlateInput,
    BoltInput,
    CopeInput,
    DoublerPlateInput,
    EmbeddedBaseInput,
    EmbeddedRebarInput,
    LongitudinalStiffenerInput,
    PedestalRebarInput,
    ReinforcementInput,
    ShearConnectionInput,
    ShearLugInput,
    WeakBaseInput,
)

ROOT = Path(__file__).parents[1]
DOC = ROOT / "docs" / "usuario" / "10-referencia-conexion-corte.md"
BASE_DOC = ROOT / "docs" / "usuario" / "11-referencia-placa-base.md"


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
    assert BASE_DOC.read_text(encoding="utf-8") == render_base_help_markdown()


def test_every_base_plate_field_has_help():
    keys = set(BasePlateInput.model_fields)
    for model, prefix in (
            (PedestalRebarInput, "pedestal_rebars"),
            (ReinforcementInput, "reinforcement"),
            (WeakBaseInput, "weak_base"),
            (EmbeddedBaseInput, "embedded_base"),
            (ShearLugInput, "shear_lug")):
        keys |= {f"{prefix}.{name}" for name in model.model_fields}
    keys |= {f"embedded_base.rebar_top.{name}" for name in EmbeddedRebarInput.model_fields}
    keys |= {f"embedded_base.rebar_bottom.{name}" for name in EmbeddedRebarInput.model_fields}
    keys |= {f"edges.{name}" for name in ("left", "right", "bottom", "top")}
    missing = sorted(keys - set(HELP_ITEMS))
    assert not missing, f"base fields without help: {missing}"


def test_main_menu_help():
    keys = {item.key for item in HELP_ITEMS.values()}
    assert {"main.file.open", "main.calc.run", "main.export.dxf",
            "main.help.fields", "base.ui.geometry"} <= keys


def test_base_fields_are_in_the_document():
    text = BASE_DOC.read_text(encoding="utf-8")
    for item in BASE_ITEMS.values():
        assert f"`{item.key}`" in text, item.key


def test_all_fields_are_in_the_document():
    text = DOC.read_text(encoding="utf-8")
    for item in shear_fields():
        assert f"`{item.key}`" in text, item.key


def test_every_cli_argument_has_help():
    from openconex.cli import build_parser

    parser = build_parser()
    for action in parser._actions:
        if action.dest == "help" or action.__class__.__name__ == "_SubParsersAction":
            continue
        assert action.help, action.dest
    sub = next(action for action in parser._actions
               if action.__class__.__name__ == "_SubParsersAction")
    for name, command in sub.choices.items():
        for action in command._actions:
            if action.dest == "help":
                continue
            assert action.help, f"{name}: {action.dest}"
