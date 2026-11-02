# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Graphical geometry editor tests."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication

from openconex.gui.geometry import GeometryEditor, GeometryValues
from openconex.units import PRESETS


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    return app


def _values(state: dict[str, float]) -> GeometryValues:
    return GeometryValues(
        N=state["N"], B=state["B"], tp=state["tp"], grout=state["grout"],
        f=state["f"], rod_spacing=state["rod_spacing"], hef=state["hef"],
        rods_per_side=2, column_d=300.0, column_bf=300.0, column_label="W12X96",
        pedestal_N=700.0, pedestal_B=700.0, lug_width=200.0,
        lug_direction="strong", units=PRESETS["US"])


def _editor():
    state = {"N": 600.0, "B": 600.0, "tp": 30.0, "grout": 50.0,
             "f": 200.0, "rod_spacing": 300.0, "hef": 300.0}

    def read():
        return _values(state)

    def apply(changes):
        state.update(changes)

    return GeometryEditor(read, apply), state


def test_geometry_draws_plan_and_elevation(qapp):
    editor, _ = _editor()
    editor.refresh()
    assert len(editor._plan_scene.items()) > 10
    assert len(editor._elevation_scene.items()) > 5


def test_geometry_plan_handles_and_undo(qapp):
    editor, state = _editor()
    editor.refresh()
    editor._on_handle("edge_right", QPointF(350, 0))
    assert state["B"] == pytest.approx(700)
    assert editor._undo
    editor.undo()
    assert state["B"] == pytest.approx(600)
    editor.redo()
    assert state["B"] == pytest.approx(700)


def test_geometry_enforces_minimum_dimensions(qapp):
    editor, state = _editor()
    editor.refresh()
    editor._on_handle("edge_right", QPointF(1, 0))
    assert state["B"] == pytest.approx(360)
    editor._on_handle("anchor", QPointF(1, 1))
    assert state["rod_spacing"] == pytest.approx(240)
    assert state["f"] == pytest.approx(170)


def test_geometry_pedestal_handles(qapp):
    editor, state = _editor()
    editor.refresh()
    editor._on_handle("pedestal_right", QPointF(400, 0))
    assert state["pedestal_B"] == pytest.approx(800)
    editor._on_handle("pedestal_top", QPointF(0, -400))
    assert state["pedestal_N"] == pytest.approx(800)


def test_geometry_elevation_handles(qapp):
    editor, state = _editor()
    editor.refresh()
    editor._on_handle("plate_top", QPointF(0, -40))
    assert state["tp"] == pytest.approx(40)
    editor._on_handle("grout_bottom", QPointF(0, 60))
    assert state["grout"] == pytest.approx(60)
    editor._on_handle("hef_bottom", QPointF(0, 300))
    assert state["hef"] == pytest.approx(240)
