# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Interaction tests for the desktop interface (pytest-qt)."""

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QPushButton

from openconex.gui.app import MainWindow
from openconex.gui.import_table import TableImportDialog
from openconex.gui.units import UnitDialog
from openconex.units import PRESETS, Kind

EXAMPLE = Path(__file__).parents[2] / "examples" / "base_plate_dg1_4_7_11.ocnx"


def _button(widget, text: str) -> QPushButton:
    return next(button for button in widget.findChildren(QPushButton)
                if button.text() == text)


def test_unit_action_click(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.open_project(EXAMPLE)
    window.show()
    qtbot.waitExposed(window)
    window._unit_actions["SI_N_mm"].trigger()
    qtbot.wait(20)
    assert window._quantity_fields["N"][1].text() == "mm"
    assert float(window._quantity_fields["tp"][0].text()) == pytest.approx(50.8)


def test_add_case_button_click(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.open_project(EXAMPLE)
    window.show()
    qtbot.waitExposed(window)
    before = window.cases.rowCount()
    qtbot.mouseClick(_button(window, "Añadir caso"), Qt.MouseButton.LeftButton)
    assert window.cases.rowCount() == before + 1


def test_unit_dialog_apply_click(qtbot):
    dialog = UnitDialog(None, PRESETS["US"])
    qtbot.addWidget(dialog)
    dialog._combos[Kind.LENGTH].setCurrentText("m")
    dialog.show()
    qtbot.waitExposed(dialog)
    qtbot.mouseClick(_button(dialog, "Aplicar"), Qt.MouseButton.LeftButton)
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.system().unit(Kind.LENGTH) == "m"


def test_table_import_dialog_click(qtbot, tmp_path):
    path = tmp_path / "table.csv"
    path.write_text("support,case,P\nJ1,D,10\n", encoding="utf-8")
    dialog = TableImportDialog(None, "US")
    qtbot.addWidget(dialog)
    dialog._file.setText(str(path))
    dialog._output.setText(str(tmp_path / "out"))
    dialog.show()
    qtbot.waitExposed(dialog)
    qtbot.mouseClick(_button(dialog, "Importar"), Qt.MouseButton.LeftButton)
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.units == "US"
