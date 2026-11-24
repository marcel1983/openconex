# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Editor window for beam-end shear connection projects.

Quantities are typed as in the project file: text with its unit (``3 in``,
``25 kip``); a bare number uses the unit system of the project. The fields
shown follow the connection type.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from openconex.connections.shear.check import ShearType
from openconex.core.loads import LoadType
from openconex.core.model import HoleType, Threads
from openconex.gui.connection_window import ConnectionWindow
from openconex.gui.help import HelpDialog
from openconex.i18n import tr
from openconex.io.project import Project
from openconex.io.shear_project import REQUIRED
from openconex.units import Kind

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
# Viewer-only offsets for the exploded inspection view [mm], in the model axes
# of the shear connection (x along the beam, y up, z across the web).
EXPLODE_BY_TYPE = {
    "double_angle": {"beam": (0.0, 0.0, -250.0)},
    "single_plate": {"beam": (0.0, 0.0, -200.0)},
    "extended_single_plate": {"beam": (0.0, 0.0, -200.0)},
    "end_plate": {"beam": (80.0, 0.0, -260.0),
                  "end_plate": (80.0, 0.0, 0.0),
                  "support_bolt*": (80.0, 0.0, 0.0)},
    "seated": {"beam": (80.0, 220.0, 0.0)},
    "stiffened_seat": {"beam": (80.0, 240.0, 0.0)},
    "skewed_bent_plate": None,
}
CASE_TYPES = [t.value for t in LoadType]

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


class ShearWindow(ConnectionWindow):
    """Editor, calculation and outputs of one shear connection project."""

    family_key = "shear_connection"
    template = TEMPLATE
    noun = "conexión de corte"
    _session_key = "shear"

    def _init_state(self) -> None:
        self._fields: dict[str, QWidget] = {}
        self._rows: dict[str, tuple[QLabel, QWidget]] = {}
        self._cope: dict[str, QLineEdit] = {}
        self._cope_reinf: dict[str, QLineEdit] = {}

    # -- construction -----------------------------------------------------------
    def _build_extra_menus(self) -> None:
        help_menu = self.menuBar().addMenu("A&yuda")
        help_menu.addAction(self._action("Guía rápida", self._show_guide, "F1",
                                         "menu.help.guide"))
        for label, topic in (("Referencia de campos", "fields"), ("Menús y acciones", "menus"),
                             ("Verificaciones", "checks")):
            help_menu.addAction(self._action(
                label, lambda t=topic: HelpDialog(t, self).exec(), "", f"menu.help.{topic}"))
        help_menu.addAction(self._action("Acerca de", self._show_about, "",
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
        self._form = form
        layout = QVBoxLayout(form)
        layout.addWidget(self._build_info_group()[0])
        layout.addWidget(self._build_connection())
        layout.addWidget(self._build_geometry())
        layout.addWidget(self._build_cope())
        layout.addWidget(self._build_cases())
        self._end_form(layout)
        self._build_results(form, y_up=True, explode=self._explode_for_current_type())

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
        return self._build_cases_group("Casos de carga (P: tracción negativa)",
                                       ["Nombre", "Tipo", "V", "P"],
                                       lambda: self._add_case("", "D", "", ""))

    def _add_case(self, name: str, kind: str, V: str, P: str) -> None:
        row = self.cases.rowCount()
        self.cases.insertRow(row)
        self.cases.setItem(row, 0, QTableWidgetItem(name))
        combo = QComboBox()
        combo.addItems(CASE_TYPES)
        combo.setCurrentText(kind)
        combo.currentIndexChanged.connect(self._mark_modified)
        self.cases.setCellWidget(row, 1, combo)
        self.cases.setItem(row, 2, QTableWidgetItem(V))
        self.cases.setItem(row, 3, QTableWidgetItem(P))

    # -- form <-> project ---------------------------------------------------------
    def _explode_for_current_type(self):
        return EXPLODE_BY_TYPE.get(self.type.currentData())

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
        if hasattr(self, "viewer"):
            self.viewer.set_explode_spec(self._explode_for_current_type())

    def _unit_fields(self):
        """Every quantity field of the form with its magnitude."""
        for name in ("spacing", "gage", "length", "width", "lev", "leh", "leh_support",
                     "a", "beam_leg", "outstanding_leg", "beam_leh", "leg",
                     "vertical_leg", "bearing_length", "row_distance", "load_offset",
                     "plate_a_width", "plate_b_width", "weld_return", "weld_offset"):
            yield self._line_field(name), Kind.LENGTH
        for name in ("thickness", "weld", "support_weld", "beam_weld"):
            yield self._line_field(name), Kind.THICKNESS
        yield self._line_field("beam_area"), Kind.AREA
        yield self.bolt_diameter, Kind.LENGTH
        for edit in self._cope.values():
            yield edit, Kind.LENGTH
        for name, edit in self._cope_reinf.items():
            field = name.split("_", 1)[1]
            yield edit, Kind.THICKNESS if field in ("thickness", "weld") else Kind.LENGTH
        for row in range(self.cases.rowCount()):
            for col in (2, 3):
                yield self.cases.item(row, col), Kind.FORCE

    def _line_field(self, name: str) -> QLineEdit | None:
        widget = self._fields.get(name)
        return widget if isinstance(widget, QLineEdit) else None

    def _fill(self, project: Project) -> None:
        self._fill_info(project)
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
        return self._validated(self._project_data(shear_connection=connection, cases=cases))
