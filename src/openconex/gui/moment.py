# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Editor window for beam-to-column moment connection projects.

Quantities are typed as in the project file, text with its unit (``3/4 in``,
``252 kip*ft``); a bare number uses the unit system of the project.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QSpinBox,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from openconex.connections.moment.end_plate import EndPlateLayout
from openconex.connections.moment.fr_moment import FlangeDetail
from openconex.connections.moment.seismic import Prequalified, SeismicSystem
from openconex.core.loads import LoadType
from openconex.gui.connection_window import ConnectionWindow
from openconex.i18n import tr
from openconex.io.moment_project import MomentConnectionInput
from openconex.io.project import Project
from openconex.units import Kind

__all__ = ["MomentWindow"]

TEMPLATE = {
    "info": {"name": "Conexión de momento", "language": "es", "units": "US"},
    "moment_connection": {
        "type": "bolted_flange_plate", "beam": "W18X50", "column": "W14X99",
        "web": {"bolt": {"diameter": "7/8 in"}, "rows": 3, "spacing": "3 in",
                "length": "9 in", "thickness": "3/8 in", "lev": "1.5 in", "leh": "2 in",
                "weld": "1/4 in"},
        "top": {"width": "7 in", "thickness": "3/4 in", "weld_to_column": "3/8 in",
                "unbraced_length": "3 in"},
        "bolt": {"diameter": "7/8 in"}, "rows": 4, "spacing": "3 in", "gage": "4 in",
        "plate_lev": "1.5 in", "beam_lev": "1.5 in"},
    "cases": [{"name": "D", "type": "D", "V": "7 kip", "M": "42 kip*ft"},
              {"name": "L", "type": "L", "V": "21 kip", "M": "126 kip*ft"}],
    "combinations": {"methods": ["LRFD", "ASD"]},
}
WEB_FIELDS = (("spacing", "Separación s"), ("length", "Largo"), ("thickness", "Espesor"),
              ("lev", "l_ev"), ("leh", "l_eh"), ("weld", "Soldadura a la columna"))
PLATE_FIELDS = (("width", "Ancho"), ("thickness", "Espesor"),
                ("weld_to_column", "Soldadura a la columna"),
                ("unbraced_length", "Longitud libre (compresión)"),
                ("weld_to_beam", "Soldadura a la viga"),
                ("weld_length", "Largo de cada soldadura longitudinal"))
END_PLATE_FIELDS = (("width", "Ancho b_p"), ("thickness", "Espesor t_p"), ("gage", "Gramil g"),
                    ("pf", "p_f (p_f,i): fila interior a la cara del ala"),
                    ("pb", "p_b entre filas interiores"),
                    ("pf_o", "p_f,o: fila exterior a la cara del ala"),
                    ("pext", "p_ext: extensión de la placa"),
                    ("ps_o", "p_s,o: fila exterior al rigidizador (Tabla 3-4)"),
                    ("stiffener_thickness", "t_s del rigidizador (Tabla 3-4)"),
                    ("ps", "p_s: fila al rigidizador (Tabla 3-5)"),
                    ("pretension", "Pretensión T_b (vacío: Tabla J3.1)"),
                    ("web_weld", "Filete del alma (vacío: CJP)"),
                    ("flange_weld", "Filete de las alas (vacío: CJP)"),
                    ("weld_reinforcement", "Refuerzo de la soldadura CJP (DG4: N)"))
STIFFENING_FIELDS = (
    ("continuity_plate", "Rigidizadores: espesor t_s (vacío: sin rigidizadores)"),
    ("continuity_plate_width", "Ancho b_s (vacío: (b_fc − t_wc)/2)"),
    ("continuity_plate_clip", "Recorte de esquina"),
    ("continuity_plate_length", "Largo (vacío: altura libre o la mitad)"),
    ("continuity_plate_weld", "Filete a las alas (vacío: CJP)"),
    ("continuity_plate_web_weld", "Filete al alma (vacío: no se verifica)"),
    ("doubler_plate", "Doble placa del alma: espesor total"),
    ("doubler_weld", "Filete de la doble placa a las alas (vacío: CJP)"))
FLANGE_BOLT_FIELDS = (("spacing", "Separación s"), ("gage", "Gramil g"),
                      ("plate_lev", "l_ev de la placa"), ("beam_lev", "l_ev de la viga"))


SEISMIC_FIELDS = [
    ("span", "Luz libre entre caras de columnas L_cf"),
    ("gravity_load", "Carga gravitacional mayorada w_u (1,2D + f₁L + 0,15S)"),
    ("gravity_shear", "Corte gravitacional adicional en la rótula"),
    ("column_axial", "Compresión mayorada de la columna P_uc"),
    ("rbs_a", "RBS: distancia a de la cara al corte"),
    ("rbs_b", "RBS: largo b del corte"),
    ("rbs_c", "RBS: profundidad c del corte"),
    ("bfp_s1", "BFP: cara de la columna a la primera fila S₁"),
    ("stiffener_thickness", "BSEEP: espesor del rigidizador"),
    ("Ry_beam", "R_y de la viga (vacío: AISC 341 Tabla A3.2)"),
    ("Rt_beam", "R_t de la viga"),
    ("Ry_column", "R_y de la columna"),
    ("Ry_plate", "R_y de las placas (ala BFP, placa simple WUF-W, continuidad)"),
]
"""Fields of the AISC 358 group of the moment window."""


def _text(value) -> str:
    return "" if value is None else str(value)


class MomentWindow(ConnectionWindow):
    """Editor, calculation and outputs of one moment connection project."""

    family_key = "moment_connection"
    template = TEMPLATE
    noun = "conexión de momento"
    _session_key = "moment"

    # -- construction ------------------------------------------------------------------
    def _build_body(self) -> None:
        form_widget = QWidget()
        self._form = form_widget
        layout = QVBoxLayout(form_widget)

        info, _ = self._build_info_group()
        layout.addWidget(info)

        conn = QGroupBox("Conexión")
        form = QFormLayout(conn)
        self.type = QComboBox()
        for detail in FlangeDetail:
            self.type.addItem(tr(f"moment.type.{detail.value}", "es"), detail.value)
        self.type.currentIndexChanged.connect(self._update_visible)
        form.addRow("Tipo", self.type)
        self.beam = self._section_combo()
        form.addRow("Viga", self.beam)
        self.column = self._section_combo()
        form.addRow("Columna", self.column)
        self.support = QComboBox()
        self.support.addItem("Ala de la columna", "flange")
        self.support.addItem("Alma de la columna (eje débil, DG13 Ap. D)", "web")
        form.addRow("Cara de la columna", self.support)
        self.support.currentIndexChanged.connect(self._update_visible)
        self.plate_extension = self._line(form, "Prolongación de las placas (alma; vacío: 3/4 in)")
        self.grade = self._line(form, "Material de las placas")
        self.electrode = self._line(form, "Electrodo")
        self.near_end = QCheckBox("Fuerza de ala cerca del extremo de la columna")
        form.addRow(self.near_end)
        self.two_sided = QCheckBox("Vigas a ambos lados de la columna")
        form.addRow(self.two_sided)
        layout.addWidget(conn)

        stiff = QGroupBox("Rigidización de la columna (AISC DG13)")
        form = QFormLayout(stiff)
        self._stiff = {key: self._line(form, label) for key, label in STIFFENING_FIELDS}
        self.continuity_plate = self._stiff["continuity_plate"]
        self.full_depth = QCheckBox("Rigidizadores de altura completa")
        form.addRow(self.full_depth)
        self.panel_zone = QCheckBox("Verificar la zona de panel (V_c y P_c de los casos)")
        form.addRow(self.panel_zone)
        self.panel_inelastic = QCheckBox("Deformación de la zona de panel en el análisis")
        form.addRow(self.panel_inelastic)
        layout.addWidget(stiff)

        web = self.web_group = QGroupBox("Placa del alma")
        form = QFormLayout(web)
        self.web_bolt = self._line(form, "Diámetro de perno")
        self.web_rows = QSpinBox()
        self.web_rows.setRange(1, 30)
        form.addRow("Pernos", self.web_rows)
        self._web = {key: self._line(form, label) for key, label in WEB_FIELDS}
        layout.addWidget(web)

        self._plates = {}
        self._plate_groups = {}
        for key, title in (("top", "Placa de ala superior (o ambas, apernadas)"),
                           ("bottom", "Placa de ala inferior")):
            group = QGroupBox(title)
            group.setCheckable(key == "bottom")
            form = QFormLayout(group)
            fields = {name: self._line(form, label) for name, label in PLATE_FIELDS}
            fields["transverse_weld"] = QCheckBox("Soldadura transversal en el extremo")
            form.addRow(fields["transverse_weld"])
            self._plates[key] = fields
            self._plate_groups[key] = group
            layout.addWidget(group)

        self.end_plate_group = QGroupBox("Placa de extremo (AISC DG16)")
        form = QFormLayout(self.end_plate_group)
        self.ep_layout = QComboBox()
        for layout_ in EndPlateLayout:
            self.ep_layout.addItem(tr(f"moment.layout.{layout_.value}", "es"), layout_.value)
        form.addRow("Configuración", self.ep_layout)
        self.ep_bolt = self._line(form, "Diámetro de perno")
        self.ep_bolt_grade = self._line(form, "Material de los pernos")
        self._ep = {key: self._line(form, label) for key, label in END_PLATE_FIELDS}
        self.ep_snug = QCheckBox("Pernos con apriete ajustado (solo A325)")
        form.addRow(self.ep_snug)
        self.ep_symmetric = QCheckBox("Mismos pernos en ambas alas (momento reversible)")
        form.addRow(self.ep_symmetric)
        layout.addWidget(self.end_plate_group)

        self.seismic_group = QGroupBox("Opción sísmica precalificada (AISC 358-22)")
        self.seismic_group.setCheckable(True)
        self.seismic_group.setChecked(False)
        form = QFormLayout(self.seismic_group)
        self.seismic_connection = QComboBox()
        for item in Prequalified:
            self.seismic_connection.addItem(tr(f"seismic.connection.{item.value}", "es"),
                                            item.value)
        form.addRow("Conexión", self.seismic_connection)
        self.seismic_system = QComboBox()
        for item in SeismicSystem:
            self.seismic_system.addItem(tr(f"seismic.system.{item.value}", "es"), item.value)
        form.addRow("Sistema", self.seismic_system)
        self.seismic_column_above = QCheckBox("La columna continúa sobre el nudo")
        self.seismic_column_above.setChecked(True)
        form.addRow(self.seismic_column_above)
        self.seismic_slab = QCheckBox("Losa estructural de concreto (BFP: columna hasta W36)")
        self.seismic_slab.setChecked(True)
        form.addRow(self.seismic_slab)
        self._seismic = {key: self._line(form, label) for key, label in SEISMIC_FIELDS}
        layout.addWidget(self.seismic_group)

        self.bolts_group = QGroupBox("Pernos de ala")
        form = QFormLayout(self.bolts_group)
        self.flange_bolt = self._line(form, "Diámetro de perno")
        self.flange_rows = QSpinBox()
        self.flange_rows.setRange(1, 20)
        form.addRow("Pernos por línea", self.flange_rows)
        self._flange = {key: self._line(form, label) for key, label in FLANGE_BOLT_FIELDS}
        layout.addWidget(self.bolts_group)

        layout.addWidget(self._build_cases_group(
            "Casos de carga (V, M y P en el extremo de la viga; P solo en placas de extremo, "
            "compresión positiva)", ["Nombre", "Tipo", "V", "M", "P", "V_c", "P_c"],
            lambda: self._add_case("", "D", "", "", "", "", "")))
        self._end_form(layout)
        self._build_results(form_widget)

    def _add_case(self, name: str, kind: str, V: str, M: str, P: str = "", Vc: str = "",
                  Pc: str = "") -> None:
        row = self.cases.rowCount()
        self.cases.insertRow(row)
        self.cases.setItem(row, 0, QTableWidgetItem(name))
        combo = QComboBox()
        combo.addItems([t.value for t in LoadType])
        combo.setCurrentText(kind)
        combo.currentIndexChanged.connect(self._mark_modified)
        self.cases.setCellWidget(row, 1, combo)
        self.cases.setItem(row, 2, QTableWidgetItem(V))
        self.cases.setItem(row, 3, QTableWidgetItem(M))
        self.cases.setItem(row, 4, QTableWidgetItem(P))
        self.cases.setItem(row, 5, QTableWidgetItem(Vc))
        self.cases.setItem(row, 6, QTableWidgetItem(Pc))

    # -- form <-> project ----------------------------------------------------------------
    def _unit_fields(self):
        """Every quantity field of the form with its magnitude."""
        L, T, F = Kind.LENGTH, Kind.THICKNESS, Kind.FORCE
        thick = {"thickness", "weld", "weld_to_column", "weld_to_beam", "stiffener_thickness",
                 "web_weld", "flange_weld", "weld_reinforcement", "continuity_plate",
                 "continuity_plate_weld", "continuity_plate_web_weld", "doubler_plate",
                 "doubler_weld"}
        force = {"pretension", "gravity_shear", "column_axial"}
        groups = [self._flange, self._web, self._ep, self._stiff,
                  *self._plates.values()]
        for group in groups:
            for name, edit in group.items():
                if isinstance(edit, QLineEdit):
                    yield edit, T if name in thick else F if name in force else L
        for name, edit in self._seismic.items():
            if name.startswith("R"):
                continue  # Ry, Rt: dimensionless
            kind = (Kind.FORCE_PER_LENGTH if name == "gravity_load" else
                    T if name in thick else F if name in force else L)
            yield edit, kind
        for edit in (self.plate_extension, self.web_bolt, self.ep_bolt, self.flange_bolt):
            yield edit, L
        for row in range(self.cases.rowCount()):
            for col, kind in ((2, F), (3, Kind.MOMENT), (4, F), (5, F), (6, F)):
                yield self.cases.item(row, col), kind

    def _uses_plates(self, detail: FlangeDetail) -> bool:
        """Flange plates, or the connection plates of a flange welded to the column web."""
        if detail is FlangeDetail.WELDED_FLANGE:
            return self.support.currentData() == "web"
        return detail is not FlangeDetail.END_PLATE

    def _update_visible(self) -> None:
        detail = FlangeDetail(self.type.currentData())
        bolted = detail is FlangeDetail.BOLTED_FLANGE_PLATE
        end_plate = detail is FlangeDetail.END_PLATE
        plates = self._uses_plates(detail)
        self.web_group.setVisible(not end_plate)
        self.end_plate_group.setVisible(end_plate)
        self.bolts_group.setVisible(bolted)
        self._plate_groups["top"].setVisible(plates)
        self._plate_groups["bottom"].setVisible(plates)
        if detail is FlangeDetail.WELDED_FLANGE_PLATE or (
                detail is FlangeDetail.WELDED_FLANGE and plates):
            self._plate_groups["bottom"].setChecked(True)

    def _fill(self, project: Project) -> None:
        self._fill_info(project)
        mc = project.moment_connection
        self.type.setCurrentIndex(self.type.findData(mc.type.value))
        self.beam.setCurrentText(mc.beam if isinstance(mc.beam, str) else mc.beam.label())
        self.column.setCurrentText(mc.column if isinstance(mc.column, str)
                                   else mc.column.label())
        self.grade.setText(mc.grade)
        self.electrode.setText(mc.electrode)
        self.near_end.setChecked(mc.column_near_end)
        self.two_sided.setChecked(mc.two_sided)
        self.support.setCurrentIndex(self.support.findData(mc.support.value))
        self.plate_extension.setText("" if mc.plate_extension == "3/4 in"
                                     else _text(mc.plate_extension))
        for key, edit in self._stiff.items():
            value = getattr(mc, key)
            default = MomentConnectionInput.model_fields[key].default
            edit.setText("" if value is None or value == default else _text(value))
        self.full_depth.setChecked(mc.continuity_plate_full_depth)
        self.panel_zone.setChecked(mc.panel_zone)
        self.panel_inelastic.setChecked(mc.panel_zone_inelastic)
        web = mc.web or Project.model_validate(TEMPLATE).moment_connection.web
        self.web_bolt.setText(_text(web.bolt.diameter))
        self.web_rows.setValue(web.rows)
        for key, edit in self._web.items():
            edit.setText(_text(getattr(web, key)))
        ep = mc.end_plate
        self.ep_layout.setCurrentIndex(self.ep_layout.findData(
            (ep.layout if ep else EndPlateLayout.EXTENDED_4).value))
        self.ep_bolt.setText(_text(ep.bolt.diameter) if ep else "3/4 in")
        self.ep_bolt_grade.setText(ep.bolt.grade if ep else "ASTM F3125 Gr. A325")
        for key, edit in self._ep.items():
            edit.setText(_text(getattr(ep, key)) if ep else "")
        self.ep_snug.setChecked(bool(ep and ep.snug_tight))
        self.ep_symmetric.setChecked(ep.symmetric if ep else True)
        for key in ("top", "bottom"):
            plate = getattr(mc, key)
            fields = self._plates[key]
            if key == "bottom":
                self._plate_groups[key].setChecked(plate is not None)
            for name, _ in PLATE_FIELDS:
                value = None if plate is None else getattr(plate, name)
                fields[name].setText("" if value in (None, 0, 0.0) else _text(value))
            fields["transverse_weld"].setChecked(bool(plate and plate.transverse_weld))
        sz = mc.seismic
        self.seismic_group.setChecked(sz is not None)
        if sz is not None:
            self.seismic_connection.setCurrentIndex(
                self.seismic_connection.findData(sz.connection.value))
            self.seismic_system.setCurrentIndex(self.seismic_system.findData(sz.system.value))
        self.seismic_column_above.setChecked(sz.column_above if sz else True)
        self.seismic_slab.setChecked(sz.slab if sz else True)
        for key, edit in self._seismic.items():
            edit.setText(_text(getattr(sz, key)) if sz else "")
        self._bolt_extra = {
            key: {k: v for k, v in bolt.model_dump().items() if k in ("threads", "hole")}
            | ({"grade": bolt.grade} if key == "flange" else {})
            for key, bolt in (("flange", mc.bolt), ("end_plate", ep and ep.bolt)) if bolt}
        self.flange_bolt.setText(_text(mc.bolt.diameter) if mc.bolt else "")
        self.flange_rows.setValue(max(mc.rows, 1))
        for key, edit in self._flange.items():
            edit.setText(_text(getattr(mc, key)))
        self.cases.setRowCount(0)
        for case in project.cases:
            self._add_case(case.name, case.type.value,
                           *("" if v in (0, 0.0) else _text(v)
                             for v in (case.V, case.M, case.P, case.column_V,
                                       case.column_P)))
        self._update_visible()
        self._update_title()

    def _section(self, combo: QComboBox, key: str):
        """Catalog label, or the project's generic section when its label is kept."""
        text = combo.currentText().strip()
        current = getattr(self.project.moment_connection, key)
        if not isinstance(current, str) and text == current.label():
            return current.model_dump()
        return text.upper()

    def project_from_form(self) -> Project:
        detail = FlangeDetail(self.type.currentData())
        connection: dict = {
            "type": detail.value, "beam": self._section(self.beam, "beam"),
            "column": self._section(self.column, "column"),
            "grade": self.grade.text().strip(), "electrode": self.electrode.text().strip(),
            "column_near_end": self.near_end.isChecked(),
            "two_sided": self.two_sided.isChecked(),
            "support": self.support.currentData(),
        }
        if self.plate_extension.text().strip():
            connection["plate_extension"] = self.plate_extension.text().strip()
        connection.update({k: e.text().strip() for k, e in self._stiff.items()
                           if e.text().strip()})
        connection["continuity_plate_full_depth"] = self.full_depth.isChecked()
        connection["panel_zone"] = self.panel_zone.isChecked()
        connection["panel_zone_inelastic"] = self.panel_inelastic.isChecked()
        if detail is FlangeDetail.END_PLATE:
            plate = {"layout": self.ep_layout.currentData(),
                     "bolt": {**getattr(self, "_bolt_extra", {}).get("end_plate", {}),
                              "diameter": self.ep_bolt.text().strip(),
                              "grade": self.ep_bolt_grade.text().strip()
                              or "ASTM F3125 Gr. A325"},
                     "snug_tight": self.ep_snug.isChecked(),
                     "symmetric": self.ep_symmetric.isChecked()}
            plate.update({k: e.text().strip() for k, e in self._ep.items() if e.text().strip()})
            connection["end_plate"] = plate
        else:
            connection["web"] = {"bolt": {"diameter": self.web_bolt.text().strip()},
                                 "rows": self.web_rows.value(),
                                 **{k: e.text().strip() for k, e in self._web.items()}}
        if self._uses_plates(detail):
            for key in ("top", "bottom"):
                if key == "bottom" and not self._plate_groups[key].isChecked():
                    continue
                fields = self._plates[key]
                plate = {name: fields[name].text().strip() for name, _ in PLATE_FIELDS
                         if fields[name].text().strip()}
                plate["transverse_weld"] = fields["transverse_weld"].isChecked()
                connection[key] = plate
        if self.seismic_group.isChecked():
            seismic: dict = {"connection": self.seismic_connection.currentData(),
                             "system": self.seismic_system.currentData(),
                             "column_above": self.seismic_column_above.isChecked(),
                             "slab": self.seismic_slab.isChecked()}
            for key, edit in self._seismic.items():
                text = edit.text().strip()
                if text:
                    seismic[key] = float(text.replace(",", ".")) if key.startswith("R") \
                        else text
            connection["seismic"] = seismic
        if detail is FlangeDetail.BOLTED_FLANGE_PLATE:
            connection["bolt"] = {**getattr(self, "_bolt_extra", {}).get("flange", {}),
                                  "diameter": self.flange_bolt.text().strip()}
            connection["rows"] = self.flange_rows.value()
            connection.update({k: e.text().strip() for k, e in self._flange.items()})
        cases = []
        for row in range(self.cases.rowCount()):
            name = (self.cases.item(row, 0) or QTableWidgetItem("")).text().strip()
            if not name:
                continue
            case = {"name": name, "type": self.cases.cellWidget(row, 1).currentText()}
            for col, key in ((2, "V"), (3, "M"), (4, "P"), (5, "column_V"), (6, "column_P")):
                text = (self.cases.item(row, col) or QTableWidgetItem("")).text().strip()
                if text:
                    case[key] = text
            cases.append(case)
        return self._validated(self._project_data(moment_connection=connection, cases=cases))
