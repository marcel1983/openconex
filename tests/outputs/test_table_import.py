# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Generic Excel/CSV import tests."""

import os
from pathlib import Path

import pytest
from openpyxl import Workbook

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QDialog

from openconex.gui.import_table import TableImportDialog
from openconex.io.project import load_project, save_project
from openconex.io.table_import import projects_from_table, read_table
from openconex.units import PRESETS

EXAMPLE = Path(__file__).parents[2] / "examples" / "base_plate_dg1_4_7_11.ocnx"


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    return app


def test_read_csv_and_create_projects(tmp_path):
    path = tmp_path / "supports.csv"
    path.write_text(
        "support,case,type,column,P,V,M,V_weak,M_weak\n"
        "J1,D,D,W12X96,100 kip,0,0,0,0\n"
        "J1,L,L,,160 kip,0,0,0,0\n"
        "J2,D,D,W14X90,50,0,0,0,0\n",
        encoding="utf-8")
    projects, warnings = projects_from_table(read_table(path),
                                             load_project(EXAMPLE), PRESETS["US"])
    assert not warnings
    assert set(projects) == {"J1", "J2"}
    assert projects["J1"].base_plate.column == "W12X96"
    assert projects["J2"].base_plate.column == "W14X90"
    assert [case.name for case in projects["J1"].cases] == ["D", "L"]
    assert projects["J1"].case_forces()["D"].P == pytest.approx(444822.16, rel=1e-5)
    target = tmp_path / "J1.ocnx"
    save_project(projects["J1"], target)
    assert load_project(target).cases[1].P == "160"


def test_read_xlsx(tmp_path):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["support", "case", "P"])
    sheet.append(["J1", "D", "10 kip"])
    path = tmp_path / "supports.xlsx"
    workbook.save(path)
    projects, warnings = projects_from_table(read_table(path),
                                             load_project(EXAMPLE), PRESETS["US"])
    assert not warnings
    assert projects["J1"].case_forces()["D"].P == pytest.approx(44482.216, rel=1e-5)


def test_unknown_column_is_reported(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("support,case,column,P\nJ1,D,NO_SUCH,10\n", encoding="utf-8")
    projects, warnings = projects_from_table(read_table(path),
                                             load_project(EXAMPLE), PRESETS["US"])
    assert not projects
    assert any("unknown column" in warning for warning in warnings)


def test_table_import_dialog(qapp, tmp_path):
    path = tmp_path / "table.csv"
    path.write_text("support,case,P\nJ1,D,10\n", encoding="utf-8")
    dialog = TableImportDialog(None, "US")
    dialog._file.setText(str(path))
    dialog._output.setText(str(tmp_path / "out"))
    dialog.accept()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.file == str(path)
    assert dialog.units == "US"
    dialog.close()
