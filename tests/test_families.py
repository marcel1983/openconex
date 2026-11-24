# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Every registered connection family is complete and reachable."""

import importlib
import json
from pathlib import Path

import pytest

from openconex.cli import build_parser, main
from openconex.families import FAMILIES, KEYS, family, family_of
from openconex.io.project import Project, load_project

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


def _import(target: str):
    module, name = target.split(":")
    return getattr(importlib.import_module(module), name)


def _example(fam):
    for path in sorted(EXAMPLES.glob("*.ocnx")):
        if fam.key in json.loads(path.read_text(encoding="utf-8")):
            return path
    raise AssertionError(f"no example in examples/ for {fam.key}")


def test_keys_are_unique_project_blocks():
    assert len(set(KEYS)) == len(KEYS) == len({f.command for f in FAMILIES})
    for key in KEYS:
        assert key in Project.model_fields, key


@pytest.mark.parametrize("fam", FAMILIES, ids=lambda f: f.key)
def test_family_is_complete(fam):
    commands = build_parser()._subparsers._group_actions[0].choices
    assert fam.command in commands, f"no 'openconex {fam.command}' command"
    assert callable(_import(fam.report))
    assert fam.name_es and fam.label
    assert family(fam.key) is family(fam.command) is fam
    doc = (ROOT / "docs" / "tecnico" / "13-agregar-familia.md").read_text(encoding="utf-8")
    assert f"`{fam.key}`" in doc, f"{fam.key} missing from the family table of the guide"


@pytest.mark.parametrize("fam", FAMILIES, ids=lambda f: f.key)
def test_family_example_reports_and_labels(fam):
    project = load_project(_example(fam))
    assert family_of(project) is fam
    report = fam.build_report(project)
    assert report.results
    assert fam.members(project)


@pytest.mark.parametrize("fam", [f for f in FAMILIES if f.window], ids=lambda f: f.key)
def test_family_window_class(fam):
    pytest.importorskip("PySide6")
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    assert fam.window_class().__name__.endswith("Window")


def test_command_names_the_right_family(capsys):
    path = _example(family("splice"))
    assert main(["shear", str(path)]) == 2
    err = capsys.readouterr().err
    assert "no shear connection" in err and "'openconex splice'" in err


def test_unknown_family():
    with pytest.raises(KeyError):
        family("bracing")
