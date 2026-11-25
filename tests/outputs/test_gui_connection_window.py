# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Behaviour shared by the shear, moment and splice windows (``ConnectionWindow``)."""

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")

from PySide6.QtWidgets import QMessageBox

from openconex.families import FAMILIES, family_of
from openconex.gui.connection_window import CUSTOM_UNITS, ConnectionWindow
from openconex.gui.moment import MomentWindow
from openconex.gui.shear import ShearWindow
from openconex.gui.splice import SpliceWindow
from openconex.io.project import Project, load_project

EXAMPLES = Path(__file__).parents[2] / "examples"
WINDOWS = [
    (ShearWindow, "shear_single_plate.ocnx"),
    (MomentWindow, "moment_bolted_flange_plate.ocnx"),
    (SpliceWindow, "splice_beam_bolted.ocnx"),
]


def _tabs(window) -> list[str]:
    return [page.title for page in window.ribbon.pages]


def test_every_family_window_uses_the_common_base():
    for fam in FAMILIES:
        if fam.window is not None:
            assert issubclass(fam.window_class(), ConnectionWindow)
            assert fam.window_class().family_key == fam.key


@pytest.mark.parametrize(("window_type", "name"), WINDOWS)
def test_ribbon_and_calculation(qtbot, window_type, name):
    path = EXAMPLES / name
    window = window_type(load_project(path), path)
    qtbot.addWidget(window)
    assert _tabs(window) == ["Inicio", "Conexiones", "Cálculo", "Vista 3D", "Exportar",
                             "Configuración", "Ayuda"]
    assert not window.menuBar().actions()
    assert not any(action.isEnabled() for action in window._export_actions)
    assert window.calculate()
    assert window.summary.rowCount() > 0
    assert all(action.isEnabled() for action in window._export_actions)
    assert path.name in window.windowTitle()


def test_family_specific_ribbon(qtbot):
    shear, splice = ShearWindow(), SpliceWindow()
    qtbot.addWidget(shear)
    qtbot.addWidget(splice)
    help_texts = [a.text() for a in shear.ribbon.actions_of("Ayuda")]
    assert help_texts[0] == "Guía rápida"
    assert [a.text() for a in splice.ribbon.actions_of("Ayuda")] == ["Verificaciones",
                                                                    "Acerca de"]
    new = [a.text() for a in splice.ribbon.actions_of("Conexiones")]
    assert new == ["Nuevo empalme de viga", "Nuevo empalme de columna"]


@pytest.mark.parametrize(("window_type", "name"), WINDOWS)
def test_project_of_another_family_is_refused(qtbot, monkeypatch, window_type, name):
    window = window_type()
    qtbot.addWidget(window)
    other = next(n for _, n in WINDOWS if n != name)
    messages = []
    monkeypatch.setattr(QMessageBox, "warning",
                        lambda _parent, _title, text: messages.append(text))
    assert not window.open(EXAMPLES / other)
    found = family_of(load_project(EXAMPLES / other))
    assert messages and found.name_es in messages[0]
    assert window.path is None


@pytest.mark.parametrize(("window_type", "name"), WINDOWS)
def test_custom_unit_system_is_kept(qtbot, window_type, name):
    data = json.loads((EXAMPLES / name).read_text(encoding="utf-8"))
    data["info"]["units"] = {"name": "obra", "length": "cm", "force": "kip"}
    project = Project.model_validate(data)
    window = window_type(project)
    qtbot.addWidget(window)
    assert window.units.currentText() == CUSTOM_UNITS
    assert window.project_from_form().info.units == project.info.units
