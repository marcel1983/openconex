# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Minimal desktop interface smoke tests."""

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from openconex.gui.app import MainWindow
from openconex.io.project import load_project

EXAMPLE = Path(__file__).parents[2] / "examples" / "base_plate_dg1_4_7_11.ocnx"


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    return app


def test_gui_loads_project_and_calculates(qapp):
    window = MainWindow()
    window.open_project(EXAMPLE)
    assert window.project is not None
    assert window.cases.rowCount() == len(window.project.cases)
    window.calculate()
    assert window.report is not None
    assert window.summary.rowCount() == len(window.report.summary)
    assert window.details.toPlainText()
    window.close()


def test_gui_saves_round_trip(qapp, tmp_path):
    window = MainWindow()
    window.open_project(EXAMPLE)
    target = tmp_path / "gui.ocnx"
    window.save_project_to(target)
    assert target.exists()
    assert load_project(target).base_plate.column == "W12X96"
    window.close()
