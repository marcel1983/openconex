# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Shear connection window of the desktop interface."""

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from openconex.gui.app import MainWindow
from openconex.gui.help import HelpDialog
from openconex.gui.shear import TYPE_FIELDS, ShearWindow
from openconex.io.project import Project, load_project
from openconex.units import Kind, to_internal

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


def test_cope_reinforcement_is_preserved(app):
    data = json.loads((EXAMPLES / "shear_double_angle_coped.ocnx").read_text(
        encoding="utf-8"))
    data["shear_connection"]["cope"]["doubler"] = {
        "thickness": "1/4 in", "depth": "6.5 in", "gap": "0.5 in", "weld": "1/4 in"}
    window = ShearWindow(Project.model_validate(data))
    project = window.project_from_form()
    assert project.shear_connection.cope.doubler is not None


def test_explode_button_follows_the_connection_type(app):
    window = ShearWindow(load_project(EXAMPLES / "shear_double_angle_coped.ocnx"))
    assert window.viewer._explode_button is not None
    window.type.setCurrentIndex(window.type.findData("skewed_bent_plate"))
    window._update_visible()
    assert window.viewer._explode_button.isHidden()
    window.type.setCurrentIndex(window.type.findData("double_angle"))
    window._update_visible()
    assert not window.viewer._explode_button.isHidden()
    window.close()


def test_shear_window_converts_units(app):
    window = ShearWindow(load_project(EXAMPLES / "shear_single_plate_coped.ocnx"))
    assert window._fields["length"].text() == "11.5 in"
    window.units.setCurrentText("SI_N_mm")
    assert window._units.name == "SI_N_mm"
    assert float(window._fields["length"].text()) == pytest.approx(
        to_internal(11.5, "in", Kind.LENGTH), rel=1e-6)
    assert float(window._cope["leh"].text()) == pytest.approx(
        to_internal(2.25, "in", Kind.LENGTH), rel=1e-6)
    assert float(window.cases.item(0, 2).text()) == pytest.approx(
        to_internal(6.5, "kip", Kind.FORCE), rel=1e-5)
    project = window.project_from_form()
    assert project.info.units == "SI_N_mm"
    assert project.quantity(project.shear_connection.length, Kind.LENGTH) == pytest.approx(
        to_internal(11.5, "in", Kind.LENGTH), rel=1e-6)
    assert window.calculate()
    window.close()


def test_fields_follow_the_type(app):
    window = ShearWindow()
    for index in range(window.type.count()):
        window.type.setCurrentIndex(index)
        shown = {name for name, (_, w) in window._rows.items() if not w.isHidden()}
        kind = window.type.currentData()
        assert shown == set(TYPE_FIELDS[next(k for k in TYPE_FIELDS if k.value == kind)])


def test_help_dialog_and_tooltips(app):
    window = ShearWindow()
    assert all(widget.toolTip() for widget in window._fields.values())
    for menu in window.menuBar().actions():
        submenu = menu.menu()
        if submenu is None:
            continue
        for action in submenu.actions():
            if action.isSeparator():
                continue
            assert action.toolTip(), action.text()
    dialog = HelpDialog("fields")
    assert dialog.list.count() > 20
    dialog.search.setText("perno")
    assert dialog.list.count() > 0
    dialog.close()
    for section in ("menus", "checks", "all"):
        other = HelpDialog(section)
        assert other.list.count() > 0
        other.close()


def test_bent_plate_geometry_round_trip(app):
    path = EXAMPLES / "shear_skewed_bent_plate.ocnx"
    window = ShearWindow(load_project(path), path)
    assert window._fields["skew"].text() == "6:12"
    assert window._fields["plate_a_leg"].text() == "4 7/16 in"
    assert window._fields["plate_b_leg"].text() == "3 9/16 in"
    assert window._fields["bend_radius"].text() == "9/16 in"
    project = window.project_from_form()
    assert project.shear_connection.plate_a_leg == "4 7/16 in"
    assert project.shear_connection.bend_radius == "9/16 in"
    assert window.calculate()
    assert window.report.ok


def test_new_project_calculates(app):
    window = ShearWindow()
    assert window.calculate()
    assert window.report.ok


def test_hidden_seat_details_survive_a_save(app):
    project = Project.model_validate({
        "shear_connection": {
            "type": "seated", "beam": "W16X50", "support": "W14X90",
            "length": "8 in", "thickness": "5/8 in", "leg": "4 in",
            "top_angle_thickness": "3/8 in",
        },
        "cases": [{"name": "D", "type": "D", "V": "8 kip"}],
    })
    window = ShearWindow(project)
    saved = window.project_from_form()
    assert saved.shear_connection.top_angle_thickness == "3/8 in"


def test_main_window_opens_shear_projects_in_their_window(app):
    main = MainWindow()
    main.open_project(EXAMPLES / "shear_single_plate.ocnx")
    windows = main._shear_windows
    assert len(windows) == 1 and windows[0].path.name == "shear_single_plate.ocnx"
    assert main.project is None
