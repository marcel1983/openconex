# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""The documentation covers what the program offers (docs/tecnico/08-mantener-documentacion.md)."""

import argparse
import re
from pathlib import Path

import pytest

from openconex.cli import build_parser
from openconex.core.materials import BOLTS, ELECTRODES, STEELS
from openconex.i18n import catalog
from openconex.io import project

ROOT = Path(__file__).parents[1]
DOCS = ROOT / "docs"
USER = DOCS / "usuario"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_every_check_is_in_the_catalog():
    text = _text(DOCS / "tecnico" / "04-verificaciones.md")
    ids = [key.removeprefix("check.") for key in catalog("es") if key.startswith("check.")]
    assert ids
    missing = [i for i in ids if f"`{i}`" not in text]
    assert not missing, f"checks missing in docs/tecnico/04-verificaciones.md: {missing}"


def _commands():
    parser = build_parser()
    sub = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    for name, command in sub.choices.items():
        options = [s for a in command._actions for s in a.option_strings
                   if s.startswith("--") and s != "--help"]
        yield name, options


def test_every_command_and_option_is_documented():
    text = _text(USER / "04-comandos.md")
    missing = []
    for name, options in _commands():
        if f"openconex {name}" not in text:
            missing.append(name)
        missing += [f"{name} {o}" for o in options if f"`{o}" not in text]
    assert not missing, f"missing in docs/usuario/04-comandos.md: {missing}"


MODELS = [project.ProjectInfo, project.MaterialInput, project.BasePlateInput,
          project.WSectionInput, project.HSSSectionInput, project.ShearLugInput,
          project.LoadCaseInput, project.CombinationOptions, project.CustomCombinationInput]


@pytest.mark.parametrize("model", MODELS, ids=lambda m: m.__name__)
def test_every_project_field_is_documented(model):
    text = _text(USER / "03-proyecto.md")
    missing = [f for f in model.model_fields if f"`{f}`" not in text]
    assert not missing, f"{model.__name__} fields missing in docs/usuario/03-proyecto.md: {missing}"


def test_every_example_is_cited():
    text = "".join(_text(p) for p in USER.glob("*.md"))
    missing = [p.name for p in (ROOT / "examples").glob("*.ocnx") if p.name not in text]
    assert not missing, f"examples not cited in docs/usuario: {missing}"


def test_every_material_is_listed():
    text = _text(USER / "07-unidades-materiales.md")
    missing = [g for g in (*STEELS, *BOLTS, *ELECTRODES) if f"`{g}`" not in text]
    assert not missing, f"materials missing in docs/usuario/07-unidades-materiales.md: {missing}"


LINK = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")


@pytest.mark.parametrize("page", [*sorted(DOCS.rglob("*.md")), ROOT / "README.md"],
                         ids=lambda p: str(p.relative_to(ROOT)))
def test_relative_links_resolve(page):
    broken = [target for target in LINK.findall(_text(page))
              if "://" not in target and not (page.parent / target).exists()]
    assert not broken, f"broken links in {page.relative_to(ROOT)}: {broken}"
