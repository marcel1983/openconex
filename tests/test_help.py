# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Completeness of the help registry and its generated reference page."""

from pathlib import Path

from openconex.help import (
    HELP_ITEMS,
    help_text,
    render_base_help_markdown,
    render_shear_help_markdown,
    shear_fields,
    shear_menus,
)
from openconex.help_base import BASE_ITEMS
from openconex.help_core import HelpItem, help_catalog
from openconex.io.project import (
    BasePlateInput,
    BoltInput,
    CopeInput,
    DoublerPlateInput,
    EmbeddedBaseInput,
    EmbeddedRebarInput,
    LongitudinalStiffenerInput,
    PedestalInput,
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
            (PedestalInput, "pedestal"),
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


def test_help_catalog_entries_are_unique_and_complete():
    """Every entry of i18n/help.es.toml has a distinct key and only HelpItem fields."""
    catalog = help_catalog()
    entries = [entry for section in ("shear", "base") for part in catalog[section].values()
               for entry in part]
    keys = [entry["key"] for entry in entries]
    assert len(keys) == len(set(keys)), "repeated help keys"
    assert set(keys) == set(HELP_ITEMS)
    fields = set(HelpItem.__dataclass_fields__)
    for entry in entries:
        assert set(entry) <= fields, entry["key"]
    for page in catalog["pages"].values():
        assert page["groups"] and page["reading"]


def test_tooltip_has_the_three_answers():
    item = HELP_ITEMS["beam"]
    text = help_text("beam")
    assert text.splitlines()[0] == item.what
    assert item.how in text and item.effect in text


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
