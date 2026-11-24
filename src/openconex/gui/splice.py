# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Editor window for beam and column splice projects.

Quantities are typed as in the project file, text with its unit (``5/8 in``,
``300 kip*ft``); a bare number uses the unit system of the project.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QSpinBox,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from openconex.core.loads import LoadType
from openconex.gui.connection_window import ConnectionWindow
from openconex.gui.start_data import SPLICE_BEAM as BEAM_TEMPLATE
from openconex.gui.start_data import SPLICE_COLUMN as COLUMN_TEMPLATE
from openconex.i18n import tr
from openconex.io.project import Project
from openconex.io.splice_project import SpliceType
from openconex.units import Kind

__all__ = ["BEAM_TEMPLATE", "COLUMN_TEMPLATE", "SpliceWindow"]

FLANGE_FIELDS = (("spacing", "Separación s"), ("gage", "Gramil g"),
                 ("width", "Ancho de la cubreplaca exterior"),
                 ("thickness", "Espesor de la cubreplaca exterior"),
                 ("lev_member", "Extremo del perfil al primer perno"),
                 ("lev_plate", "Último perno al extremo de la placa"),
                 ("inner_width", "Cubreplacas interiores: ancho (vacío: sin placas)"),
                 ("inner_thickness", "Cubreplacas interiores: espesor"))
WEB_FIELDS = (("spacing", "Separación vertical"), ("height", "Altura de las placas"),
              ("thickness", "Espesor de cada placa"),
              ("lev_member", "Extremo del perfil a la primera línea"),
              ("leh_plate", "Última línea al extremo de la placa"),
              ("column_spacing", "Separación entre líneas"))
CASE_COLUMNS = (("V", "V"), ("M", "M"), ("P", "P"), ("V_weak", "V débil"))


def _text(value) -> str:
    return "" if value is None else str(value)


class SpliceWindow(ConnectionWindow):
    """Editor, calculation and outputs of one splice project."""

    family_key = "splice"
    template = BEAM_TEMPLATE
    noun = "empalme"
    start_message = "Edite el empalme y pulse Calcular (F5)."
    _session_key = "splice"

    # -- construction ------------------------------------------------------------------
    def _new_actions(self):
        return [("Nuevo empalme de viga", self.new_project, "Ctrl+N", "menu.file.new"),
                ("Nuevo empalme de columna", lambda: self.new_project(SpliceType.COLUMN), "",
                 "menu.file.new")]

    def _spin(self, form: QFormLayout, label: str, top: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(1, top)
        form.addRow(label, spin)
        return spin

    def _build_body(self) -> None:
        form_widget = QWidget()
        self._form = form_widget
        layout = QVBoxLayout(form_widget)

        info, _ = self._build_info_group()
        layout.addWidget(info)

        members = QGroupBox("Empalme")
        form = QFormLayout(members)
        self.type = QComboBox()
        for kind in SpliceType:
            self.type.addItem(tr(f"splice.type.{kind.value}", "es"), kind.value)
        self.type.currentIndexChanged.connect(self._update_visible)
        form.addRow("Tipo", self.type)
        self.beam = self._section_combo()
        self.beam_label = QLabel("Viga")
        form.addRow(self.beam_label, self.beam)
        self.upper = self._section_combo()
        self.upper_label = QLabel("Columna superior")
        form.addRow(self.upper_label, self.upper)
        self.lower = self._section_combo()
        self.lower_label = QLabel("Columna inferior")
        form.addRow(self.lower_label, self.lower)
        self.member_grade = self._line(form, "Material del perfil")
        self.grade = self._line(form, "Material de las cubreplacas")
        self.gap = self._line(form, "Separación entre extremos (vacío: 1/2 in viga, 0 columna)")
        self.finished = QCheckBox("Extremos fresados (compresión por aplastamiento)")
        form.addRow(self.finished)
        self.developed = QCheckBox("Rellenos extendidos y desarrollados (§J5.2)")
        form.addRow(self.developed)
        layout.addWidget(members)

        flange = QGroupBox("Cubreplacas de ala")
        form = QFormLayout(flange)
        self.flange_bolt = self._line(form, "Diámetro de perno")
        self.flange_bolt_grade = self._line(form, "Material de los pernos")
        self.flange_rows = self._spin(form, "Pernos por línea a cada lado", 20)
        self._flange = {key: self._line(form, label) for key, label in FLANGE_FIELDS}
        layout.addWidget(flange)

        self.web_group = QGroupBox("Cubreplacas del alma")
        self.web_group.setCheckable(True)
        form = QFormLayout(self.web_group)
        self.web_bolt = self._line(form, "Diámetro de perno")
        self.web_bolt_grade = self._line(form, "Material de los pernos")
        self.web_rows = self._spin(form, "Pernos por línea", 30)
        self.web_columns = self._spin(form, "Líneas a cada lado", 4)
        self._web = {key: self._line(form, label) for key, label in WEB_FIELDS}
        layout.addWidget(self.web_group)

        layout.addWidget(self._build_cases_group(
            "Casos de carga en el empalme (P de compresión positiva; V débil solo en columnas)",
            ["Nombre", "Tipo", *(label for _, label in CASE_COLUMNS)],
            lambda: self._add_case("", "D", {})))
        self._end_form(layout)
        self._build_results(form_widget)

    def _unit_fields(self):
        """Every quantity field of the form with its magnitude."""
        for group in (self._flange, self._web):
            for name, edit in group.items():
                if isinstance(edit, QLineEdit):
                    yield edit, Kind.THICKNESS if "thickness" in name else Kind.LENGTH
        for edit in (self.gap, self.flange_bolt, self.web_bolt):
            yield edit, Kind.LENGTH
        kinds = {"V": Kind.FORCE, "M": Kind.MOMENT, "P": Kind.FORCE, "V_weak": Kind.FORCE}
        for row in range(self.cases.rowCount()):
            for col, (key, _) in enumerate(CASE_COLUMNS, start=2):
                yield self.cases.item(row, col), kinds[key]

    def _add_case(self, name: str, kind: str, values: dict[str, str]) -> None:
        row = self.cases.rowCount()
        self.cases.insertRow(row)
        self.cases.setItem(row, 0, QTableWidgetItem(name))
        combo = QComboBox()
        combo.addItems([t.value for t in LoadType])
        combo.setCurrentText(kind)
        combo.currentIndexChanged.connect(self._mark_modified)
        self.cases.setCellWidget(row, 1, combo)
        for col, (key, _) in enumerate(CASE_COLUMNS, start=2):
            self.cases.setItem(row, col, QTableWidgetItem(values.get(key, "")))

    # -- form <-> project ----------------------------------------------------------------
    def _kind(self) -> SpliceType:
        return SpliceType(self.type.currentData())

    def _update_visible(self) -> None:
        column = self._kind() is SpliceType.COLUMN
        for widget in (self.beam, self.beam_label):
            widget.setVisible(not column)
        for widget in (self.upper, self.upper_label, self.lower, self.lower_label,
                       self.finished, self.developed):
            widget.setVisible(column)
        if not column:
            self.web_group.setChecked(True)

    def _fill(self, project: Project) -> None:
        self._fill_info(project)
        sp = project.splice
        self.type.setCurrentIndex(self.type.findData(sp.type.value))
        column = sp.type is SpliceType.COLUMN

        def label(section, default: str) -> str:
            if section is None:
                return default
            return section if isinstance(section, str) else section.label()

        self.beam.setCurrentText(label(sp.beam, "W21X62"))
        self.upper.setCurrentText(label(sp.upper, "W14X90"))
        self.lower.setCurrentText(label(sp.lower, "W14X132"))
        self.member_grade.setText(sp.column_grade if column else sp.beam_grade)
        self.grade.setText(sp.grade)
        self.gap.setText(_text(sp.gap))
        self.finished.setChecked(sp.finished_ends)
        self.developed.setChecked(sp.filler_developed)
        f = sp.flange
        self.flange_bolt.setText(_text(f.bolt.diameter))
        self.flange_bolt_grade.setText(f.bolt.grade)
        self.flange_rows.setValue(f.rows)
        for key, edit in self._flange.items():
            edit.setText(_text(getattr(f, key)))
        w = sp.web
        self.web_group.setChecked(w is not None)
        template = BEAM_TEMPLATE["splice"]["web"]
        self.web_bolt.setText(_text(w.bolt.diameter) if w else template["bolt"]["diameter"])
        self.web_bolt_grade.setText(w.bolt.grade if w else "ASTM F3125 Gr. A325")
        self.web_rows.setValue(w.rows if w else template["rows"])
        self.web_columns.setValue(w.columns if w else 1)
        for key, edit in self._web.items():
            edit.setText(_text(getattr(w, key)) if w else _text(template.get(key)))
        self.cases.setRowCount(0)
        for case in project.cases:
            values = {key: _text(getattr(case, key)) for key, _ in CASE_COLUMNS
                      if getattr(case, key) not in (0, 0.0)}
            self._add_case(case.name, case.type.value, values)
        self._update_visible()
        self._update_title()

    def _section(self, combo: QComboBox, key: str):
        """Catalog label, or the project's generic section when its label is kept."""
        text = combo.currentText().strip()
        current = getattr(self.project.splice, key)
        if current is not None and not isinstance(current, str) and text == current.label():
            return current.model_dump()
        return text.upper()

    def project_from_form(self) -> Project:
        kind = self._kind()
        splice: dict = {"type": kind.value, "grade": self.grade.text().strip(),
                        "deformation_considered": self.project.splice.deformation_considered}
        grade = self.member_grade.text().strip()
        if kind is SpliceType.BEAM:
            splice["beam"] = self._section(self.beam, "beam")
            if grade:
                splice["beam_grade"] = grade
        else:
            splice["upper"] = self._section(self.upper, "upper")
            splice["lower"] = self._section(self.lower, "lower")
            splice["finished_ends"] = self.finished.isChecked()
            splice["filler_developed"] = self.developed.isChecked()
            if grade:
                splice["column_grade"] = grade
        if self.gap.text().strip():
            splice["gap"] = self.gap.text().strip()
        flange = {"bolt": {"diameter": self.flange_bolt.text().strip(),
                           "grade": self.flange_bolt_grade.text().strip()
                           or "ASTM F3125 Gr. A325"},
                  "rows": self.flange_rows.value()}
        flange.update({k: e.text().strip() for k, e in self._flange.items()
                       if e.text().strip()})
        splice["flange"] = flange
        if self.web_group.isChecked():
            web = {"bolt": {"diameter": self.web_bolt.text().strip(),
                            "grade": self.web_bolt_grade.text().strip()
                            or "ASTM F3125 Gr. A325"},
                   "rows": self.web_rows.value(), "columns": self.web_columns.value()}
            web.update({k: e.text().strip() for k, e in self._web.items()
                        if e.text().strip()})
            splice["web"] = web
        cases = []
        for row in range(self.cases.rowCount()):
            name = (self.cases.item(row, 0) or QTableWidgetItem("")).text().strip()
            if not name:
                continue
            case = {"name": name, "type": self.cases.cellWidget(row, 1).currentText()}
            for col, (key, _) in enumerate(CASE_COLUMNS, start=2):
                text = (self.cases.item(row, col) or QTableWidgetItem("")).text().strip()
                if text:
                    case[key] = text
            cases.append(case)
        return self._validated(self._project_data(splice=splice, cases=cases))

    # -- actions -----------------------------------------------------------------------
    def new_project(self, kind: SpliceType = SpliceType.BEAM) -> None:  # type: ignore[override]
        super().new_project(BEAM_TEMPLATE if kind is SpliceType.BEAM else COLUMN_TEMPLATE)
