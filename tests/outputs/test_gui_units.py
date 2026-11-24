# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Changing the unit system of a connection window keeps every magnitude."""

import datetime as dt
import math
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")

from openconex.gui.moment import MomentWindow
from openconex.gui.splice import SpliceWindow
from openconex.io.project import load_project
from openconex.report.builder import build_report

EXAMPLES = Path(__file__).parents[2] / "examples"
CASES = [
    (MomentWindow, "moment_bolted_flange_plate.ocnx"),
    (MomentWindow, "moment_end_plate_extended.ocnx"),
    (MomentWindow, "moment_seismic_rbs.ocnx"),
    (SpliceWindow, "splice_beam_bolted.ocnx"),
    (SpliceWindow, "splice_column_fillers.ocnx"),
]


def _results(project):
    report = build_report(project, dt.date(2026, 1, 1))
    return [(r.id, r.combo, r.demand, r.capacity) for r in report.results]


def _same(a, b):
    assert len(a) == len(b)
    for (id_a, combo_a, d_a, c_a), (id_b, combo_b, d_b, c_b) in zip(a, b, strict=True):
        assert (id_a, combo_a) == (id_b, combo_b)
        assert math.isclose(d_a, d_b, rel_tol=1e-6, abs_tol=1e-6), (id_a, combo_a, d_a, d_b)
        assert math.isclose(c_a, c_b, rel_tol=1e-6, abs_tol=1e-6), (id_a, combo_a, c_a, c_b)


@pytest.mark.parametrize(("window_type", "name"), CASES)
def test_unit_change_keeps_results(qtbot, window_type, name):
    path = EXAMPLES / name
    window = window_type(load_project(path), path)
    qtbot.addWidget(window)
    expected = _results(window.project_from_form())
    start = window.units.currentText()
    for preset in [*(u for u in ("SI_N_mm", "MKS", "SI_kN_m", "US") if u != start), start]:
        window.units.setCurrentText(preset)
        assert window.project_from_form().info.units == preset
        _same(_results(window.project_from_form()), expected)


@pytest.mark.parametrize(("window_type", "name", "group", "field"), [
    (MomentWindow, "moment_bolted_flange_plate.ocnx", "_flange", "spacing"),
    (SpliceWindow, "splice_beam_bolted.ocnx", "_flange", "spacing"),
])
def test_bare_number_is_converted(qtbot, window_type, name, group, field):
    """A number typed without unit keeps its magnitude when the system changes."""
    path = EXAMPLES / name
    window = window_type(load_project(path), path)
    qtbot.addWidget(window)
    window.units.setCurrentText("US")
    edit = getattr(window, group)[field]
    edit.setText("3")  # 3 in
    window.units.setCurrentText("SI_N_mm")
    assert float(edit.text()) == pytest.approx(76.2)
