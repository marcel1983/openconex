# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Minimal desktop interface smoke tests."""

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from openconex.core.model import HSSKind
from openconex.gui.app import MainWindow
from openconex.gui.library import MaterialLibraryDialog, SectionLibraryDialog
from openconex.io.project import (
    HSSSectionInput,
    MaterialInput,
    WSectionInput,
    load_project,
)

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


def test_gui_uses_section_and_material_combos(qapp):
    window = MainWindow()
    window.open_project(EXAMPLE)
    assert window._section_combo.currentText() == "W12X96"
    assert window._section_combo.findText("C15X50") == -1
    assert window._material_combos["column_grade"].currentText() == "ASTM A992"
    assert window._material_combos["plate_grade"].currentText() == "ASTM A572 Gr. 50"
    assert window._material_combos["rod_grade"].currentText() == "ASTM F1554 Gr. 36"
    window.close()


def test_gui_converts_units_from_menu(qapp):
    window = MainWindow()
    window.open_project(EXAMPLE)
    assert window._quantity_fields["N"][0].text() == "24"
    assert window._quantity_fields["N"][1].text() == "in"
    window.set_unit_system("SI_N_mm")
    assert window._quantity_fields["N"][1].text() == "mm"
    assert window._quantity_fields["tp"][0].text() == "50.8"
    assert float(window._quantity_fields["N"][0].text()) == pytest.approx(609.6)
    assert window.cases.horizontalHeaderItem(2).text() == "P (N)"
    assert float(window.cases.item(0, 2).text()) == pytest.approx(444822.16, rel=1e-6)
    window.calculate()
    assert window.report is not None
    assert window.project.info.units == "SI_N_mm"
    assert window.project.base_plate_model().N == pytest.approx(609.6)
    window.close()


def test_gui_units_round_trip(qapp, tmp_path):
    window = MainWindow()
    window.open_project(EXAMPLE)
    window.set_unit_system("SI_kN_m")
    assert window._quantity_fields["N"][1].text() == "m"
    window.set_unit_system("US")
    assert float(window._quantity_fields["N"][0].text()) == pytest.approx(24, rel=1e-6)
    target = tmp_path / "units.ocnx"
    window.save_project_to(target)
    again = load_project(target)
    assert again.info.units == "US"
    assert again.base_plate_model().N == pytest.approx(609.6)
    window.close()


def test_gui_units_keep_preserved_blocks(qapp):
    from openconex.units import Kind

    window = MainWindow()
    window.open_project(EXAMPLE.with_name("base_plate_embedded_base.ocnx"))
    before = window.project.quantity(window.project.base_plate.embedded_base.embedment,
                                     Kind.LENGTH)
    window.set_unit_system("SI_N_mm")
    after = window.project.quantity(window.project.base_plate.embedded_base.embedment,
                                    Kind.LENGTH)
    assert after == pytest.approx(before)
    window.close()

    window = MainWindow()
    window.open_project(EXAMPLE.with_name("base_plate_shear_lug.ocnx"))
    before = window.project.quantity(window.project.base_plate.shear_lug.weld,
                                     Kind.THICKNESS)
    window.set_unit_system("US")
    after = window.project.quantity(window.project.base_plate.shear_lug.weld,
                                    Kind.THICKNESS)
    assert after == pytest.approx(before)
    window.close()


def test_gui_custom_section_and_material_round_trip(qapp, tmp_path):
    window = MainWindow()
    window.open_project(EXAMPLE)
    section = WSectionInput(type="W", name="COL-GUI", d="14", bf="10", tf="0.5",
                            tw="0.3", grade="ASTM A992")
    assert window.add_custom_section(section) == "COL-GUI"
    assert window._section_combo.currentText() == "COL-GUI"
    material = MaterialInput(name="Acero GUI", Fy="50 ksi", Fu="65 ksi", E="29000 ksi")
    window.add_custom_material(material)
    assert window._material_combos["plate_grade"].findText("Acero GUI") >= 0
    window._material_combos["plate_grade"].setCurrentText("Acero GUI")
    target = tmp_path / "gui_custom.ocnx"
    window.save_project_to(target)
    again = load_project(target)
    assert [item.label() for item in again.sections] == ["COL-GUI"]
    assert any(item.name == "Acero GUI" for item in again.materials)
    assert again.base_plate.plate_grade == "Acero GUI"
    assert not isinstance(again.base_plate.column, str)
    assert again.base_plate.column.label() == "COL-GUI"
    window.calculate()
    assert window.report is not None
    window.close()


def test_gui_custom_hss_section(qapp):
    window = MainWindow()
    window.open_project(EXAMPLE)
    section = HSSSectionInput(type="HSS", name="HSS-GUI", shape=HSSKind.SQUARE,
                              d="10", t="0.5",
                              grade="ASTM A500 Gr. C (rectangular)")
    window.add_custom_section(section)
    assert window._section_combo.currentText() == "HSS-GUI"
    window.calculate()
    assert window.report is not None
    window.close()


def test_library_dialogs(qapp):
    window = MainWindow()
    window.open_project(EXAMPLE)
    sections = SectionLibraryDialog(window, window._units, window._custom_sections,
                                    window.add_custom_section, window._steel_names())
    assert sections._table.rowCount() > 300
    sections.close()
    materials = MaterialLibraryDialog(window, window._units, window.project.materials,
                                      window.add_custom_material)
    assert materials._tabs.count() == 3
    assert materials._bolt_table.rowCount() >= 5
    assert materials._weld_table.rowCount() == 2
    materials.close()
    window.close()
