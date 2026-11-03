# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Shear connection window of the desktop interface."""

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from openconex.gui.app import MainWindow
from openconex.gui.shear import TYPE_FIELDS, ShearWindow
from openconex.io.project import load_project

EXAMPLES = Path(__file__).parents[2] / "examples"


@pytest.fixture
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_round_trip_and_calculate(app, tmp_path):
    path = EXAMPLES / "shear_double_angle_coped.ocnx"
    window = ShearWindow(load_project(path), path)
    project = window.project_from_form()
    original = load_project(path)
    assert project.shear_connection == original.shear_connection
    assert project.cases == original.cases
    assert window.calculate()
    assert window.summary.rowCount() == 10
    assert window.export("dxf", ".dxf", tmp_path / "x").exists()
    assert window.export("html", ".html", tmp_path / "x").exists()
    assert window.save_to(tmp_path / "copy.ocnx")
    assert load_project(tmp_path / "copy.ocnx").shear_connection == original.shear_connection


def test_fields_follow_the_type(app):
    window = ShearWindow()
    for index in range(window.type.count()):
        window.type.setCurrentIndex(index)
        shown = {name for name, (_, w) in window._rows.items() if not w.isHidden()}
        kind = window.type.currentData()
        assert shown == set(TYPE_FIELDS[next(k for k in TYPE_FIELDS if k.value == kind)])


def test_new_project_calculates(app):
    window = ShearWindow()
    assert window.calculate()
    assert window.report.ok


def test_main_window_opens_shear_projects_in_their_window(app):
    main = MainWindow()
    main.open_project(EXAMPLES / "shear_single_plate.ocnx")
    windows = main._shear_windows
    assert len(windows) == 1 and windows[0].path.name == "shear_single_plate.ocnx"
    assert main.project is None
