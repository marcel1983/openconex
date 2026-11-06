# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Minimal desktop interface smoke tests."""

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog

from openconex.core.loads import Method
from openconex.core.model import HSSKind
from openconex.gui.advanced import BasePlateAdvancedForm
from openconex.gui.app import MainWindow
from openconex.gui.help import HelpDialog
from openconex.gui.import_supports import ImportSupportsDialog
from openconex.gui.library import MaterialLibraryDialog, SectionLibraryDialog
from openconex.gui.units import UnitDialog
from openconex.io.project import (
    BoltGradeInput,
    ElectrodeInput,
    HSSSectionInput,
    MaterialInput,
    WSectionInput,
    load_project,
)
from openconex.units import PRESETS, Kind

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


def test_base_plate_help_and_tooltips(qapp):
    window = MainWindow()
    window.open_project(EXAMPLE)
    assert all(edit.toolTip() for edit, _unit, _kind in window._quantity_fields.values())
    assert all(combo.toolTip() for combo in window._material_combos.values())
    assert all(box.toolTip() for box in window._plate_boxes.values())
    assert window._plain_edits["A2_over_A1"].toolTip()
    assert window._plain_edits["rods_per_side"].toolTip()
    for menu in window.menuBar().actions():
        submenu = menu.menu()
        if submenu is None:
            continue
        for action in submenu.actions():
            if not action.isSeparator():
                assert action.toolTip(), action.text()
    form = BasePlateAdvancedForm()
    assert all(field.edit.toolTip() for field in form._fields.values())
    dialog = HelpDialog("fields")
    assert dialog.list.count() > 50
    dialog.close()
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


def test_gui_custom_units_round_trip(qapp, tmp_path):
    window = MainWindow()
    window.open_project(EXAMPLE)
    custom = (PRESETS["US"].with_unit(Kind.LENGTH, "m")
              .with_unit(Kind.THICKNESS, "mm"))
    window.set_unit_system(custom)
    assert window._quantity_fields["N"][1].text() == "m"
    assert window._quantity_fields["tp"][1].text() == "mm"
    target = tmp_path / "custom_units.ocnx"
    window.save_project_to(target)
    again = load_project(target)
    system = again.info.unit_system()
    assert system.unit(Kind.LENGTH) == "m"
    assert system.unit(Kind.THICKNESS) == "mm"
    assert again.base_plate_model().N == pytest.approx(609.6)
    window.calculate()
    assert window.report is not None
    window.close()


def test_unit_dialog(qapp):
    dialog = UnitDialog(None, PRESETS["US"])
    dialog._combos[Kind.LENGTH].setCurrentText("m")
    dialog._combos[Kind.THICKNESS].setCurrentText("mm")
    system = dialog.system()
    assert system.unit(Kind.LENGTH) == "m"
    assert system.unit(Kind.THICKNESS) == "mm"
    assert system.name == "custom"
    dialog.close()


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


def test_gui_custom_bolts_and_electrodes(qapp, tmp_path):
    window = MainWindow()
    window.open_project(EXAMPLE)
    bolt = BoltGradeInput(name="Perno GUI", Fnt="100 ksi", Fnv_N="60 ksi",
                          Fnv_X="75 ksi", Fu="125 ksi", Fy="100 ksi")
    window.add_custom_bolt(bolt)
    assert window._material_combos["rod_grade"].findText("Perno GUI") >= 0
    electrode = ElectrodeInput(name="E90XX", FEXX="90 ksi")
    window.add_custom_electrode(electrode)
    assert window.advanced._electrode.findText("E90XX") >= 0
    window._material_combos["rod_grade"].setCurrentText("Perno GUI")
    window.advanced._electrode.setCurrentText("E90XX")
    window.advanced._fields["flange_weld"].edit.setText("0.25")
    target = tmp_path / "custom_bolts.ocnx"
    window.save_project_to(target)
    again = load_project(target)
    assert again.base_plate.rod_grade == "Perno GUI"
    assert again.base_plate.electrode == "E90XX"
    assert again.base_plate_model().rod.material.name == "Perno GUI"
    window.calculate()
    assert window.report is not None
    window.close()


def test_gui_edits_shear_lug(qapp, tmp_path):
    window = MainWindow()
    window.open_project(EXAMPLE.with_name("base_plate_shear_lug.ocnx"))
    assert window.advanced._shear_group.isChecked()
    assert window.advanced._fields["shear_lug.width"].edit.text() == "8"
    window.advanced._fields["shear_lug.width"].edit.setText("9")
    target = tmp_path / "lug.ocnx"
    window.save_project_to(target)
    again = load_project(target)
    assert again.base_plate.shear_lug.width == "9"
    assert again.base_plate.shear_lug.ca1 == "14.5"
    window.calculate()
    assert window.report is not None
    window.close()


def test_gui_edits_reinforcement(qapp, tmp_path):
    window = MainWindow()
    window.open_project(EXAMPLE.with_name("base_plate_anchor_reinforcement.ocnx"))
    assert window.advanced._reinforcement_group.isChecked()
    assert window.advanced._bars.text() == "4 #6"
    window.advanced._fields["reinforcement.area"].edit.setText("2.0")
    target = tmp_path / "reinforcement.ocnx"
    window.save_project_to(target)
    again = load_project(target)
    assert again.base_plate.reinforcement.area == "2.0"
    assert again.base_plate.reinforcement.bars == "4 #6"
    window.calculate()
    assert window.report is not None
    window.close()


def test_gui_edits_weak_base(qapp, tmp_path):
    window = MainWindow()
    window.open_project(EXAMPLE.with_name("base_plate_weak_base.ocnx"))
    assert window.advanced._weak_group.isChecked()
    assert window.advanced._rt.text() == "1.2"
    window.advanced._rt.setText("1.3")
    target = tmp_path / "weak.ocnx"
    window.save_project_to(target)
    again = load_project(target)
    assert again.base_plate.weak_base.Rt == pytest.approx(1.3)
    window.calculate()
    assert window.report is not None
    window.close()


def test_gui_edits_embedded_base(qapp, tmp_path):
    window = MainWindow()
    window.open_project(EXAMPLE.with_name("base_plate_embedded_base.ocnx"))
    assert window._connection_combo.currentData() == "embedded"
    assert not window.advanced._embedded_group.isHidden()
    assert window._plate_group.isHidden()
    assert window.advanced._fields["embedded_base.embedment"].edit.text() == "22"
    window.advanced._fields["embedded_base.embedment"].edit.setText("24")
    target = tmp_path / "embedded.ocnx"
    window.save_project_to(target)
    again = load_project(target)
    assert again.base_plate.connection_type == "embedded"
    assert again.base_plate.embedded_base.embedment == "24"
    assert again.base_plate.N is None
    window.calculate()
    assert window.report is not None
    window.close()


def test_gui_advanced_options_and_combinations(qapp, tmp_path):
    window = MainWindow()
    window.open_project(EXAMPLE)
    advanced = window.advanced
    advanced._friction.setText("0.3")
    advanced._fields["rod_bending_lever"].edit.setText("2")
    advanced._fields["bearing_area"].edit.setText("4 in**2")
    advanced._fields["washer_thickness"].edit.setText("0.5")
    advanced._fields["flange_weld"].edit.setText("0.25")
    for key, value in (("left", "3"), ("right", "4"),
                       ("bottom", "5"), ("top", "6")):
        advanced._fields[f"edges.{key}"].edit.setText(value)
    advanced._add_rebar()
    advanced._rebar_table.item(0, 0).setText("2")
    advanced._rebar_table.item(0, 1).setText("3")
    advanced._rebar_table.item(0, 2).setText("0.75")
    window._combination_edits["SDS"].setText("1.0")
    window._combination_edits["live_factor"].setText("0.8")

    target = tmp_path / "advanced.ocnx"
    window.save_project_to(target)
    again = load_project(target)
    bp = again.base_plate
    assert bp.friction_mu == pytest.approx(0.3)
    assert bp.rod_bending_lever == "2"
    assert bp.bearing_area == "4 in**2"
    assert bp.washer_thickness == "0.5"
    assert bp.flange_weld == "0.25"
    assert bp.edges == {"left": "3", "right": "4", "bottom": "5", "top": "6"}
    assert len(bp.pedestal_rebars) == 1
    assert bp.pedestal_rebars[0].diameter == "0.75"
    assert again.combinations.SDS == pytest.approx(1.0)
    assert again.combinations.live_factor == pytest.approx(0.8)
    window.calculate()
    assert window.report is not None
    window.close()


def test_gui_switches_to_embedded(qapp, tmp_path):
    window = MainWindow()
    window.open_project(EXAMPLE)
    window._connection_combo.setCurrentIndex(
        window._connection_combo.findData("embedded"))
    assert window._plate_group.isHidden()
    assert not window.advanced._embedded_group.isHidden()
    advanced = window.advanced
    advanced._fields["embedded_base.embedment"].edit.setText("22")
    advanced._fields["embedded_base.foundation_width"].edit.setText("60")
    advanced._fields["embedded_base.face_plate_thickness"].edit.setText("1")
    window._method_boxes[Method.ASD].setChecked(False)

    target = tmp_path / "switched.ocnx"
    window.save_project_to(target)
    again = load_project(target)
    assert again.base_plate.connection_type == "embedded"
    assert again.base_plate.embedded_base is not None
    assert again.base_plate.N is None
    assert again.combinations.methods == [Method.LRFD]
    window.calculate()
    assert window.report is not None
    window.close()


def test_gui_units_convert_advanced_fields(qapp, tmp_path):
    window = MainWindow()
    window.open_project(EXAMPLE.with_name("base_plate_shear_lug.ocnx"))
    field = window.advanced._fields["shear_lug.weld"]
    assert field.edit.text() == "0.3125"
    assert field.unit.text() == "in"
    window.set_unit_system("SI_N_mm")
    assert field.edit.text() == "7.9375"
    assert field.unit.text() == "mm"
    assert window.advanced._fields["edges.bottom"].edit.text() == "274.32"
    target = tmp_path / "lug_units.ocnx"
    window.save_project_to(target)
    again = load_project(target)
    assert again.info.units == "SI_N_mm"
    assert again.base_plate_model().shear_lug.weld == pytest.approx(7.9375)
    window.close()


def test_gui_custom_combinations_round_trip(qapp, tmp_path):
    window = MainWindow()
    window.open_project(EXAMPLE)
    window._add_custom_combination()
    row = window._custom_table.rowCount() - 1
    window._custom_table.item(row, 0).setText("Custom")
    window._custom_table.item(row, 2).setText("D=1.2; L=1.6")
    window._custom_table.item(row, 3).setCheckState(Qt.CheckState.Checked)
    target = tmp_path / "combinations.ocnx"
    window.save_project_to(target)
    again = load_project(target)
    custom = again.combinations.custom
    assert len(custom) == 1
    assert custom[0].name == "Custom"
    assert custom[0].factors == {"D": 1.2, "L": 1.6}
    assert custom[0].seismic is True
    window.calculate()
    assert window.report is not None

    window._custom_table.setCurrentCell(row, 0)
    window._duplicate_custom_combination()
    assert window._custom_table.rowCount() == 2
    window._custom_table.setCurrentCell(1, 0)
    window._remove_custom_combination()
    assert window._custom_table.rowCount() == 1
    window.close()


def test_import_supports_dialog(qapp, tmp_path):
    export = tmp_path / "model.xlsx"
    export.write_bytes(b"")
    dialog = ImportSupportsDialog(None, "Plantilla")
    dialog._file.setText(str(export))
    dialog._output.setText(str(tmp_path / "out"))
    dialog.accept()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.file == str(export)
    assert dialog.group == "joint"
    assert dialog.loads == "cases"
    assert dialog.method == ""
    dialog.close()


def test_gui_import_from_csi(qapp, tmp_path, monkeypatch):
    window = MainWindow()
    window.open_project(EXAMPLE)
    monkeypatch.setattr("openconex.gui.app.import_supports", lambda path: object())
    monkeypatch.setattr(
        "openconex.gui.app.base_plate_projects",
        lambda data, template, *args, **kwargs: ({"J1": template}, []))
    monkeypatch.setattr("openconex.gui.app.QMessageBox.information",
                        lambda *args: None)
    paths = window.import_from_csi("model.xlsx", str(tmp_path / "out"),
                                   "joint", "cases")
    assert len(paths) == 1 and paths[0].exists()
    again = load_project(paths[0])
    assert again.base_plate.column == "W12X96"
    assert again.cases
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
