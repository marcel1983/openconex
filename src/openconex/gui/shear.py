# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Editor window for beam-end shear connection projects.

Quantities are typed as in the project file: text with its unit (``3 in``,
``25 kip``); a bare number uses the unit system of the project. The fields
shown follow the connection type.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtGui import QAction, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from openconex.connections.shear.check import ShearType
from openconex.core.loads import LoadType, Method
from openconex.core.model import HoleType, Threads
from openconex.core.shapes import ShapeDatabaseError, aisc_shapes
from openconex.gui.exporting import parts_3d, write_3d, write_dxf
from openconex.gui.help import HelpDialog
from openconex.gui.quantity import convert_text
from openconex.gui.viewer3d import Viewer3D
from openconex.help import help_text
from openconex.i18n import tr
from openconex.io.project import Project, load_project, save_project
from openconex.io.shear_project import REQUIRED
from openconex.report.builder import Report
from openconex.report.docx import write_docx
from openconex.report.html import write_html
from openconex.report.pdf import write_pdf
from openconex.report.shear import build_shear_report
from openconex.units import PRESETS, Kind

__all__ = ["TYPE_FIELDS", "ShearWindow"]

# Quantity fields of ``ShearConnectionInput`` with their label; integers apart.
QUANTITIES = ("spacing", "gage", "length", "thickness", "width", "lev", "leh", "leh_support",
              "a", "beam_leg", "outstanding_leg", "beam_leh", "leg", "vertical_leg",
              "bearing_length", "weld", "support_weld", "beam_weld", "beam_area",
              "row_distance", "load_offset", "share_a", "share_b", "plate_a_width", "plate_b_width",
              "plate_a_leg", "plate_b_leg", "bend_radius", "weld_return", "weld_offset")
LABELS = {"beam_area": "beam_area"}

TYPE_FIELDS: dict[ShearType, tuple[str, ...]] = {
    ShearType.DOUBLE_ANGLE: ("rows", "spacing", "length", "thickness", "lev", "leh",
                             "leh_support", "support_weld", "beam_weld", "beam_leg",
                             "outstanding_leg", "gage", "beam_leh", "beam_area"),
    ShearType.SINGLE_PLATE: ("rows", "spacing", "length", "thickness", "lev", "leh", "a",
                             "weld", "beam_leh"),
    ShearType.EXTENDED_SINGLE_PLATE: ("rows", "lines", "spacing", "gage", "length",
                                      "thickness", "lev", "leh", "a", "weld"),
    ShearType.END_PLATE: ("rows", "spacing", "length", "thickness", "lev", "leh", "weld"),
    ShearType.SEATED: ("length", "thickness", "leg", "vertical_leg", "bolts", "support_weld",
                       "bearing_length"),
    ShearType.STIFFENED_SEAT: ("width", "length", "thickness", "weld", "two_sided"),
    ShearType.SKEWED_BENT_PLATE: ("rows", "spacing", "length", "thickness", "lev", "leh",
                                  "weld", "weld_return", "weld_offset", "row_distance",
                                  "load_offset", "share_a", "share_b", "plate_a_width",
                                  "plate_b_width", "plate_a_leg", "plate_b_leg",
                                  "bend_radius", "skew"),
}
COPE_FIELDS = ("c", "dc", "dc_bottom", "setback", "lev", "leh")
DOUBLER_FIELDS = ("thickness", "depth", "gap", "weld")
STIFFENER_FIELDS = ("width", "thickness", "weld", "length")
# Advanced seat details kept in the project but not shown in the form; preserved on save.
HIDDEN_FIELDS = ("seat_plate_width", "seat_plate_thickness", "seat_plate_weld",
                 "top_angle_leg", "top_angle_thickness", "top_angle_length",
                 "top_angle_bolts", "top_angle_weld")
CASE_TYPES = [t.value for t in LoadType]
CUSTOM_UNITS = "(del proyecto)"

TEMPLATE = {
    "info": {"name": "Conexión de corte", "language": "es", "units": "US"},
    "shear_connection": {
        "type": "single_plate", "beam": "W16X50", "support": "W14X90",
        "rows": 4, "spacing": "3 in", "length": "11.5 in", "thickness": "1/4 in",
        "lev": "1.25 in", "leh": "1.5 in", "a": "3 in", "weld": "3/16 in"},
    "cases": [{"name": "D", "type": "D", "V": "8 kip"}, {"name": "L", "type": "L", "V": "25 kip"}],
    "combinations": {"methods": ["LRFD", "ASD"]},
}


def _text(value) -> str:
    return "" if value is None else str(value)


class ShearWindow(QMainWindow):
    """Editor, calculation and outputs of one shear connection project."""

    def __init__(self, project: Project | None = None, path: str | Path | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project = project or Project.model_validate(TEMPLATE)
        self.path = None if path is None else Path(path)
        self._units = self.project.info.unit_system()
        self.report: Report | None = None
        self._fields: dict[str, QWidget] = {}
        self._rows: dict[str, tuple[QLabel, QWidget]] = {}
        self._cope: dict[str, QLineEdit] = {}
        self._cope_reinf: dict[str, QLineEdit] = {}
        self._export_actions: list[QAction] = []
        self.setWindowTitle("OpenConex — conexión de corte")
        self.resize(1280, 860)
        self._build_menu()
        self._build_body()
        self._fill(self.project)
        self.statusBar().showMessage("Edite la conexión y pulse Calcular (F5).")

    # -- construction -----------------------------------------------------------
    def _build_menu(self) -> None:
        def action(label: str, slot, shortcut: str, key: str) -> QAction:
            item = QAction(label, self)
            if shortcut:
                item.setShortcut(shortcut)
            item.setToolTip(help_text(key))
            item.setStatusTip(help_text(key))
            item.triggered.connect(slot)
            return item

        menu = self.menuBar().addMenu("&Archivo")
        menu.addAction(action("Nuevo", self.new_project, "Ctrl+N", "menu.file.new"))
        menu.addAction(action("Abrir…", self.open_dialog, "Ctrl+O", "menu.file.open"))
        menu.addAction(action("Guardar", self.save_dialog, "Ctrl+S", "menu.file.save"))
        menu.addAction(action("Guardar como…", lambda: self.save_dialog(True), "",
                              "menu.file.save_as"))
        calc = self.menuBar().addMenu("&Cálculo")
        self.calc_action = action("Calcular", self.calculate, "F5", "menu.calc.run")
        calc.addAction(self.calc_action)
        export = self.menuBar().addMenu("&Exportar")
        for key, label, suffix in (("html", "Memoria HTML…", ".html"),
                                   ("docx", "Memoria Word…", ".docx"),
                                   ("pdf", "Memoria PDF…", ".pdf"),
                                   ("dxf", "Plano DXF…", ".dxf"),
                                   ("step", "Modelo STEP…", ".step"),
                                   ("stl", "Modelo STL…", ".stl")):
            item = action(label, lambda _c=False, k=key, s=suffix: self.export(k, s),
                          "", f"menu.export.{key}")
            item.setEnabled(False)
            export.addAction(item)
            self._export_actions.append(item)
        help_menu = self.menuBar().addMenu("A&yuda")
        help_menu.addAction(action("Guía rápida", self._show_guide, "F1",
                                   "menu.help.guide"))
        help_menu.addAction(action("Referencia de campos",
                                   lambda: HelpDialog("fields", self).exec(), "",
                                   "menu.help.fields"))
        help_menu.addAction(action("Menús y acciones",
                                   lambda: HelpDialog("menus", self).exec(), "",
                                   "menu.help.menus"))
        help_menu.addAction(action("Verificaciones",
                                   lambda: HelpDialog("checks", self).exec(), "",
                                   "menu.help.checks"))
        help_menu.addAction(action("Acerca de", self._show_about, "",
                                   "menu.help.about"))

    def _show_guide(self) -> None:
        QMessageBox.information(
            self, "Guía rápida",
            "1. Elija el tipo de conexión y las secciones.\n"
            "2. Complete solo los campos visibles; los obligatorios llevan *.\n"
            "3. Defina los casos de carga y los métodos LRFD/ASD.\n"
            "4. Pulse Calcular (F5).\n"
            "5. Revise Resumen y Verificaciones; exporte la memoria o el plano.\n\n"
            "Cada campo tiene un tooltip y el menú Ayuda → Referencia de campos "
            "explica qué es, cómo se usa y cómo afecta al cálculo.")

    def _show_about(self) -> None:
        from openconex import __version__
        QMessageBox.about(
            self, "Acerca de OpenConex",
            f"OpenConex {__version__}\n\n"
            "Cálculo de conexiones metálicas según AISC 360-22, "
            "AISC Design Guide 1 y ACI 318-19.\n\n"
            "Software libre bajo GPL-3.0-or-later. La responsabilidad del "
            "diseño corresponde al profesional que lo firma.")

    def _build_body(self) -> None:
        form = QWidget()
        layout = QVBoxLayout(form)
        layout.addWidget(self._build_info())
        layout.addWidget(self._build_connection())
        layout.addWidget(self._build_geometry())
        layout.addWidget(self._build_cope())
        layout.addWidget(self._build_cases())
        calculate = QPushButton("Calcular")
        calculate.clicked.connect(self.calculate)
        self._tip(calculate, "action.calculate")
        layout.addWidget(calculate)
        layout.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(form)

        self.tabs = QTabWidget()
        self.summary = QTableWidget(0, 6)
        self.summary.setHorizontalHeaderLabels(
            ["Verificación", "Combinación", "Demanda", "Capacidad", "Relación", "Estado"])
        self.summary.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabs.addTab(self.summary, "Resumen")
        self.details = QTextBrowser()
        self.tabs.addTab(self.details, "Verificaciones")
        self.figures = QWidget()
        self.figure_layout = QVBoxLayout(self.figures)
        figure_scroll = QScrollArea()
        figure_scroll.setWidgetResizable(True)
        figure_scroll.setWidget(self.figures)
        self.tabs.addTab(figure_scroll, "Figuras")
        self.viewer = Viewer3D(lambda: parts_3d(self.project), swap_yz=True)
        self.tabs.addTab(self.viewer, "3D")
        for index, key in enumerate(("tab.summary", "tab.details", "tab.figures", "tab.viewer")):
            self.tabs.setTabToolTip(index, help_text(key))
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(scroll)
        splitter.addWidget(self.tabs)
        splitter.setSizes([480, 800])
        self.setCentralWidget(splitter)

    def _build_info(self) -> QGroupBox:
        group = QGroupBox("Proyecto")
        form = QFormLayout(group)
        self._info: dict[str, QLineEdit] = {}
        for key, label in (("name", "Nombre"), ("number", "Número"), ("client", "Cliente"),
                           ("engineer", "Ingeniero"), ("revision", "Revisión"),
                           ("date", "Fecha")):
            edit = QLineEdit()
            self._info[key] = edit
            form.addRow(label, edit)
            self._tip(edit, f"project.{key}")
        self.language = QComboBox()
        self.language.addItems(["es", "en"])
        form.addRow("Idioma", self.language)
        self._tip(self.language, "ui.language")
        self.units = QComboBox()
        self.units.addItems(sorted(PRESETS))
        self.units.currentTextChanged.connect(self._change_units)
        form.addRow("Unidades", self.units)
        self._tip(self.units, "ui.units")
        self._methods = {m: QCheckBox(m.value) for m in Method}
        row = QWidget()
        box = QHBoxLayout(row)
        box.setContentsMargins(0, 0, 0, 0)
        for check in self._methods.values():
            box.addWidget(check)
            self._tip(check, "ui.methods")
        form.addRow("Métodos", row)
        return group

    def _section_combo(self) -> QComboBox:
        combo = QComboBox()
        combo.setEditable(True)
        try:
            combo.addItems(aisc_shapes().labels("W"))
        except ShapeDatabaseError:
            pass
        return combo

    def _build_connection(self) -> QGroupBox:
        group = QGroupBox("Conexión")
        form = QFormLayout(group)
        self.type = QComboBox()
        for kind in ShearType:
            self.type.addItem(tr(f"shear.type.{kind.value}", "es"), kind.value)
        self.type.currentIndexChanged.connect(self._update_visible)
        form.addRow("Tipo", self.type)
        self._tip(self.type, "type")
        self.beam = self._section_combo()
        form.addRow("Viga", self.beam)
        self._tip(self.beam, "beam")
        self.support = self._section_combo()
        form.addRow("Apoyo", self.support)
        self._tip(self.support, "support")
        self.support_element = QComboBox()
        self.support_element.addItem("Ala", "flange")
        self.support_element.addItem("Alma", "web")
        form.addRow("Unido al", self.support_element)
        self._tip(self.support_element, "support_element")
        self.grade = QLineEdit()
        form.addRow("Material de placa o ángulo", self.grade)
        self._tip(self.grade, "grade")
        self.electrode = QLineEdit()
        form.addRow("Electrodo", self.electrode)
        self._tip(self.electrode, "electrode")
        self.bolt_diameter = QLineEdit()
        form.addRow("Diámetro de perno", self.bolt_diameter)
        self._tip(self.bolt_diameter, "bolt.diameter")
        self.bolt_grade = QLineEdit()
        form.addRow("Grado de perno", self.bolt_grade)
        self._tip(self.bolt_grade, "bolt.grade")
        self.threads = QComboBox()
        for value in Threads:
            self.threads.addItem(value.value, value.value)
        form.addRow("Roscas (N/X)", self.threads)
        self._tip(self.threads, "bolt.threads")
        self.hole = QComboBox()
        for value in HoleType:
            self.hole.addItem(value.value, value.value)
        form.addRow("Agujero", self.hole)
        self._tip(self.hole, "bolt.hole")
        self.deformation = QCheckBox("Deformación en el agujero considerada")
        form.addRow(self.deformation)
        self._tip(self.deformation, "deformation_considered")
        return group

    def _build_geometry(self) -> QGroupBox:
        group = QGroupBox("Geometría")
        form = QFormLayout(group)
        for name in ("rows", "lines", "bolts"):
            spin = QSpinBox()
            spin.setRange(0 if name == "rows" else 1, 2 if name == "lines" else 30)
            self._add_row(form, name, spin, "seat_bolts" if name == "bolts" else name)
        for name in QUANTITIES:
            self._add_row(form, name, QLineEdit(), LABELS.get(name, name))
        self._add_row(form, "skew", QLineEdit(), "skew")
        self._add_row(form, "two_sided", QCheckBox(), "two_sided")
        return group

    def _add_row(self, form: QFormLayout, name: str, widget: QWidget, key: str) -> None:
        label = QLabel(tr(f"input.{key}", "es"))
        form.addRow(label, widget)
        self._fields[name] = widget
        self._rows[name] = (label, widget)
        help_key = "bolts" if key == "seat_bolts" else key
        self._tip(label, help_key)
        self._tip(widget, help_key)

    def _tip(self, widget: QWidget, key: str) -> None:
        try:
            text = help_text(key)
        except KeyError:
            return
        widget.setToolTip(text)
        widget.setStatusTip(text)

    def _build_cope(self) -> QGroupBox:
        self.cope_group = QGroupBox("Destaje de la viga")
        self.cope_group.setCheckable(True)
        form = QFormLayout(self.cope_group)
        for name, label in zip(COPE_FIELDS, ("Largo c", "Profundidad superior d_c",
                                             "Profundidad inferior", "Holgura",
                                             "l_ev desde el destaje", "l_eh desde el extremo"),
                               strict=True):
            edit = QLineEdit()
            self._cope[name] = edit
            form.addRow(label, edit)
            self._tip(edit, f"cope.{name}")
            self._tip(form.labelForField(edit), f"cope.{name}")
        self.doubler_enabled = QCheckBox("Placa doble (II.A-6 C)")
        form.addRow(self.doubler_enabled)
        self._tip(self.doubler_enabled, "cope.doubler")
        for name, label, placeholder in (
                ("thickness", "Espesor t_p", "1/4 in"),
                ("depth", "Profundidad d_p", "6.5 in"),
                ("gap", "Separación a la línea del destaje", "0.5 in"),
                ("weld", "Soldadura", "3/16 in")):
            edit = QLineEdit()
            edit.setPlaceholderText(placeholder)
            self._cope_reinf[f"doubler_{name}"] = edit
            form.addRow("  " + label, edit)
            self._tip(edit, f"cope.doubler.{name}")
            self._tip(form.labelForField(edit), f"cope.doubler.{name}")
        self.stiffener_enabled = QCheckBox("Rigidizador longitudinal (II.A-6 D)")
        form.addRow(self.stiffener_enabled)
        self._tip(self.stiffener_enabled, "cope.stiffener")
        for name, label, placeholder in (
                ("width", "Ancho b_s", "4 in"),
                ("thickness", "Espesor t_s", "1/4 in"),
                ("weld", "Soldadura", "1/4 in"),
                ("length", "Longitud (opcional)", "c + d_c")):
            edit = QLineEdit()
            edit.setPlaceholderText(placeholder)
            self._cope_reinf[f"stiffener_{name}"] = edit
            form.addRow("  " + label, edit)
            self._tip(edit, f"cope.stiffener.{name}")
            self._tip(form.labelForField(edit), f"cope.stiffener.{name}")
        return self.cope_group

    def _build_cases(self) -> QGroupBox:
        group = QGroupBox("Casos de carga (P: tracción negativa)")
        layout = QVBoxLayout(group)
        self.cases = QTableWidget(0, 4)
        self.cases.setHorizontalHeaderLabels(["Nombre", "Tipo", "V", "P"])
        layout.addWidget(self.cases)
        self._tip(self.cases, "ui.cases")
        buttons = QHBoxLayout()
        add = QPushButton("Agregar")
        add.clicked.connect(lambda: self._add_case("", "D", "", ""))
        remove = QPushButton("Quitar")
        remove.clicked.connect(lambda: self.cases.removeRow(self.cases.currentRow()))
        self._tip(add, "ui.cases")
        self._tip(remove, "ui.cases")
        buttons.addWidget(add)
        buttons.addWidget(remove)
        layout.addLayout(buttons)
        return group

    def _add_case(self, name: str, kind: str, V: str, P: str) -> None:
        row = self.cases.rowCount()
        self.cases.insertRow(row)
        self.cases.setItem(row, 0, QTableWidgetItem(name))
        combo = QComboBox()
        combo.addItems(CASE_TYPES)
        combo.setCurrentText(kind)
        self.cases.setCellWidget(row, 1, combo)
        self.cases.setItem(row, 2, QTableWidgetItem(V))
        self.cases.setItem(row, 3, QTableWidgetItem(P))

    # -- form <-> project ---------------------------------------------------------
    def _update_visible(self) -> None:
        kind = ShearType(self.type.currentData())
        shown = set(TYPE_FIELDS[kind])
        required = set(REQUIRED[kind])
        for name, (label, widget) in self._rows.items():
            visible = name in shown
            label.setVisible(visible)
            widget.setVisible(visible)
            text = tr(f"input.{'seat_bolts' if name == 'bolts' else name}", "es")
            label.setText(f"{text} *" if name in required else text)

    def _change_units(self, name: str) -> None:
        if name == CUSTOM_UNITS:
            return
        new = PRESETS.get(name)
        if new is None or new.name == self._units.name:
            return
        old = self._units
        try:
            lines, case_lines = self._converted_lines(old, new)
        except ValueError as exc:
            QMessageBox.warning(self, "Unidades", str(exc))
            with QSignalBlocker(self.units):
                self.units.setCurrentText(
                    old.name if old.name in PRESETS else CUSTOM_UNITS)
            return
        for widget, text in lines:
            widget.setText(text)
        for item, text in case_lines:
            item.setText(text)
        self._units = new
        self.project.info.units = name
        custom = self.units.findText(CUSTOM_UNITS)
        if custom >= 0:
            self.units.removeItem(custom)
        self.statusBar().showMessage(f"Unidades convertidas a {name}.")

    def _converted_lines(self, old, new) -> tuple[
            list[tuple[QLineEdit, str]], list[tuple[QTableWidgetItem, str]]]:
        lines: list[tuple[QLineEdit, str]] = []
        case_lines: list[tuple[QTableWidgetItem, str]] = []
        for name in ("spacing", "gage", "length", "width", "lev", "leh", "leh_support",
                     "a", "beam_leg", "outstanding_leg", "beam_leh", "leg",
                     "vertical_leg", "bearing_length", "row_distance", "load_offset",
                     "plate_a_width", "plate_b_width", "weld_return", "weld_offset"):
            self._collect_line(lines, self._fields.get(name), Kind.LENGTH, old, new)
        for name in ("thickness", "weld", "support_weld", "beam_weld"):
            self._collect_line(lines, self._fields.get(name), Kind.THICKNESS, old, new)
        self._collect_line(lines, self._fields.get("beam_area"), Kind.AREA, old, new)
        self._collect_line(lines, self.bolt_diameter, Kind.LENGTH, old, new)
        for edit in self._cope.values():
            self._collect_line(lines, edit, Kind.LENGTH, old, new)
        for name in ("doubler_depth", "doubler_gap", "stiffener_width", "stiffener_length"):
            self._collect_line(lines, self._cope_reinf.get(name), Kind.LENGTH, old, new)
        for name in ("doubler_thickness", "doubler_weld", "stiffener_thickness",
                     "stiffener_weld"):
            self._collect_line(lines, self._cope_reinf.get(name), Kind.THICKNESS, old, new)
        for row in range(self.cases.rowCount()):
            for col in (2, 3):
                item = self.cases.item(row, col)
                if item is not None and item.text().strip():
                    case_lines.append(
                        (item, convert_text(item.text().strip(), Kind.FORCE, old, new)))
        return lines, case_lines

    @staticmethod
    def _collect_line(lines: list[tuple[QLineEdit, str]], widget, kind: Kind,
                      old, new) -> None:
        if isinstance(widget, QLineEdit) and widget.text().strip():
            lines.append((widget, convert_text(widget.text().strip(), kind, old, new)))

    def _fill(self, project: Project) -> None:
        info = project.info
        for key, edit in self._info.items():
            edit.setText(_text(getattr(info, key)))
        self.language.setCurrentText(info.language)
        self._units = info.unit_system()
        with QSignalBlocker(self.units):
            if isinstance(info.units, str):
                self.units.setCurrentText(info.units)
            else:
                if self.units.findText(CUSTOM_UNITS) < 0:
                    self.units.addItem(CUSTOM_UNITS)
                self.units.setCurrentText(CUSTOM_UNITS)
        for method, check in self._methods.items():
            check.setChecked(method in project.combinations.methods)
        sc = project.shear_connection
        self.type.setCurrentIndex(self.type.findData(sc.type.value))
        self.beam.setCurrentText(sc.beam if isinstance(sc.beam, str) else sc.beam.label())
        self.support.setCurrentText(sc.support if isinstance(sc.support, str)
                                    else sc.support.label())
        self.support_element.setCurrentIndex(self.support_element.findData(sc.support_element))
        self.grade.setText(sc.grade)
        self.electrode.setText(sc.electrode)
        self.bolt_diameter.setText(_text(sc.bolt.diameter))
        self.bolt_grade.setText(sc.bolt.grade)
        self.threads.setCurrentIndex(self.threads.findData(sc.bolt.threads.value))
        self.hole.setCurrentIndex(self.hole.findData(sc.bolt.hole.value))
        self.deformation.setChecked(sc.deformation_considered)
        for name, widget in self._fields.items():
            value = getattr(sc, name)
            if isinstance(widget, QSpinBox):
                widget.setValue(value or 0)
            elif isinstance(widget, QCheckBox):
                widget.setChecked(bool(value))
            else:
                widget.setText(_text(value))
        self.cope_group.setChecked(sc.cope is not None)
        for name, edit in self._cope.items():
            value = None if sc.cope is None else getattr(sc.cope, name)
            edit.setText("" if value in (None, 0, 0.0) else _text(value))
        doubler = None if sc.cope is None else sc.cope.doubler
        stiffener = None if sc.cope is None else sc.cope.stiffener
        self.doubler_enabled.setChecked(doubler is not None)
        self.stiffener_enabled.setChecked(stiffener is not None)
        for name, edit in self._cope_reinf.items():
            group, field = name.split("_", 1)
            value = getattr(doubler if group == "doubler" else stiffener, field, None)
            edit.setText("" if value in (None, 0, 0.0) else _text(value))
        self.cases.setRowCount(0)
        for case in project.cases:
            self._add_case(case.name, case.type.value,
                           *("" if v in (0, 0.0) else _text(v) for v in (case.V, case.P)))
        self._update_visible()
        self._update_title()

    def project_from_form(self) -> Project:
        """Project built from the form; raises ``ValueError`` when it is not valid."""
        kind = ShearType(self.type.currentData())
        shown = set(TYPE_FIELDS[kind])
        connection: dict = {
            "type": kind.value, "beam": self.beam.currentText().strip().upper(),
            "support": self.support.currentText().strip().upper(),
            "support_element": self.support_element.currentData(),
            "grade": self.grade.text().strip(), "electrode": self.electrode.text().strip(),
            "deformation_considered": self.deformation.isChecked(),
            "bolt": {"diameter": self.bolt_diameter.text().strip(),
                     "grade": self.bolt_grade.text().strip(),
                     "threads": self.threads.currentData(), "hole": self.hole.currentData()},
        }
        for name, widget in self._fields.items():
            if name not in shown:
                continue
            if isinstance(widget, QSpinBox):
                if widget.value():
                    connection[name] = widget.value()
            elif isinstance(widget, QCheckBox):
                connection[name] = widget.isChecked()
            elif widget.text().strip():
                connection[name] = widget.text().strip()
        if self.project.shear_connection is not None:
            for name in HIDDEN_FIELDS:
                value = getattr(self.project.shear_connection, name, None)
                if value is not None:
                    connection.setdefault(name, value)
        if self.cope_group.isChecked():
            cope = {name: edit.text().strip() for name, edit in self._cope.items()
                    if edit.text().strip()}
            if self.doubler_enabled.isChecked():
                cope["doubler"] = {
                    name: self._cope_reinf[f"doubler_{name}"].text().strip()
                    for name in DOUBLER_FIELDS
                    if self._cope_reinf[f"doubler_{name}"].text().strip()}
            if self.stiffener_enabled.isChecked():
                cope["stiffener"] = {
                    name: self._cope_reinf[f"stiffener_{name}"].text().strip()
                    for name in STIFFENER_FIELDS
                    if self._cope_reinf[f"stiffener_{name}"].text().strip()}
            connection["cope"] = cope
        cases = []
        for row in range(self.cases.rowCount()):
            name = (self.cases.item(row, 0) or QTableWidgetItem("")).text().strip()
            if not name:
                continue
            case = {"name": name, "type": self.cases.cellWidget(row, 1).currentText()}
            for col, key in ((2, "V"), (3, "P")):
                text = (self.cases.item(row, col) or QTableWidgetItem("")).text().strip()
                if text:
                    case[key] = text
            cases.append(case)
        info = self.project.info.model_dump()
        info.update({k: e.text().strip() for k, e in self._info.items()})
        info.update(language=self.language.currentText())
        if self.units.currentText() != CUSTOM_UNITS:
            info["units"] = self.units.currentText()
        combinations = self.project.combinations.model_dump()
        combinations["methods"] = [m.value for m, c in self._methods.items() if c.isChecked()]
        data = {"info": info, "materials": [m.model_dump() for m in self.project.materials],
                "bolts": [b.model_dump() for b in self.project.bolts],
                "electrodes": [e.model_dump() for e in self.project.electrodes],
                "shear_connection": connection, "cases": cases,
                "combinations": combinations}
        try:
            return Project.model_validate(data)
        except Exception as exc:  # pydantic ValidationError and unit errors
            raise ValueError(str(exc)) from exc

    # -- actions --------------------------------------------------------------------
    def _update_title(self) -> None:
        name = self.path.name if self.path else "sin guardar"
        self.setWindowTitle(f"OpenConex — conexión de corte — {name}")

    def new_project(self) -> None:
        self.project, self.path, self.report = Project.model_validate(TEMPLATE), None, None
        self._fill(self.project)
        self._set_export_enabled(False)

    def open_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Abrir proyecto", "",
                                               "OpenConex (*.ocnx);;Todos (*)")
        if path:
            self.open(path)

    def open(self, path: str | Path) -> bool:
        try:
            project = load_project(path)
        except Exception as exc:
            QMessageBox.critical(self, "Error al abrir", str(exc))
            return False
        if project.shear_connection is None:
            QMessageBox.warning(self, "Proyecto de placa base",
                                "Ese proyecto es una placa base; ábralo en la ventana principal.")
            return False
        self.project, self.path, self.report = project, Path(path), None
        self._fill(project)
        self._set_export_enabled(False)
        return True

    def save_dialog(self, save_as: bool = False) -> None:
        path = self.path
        if save_as or path is None:
            selected, _ = QFileDialog.getSaveFileName(self, "Guardar proyecto", "",
                                                       "OpenConex (*.ocnx)")
            if not selected:
                return
            path = Path(selected).with_suffix(".ocnx")
        self.save_to(path)

    def save_to(self, path: str | Path) -> bool:
        try:
            project = self.project_from_form()
            save_project(project, path)
        except Exception as exc:
            QMessageBox.critical(self, "Error al guardar", str(exc))
            return False
        self.project, self.path = project, Path(path)
        self._update_title()
        self.statusBar().showMessage(f"Proyecto guardado: {path}")
        return True

    def calculate(self) -> bool:
        try:
            self.project = self.project_from_form()
            self.report = build_shear_report(self.project)
        except Exception as exc:
            QMessageBox.critical(self, "Datos no válidos", str(exc))
            return False
        self._show_report(self.report)
        self._set_export_enabled(True)
        self.statusBar().showMessage("Cumple" if self.report.ok else "No cumple")
        return True

    def _show_report(self, report: Report) -> None:
        self.summary.setRowCount(0)
        for row in report.summary:
            index = self.summary.rowCount()
            self.summary.insertRow(index)
            for col, value in enumerate([*row.cells, row.status]):
                self.summary.setItem(index, col, QTableWidgetItem(str(value)))
        self.summary.resizeColumnsToContents()
        lines = []
        for block in report.checks:
            lines.append(f"{block.title} — {block.status.upper()} ({block.combo})")
            lines.append(f"  {block.clause}")
            for line in block.lines:
                lines.append(f"  {line.symbol} = {line.value}    {line.clause}")
            lines.append(f"  Demanda / capacidad = {block.demand} / {block.capacity}"
                         f" = {block.ratio:.3f}")
            lines.append("")
        self.details.setPlainText("\n".join(lines))
        while self.figure_layout.count():
            item = self.figure_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        for figure in report.figures:
            pixmap = QPixmap()
            if figure.png and pixmap.loadFromData(figure.png):
                label = QLabel()
                label.setPixmap(pixmap.scaledToWidth(
                    760, Qt.TransformationMode.SmoothTransformation))
                self.figure_layout.addWidget(label)
                self.figure_layout.addWidget(QLabel(figure.caption))
        self.figure_layout.addStretch(1)
        self.tabs.setCurrentIndex(0)

    def _set_export_enabled(self, enabled: bool) -> None:
        for action in self._export_actions:
            action.setEnabled(enabled)

    def export(self, kind: str, suffix: str, path: str | Path | None = None) -> Path | None:
        if self.report is None:
            return None
        if path is None:
            selected, _ = QFileDialog.getSaveFileName(self, "Exportar", "", f"*{suffix}")
            if not selected:
                return None
            path = selected
        target = Path(path).with_suffix(suffix)
        try:
            if kind == "html":
                write_html(self.report, target)
            elif kind == "docx":
                write_docx(self.report, target)
            elif kind == "pdf":
                write_pdf(self.report, target)
            elif kind == "dxf":
                write_dxf(self.project, target)
            else:
                write_3d(self.project, target, kind)
        except Exception as exc:
            QMessageBox.critical(self, "Error al exportar", str(exc))
            return None
        self.statusBar().showMessage(f"Exportado: {target}")
        return target
