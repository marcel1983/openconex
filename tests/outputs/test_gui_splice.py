# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Splice window of the desktop interface."""

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")

from openconex.gui.app import MainWindow
from openconex.gui.splice import SpliceWindow
from openconex.io.project import load_project
from openconex.io.splice_project import SpliceType

EXAMPLES = Path(__file__).parents[2] / "examples"


@pytest.mark.parametrize("name", ["splice_beam_bolted.ocnx", "splice_column_fillers.ocnx"])
def test_round_trip_and_calculate(qtbot, tmp_path, name):
    path = EXAMPLES / name
    window = SpliceWindow(load_project(path), path)
    qtbot.addWidget(window)
    project = window.project_from_form()
    original = load_project(path)
    assert project.splice_model() == original.splice_model()
    assert project.cases == original.cases
    assert window.calculate()
    assert window.summary.rowCount() > 10
    assert window.export("dxf", ".dxf", tmp_path / "x").exists()
    assert window.export("html", ".html", tmp_path / "x").exists()
    assert window.save_to(tmp_path / "copy.ocnx")
    assert load_project(tmp_path / "copy.ocnx").splice == project.splice


def test_new_column_splice_and_change_tracking(qtbot, tmp_path):
    window = SpliceWindow()
    qtbot.addWidget(window)
    assert not window.is_modified
    window._info["name"].setText("Empalme E-1")
    assert window.is_modified
    assert window.save_to(tmp_path / "empalme.ocnx")
    assert not window.is_modified
    window.new_project(SpliceType.COLUMN)
    assert window.project.splice.type is SpliceType.COLUMN
    assert window.upper.isVisibleTo(window) and not window.beam.isVisibleTo(window)
    assert window.calculate()


def test_main_window_opens_splice_projects(qtbot):
    main = MainWindow()
    qtbot.addWidget(main)
    main.open_project(str(EXAMPLES / "splice_beam_bolted.ocnx"))
    assert any(isinstance(w, SpliceWindow) for w in getattr(main, "_splice_windows", []))
