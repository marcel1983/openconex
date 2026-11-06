# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Advanced base plate form: special blocks and calculation options."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from PySide6.QtCore import QSignalBlocker
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from openconex.connections.base_plate.check import BearingAreaModel, PressureModel
from openconex.core.materials import ELECTRODES, STEELS
from openconex.gui.quantity import convert_text, format_quantity, unit_label
from openconex.help import help_text
from openconex.io.project import (
    EmbeddedBaseInput,
    EmbeddedRebarInput,
    PedestalRebarInput,
    Project,
    ReinforcementInput,
    ShearLugInput,
    WeakBaseInput,
)
from openconex.units import PRESETS, Kind, UnitSystem, parse

__all__ = ["BasePlateAdvancedForm"]


@dataclass
class _Field:
    path: tuple[str | int, ...]
    label: str
    edit: QLineEdit
    unit: QLabel
    kind: Kind
    required: bool = True


def _path(key: str) -> tuple[str | int, ...]:
    return tuple(int(part) if part.isdigit() else part for part in key.split("."))


def _get(obj: object, path: tuple[str | int, ...]) -> object | None:
    for part in path:
        if obj is None:
            return None
        if isinstance(part, int):
            obj = obj[part]  # type: ignore[index]
        elif isinstance(obj, Mapping):
            obj = obj.get(part)
        else:
            obj = getattr(obj, part, None)
    return obj


def _quantity_row(edit: QLineEdit, unit: QLabel) -> QWidget:
    widget = QWidget()
    layout = QHBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(edit, 1)
    layout.addWidget(unit)
    return widget


class BasePlateAdvancedForm(QWidget):
    """Edit the optional blocks and advanced options of a base plate project."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._units: UnitSystem = PRESETS["US"]
        self._fields: dict[str, _Field] = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._build_advanced_group())
        layout.addWidget(self._build_pedestal_group())
        layout.addWidget(self._build_shear_group())
        layout.addWidget(self._build_reinforcement_group())
        layout.addWidget(self._build_weak_group())
        layout.addWidget(self._build_embedded_group())
        self.set_embedded(False)

    # -- construction -----------------------------------------------------------
    def _tip(self, widget: QWidget, key: str) -> None:
        if widget is None:
            return
        normalized = key.replace(".ca2.0", ".ca2").replace(".ca2.1", ".ca2")
        try:
            text = help_text(normalized)
        except KeyError:
            return
        widget.setToolTip(text)
        widget.setStatusTip(text)

    def _add(self, layout: QFormLayout, key: str, label: str, kind: Kind,
             required: bool = True) -> QLineEdit:
        edit = QLineEdit()
        if not required:
            edit.setPlaceholderText("opcional")
        unit = QLabel(unit_label(self._units, kind))
        unit.setMinimumWidth(42)
        row = _quantity_row(edit, unit)
        layout.addRow(label, row)
        self._tip(edit, key)
        self._tip(row, key)
        self._fields[key] = _Field(_path(key), label, edit, unit, kind, required)
        return edit

    def _build_advanced_group(self) -> QGroupBox:
        group = QGroupBox("Opciones de cálculo")
        layout = QFormLayout(group)
        self._pressure = QComboBox()
        self._pressure.addItem("Rectangular (DG1 §4.3)", PressureModel.RECTANGULAR.value)
        self._pressure.addItem("Triangular (DG1 Ap. B.2)",
                               PressureModel.TRIANGULAR.value)
        self._pressure.setToolTip("La distribución triangular solo se aplica al eje fuerte "
                                  "y a combinaciones con compresión.")
        self._tip(self._pressure, "pressure_model")
        layout.addRow("Modelo de presión", self._pressure)

        self._bearing = QComboBox()
        self._bearing.addItem("Placa completa", BearingAreaModel.PLATE.value)
        self._bearing.addItem("Área efectiva (DG1 Ap. B.3)",
                              BearingAreaModel.EFFECTIVE.value)
        self._bearing.setToolTip("El área efectiva solo se define para perfiles I en "
                                 "compresión concéntrica.")
        self._tip(self._bearing, "bearing_area_model")
        layout.addRow("Área de apoyo", self._bearing)

        self._electrode = QComboBox()
        self._electrode.addItems(sorted(ELECTRODES))
        layout.addRow("Electrodo", self._electrode)
        self._tip(self._electrode, "electrode")
        self._add(layout, "rod_bending_lever", "Brazo de flexión de placa",
                  Kind.LENGTH, required=False)
        self._add(layout, "bearing_area", "Área de apoyo del anclaje", Kind.AREA,
                  required=False)
        self._add(layout, "washer_thickness", "Arandela soldada", Kind.THICKNESS,
                  required=False)
        self._add(layout, "flange_weld", "Soldadura de ala", Kind.THICKNESS,
                  required=False)

        self._friction = QLineEdit("0.4")
        self._friction.setToolTip("Coeficiente de fricción placa-concreto (0.4 por defecto).")
        self._tip(self._friction, "friction_mu")
        layout.addRow("Coef. de fricción", self._friction)

        for key, label in (("edges.left", "Borde izquierdo"),
                           ("edges.right", "Borde derecho"),
                           ("edges.bottom", "Borde inferior"),
                           ("edges.top", "Borde superior")):
            self._add(layout, key, label, Kind.LENGTH, required=False)
        note = QLabel("Los bordes se miden desde el anclaje exterior al borde del concreto; "
                      "si se omiten, se deducen del pedestal.")
        note.setWordWrap(True)
        layout.addRow(note)
        self._advanced_group = group
        return group

    def _build_pedestal_group(self) -> QGroupBox:
        group = QGroupBox("Barras del pedestal (opcional)")
        layout = QVBoxLayout(group)
        self._rebar_table = QTableWidget(0, 3)
        self._rebar_table.setHorizontalHeaderLabels(self._rebar_headers())
        self._rebar_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self._rebar_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection)
        self._rebar_table.verticalHeader().setVisible(False)
        self._rebar_table.horizontalHeader().setStretchLastSection(True)
        self._rebar_table.setMaximumHeight(140)
        layout.addWidget(self._rebar_table)
        self._tip(self._rebar_table, "pedestal_rebars")
        buttons = QHBoxLayout()
        add = QPushButton("Añadir barra")
        add.clicked.connect(self._add_rebar)
        remove = QPushButton("Eliminar")
        remove.clicked.connect(self._remove_rebar)
        self._tip(add, "pedestal_rebars")
        self._tip(remove, "pedestal_rebars")
        buttons.addWidget(add)
        buttons.addWidget(remove)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        note = QLabel("Posición en planta respecto del eje de la columna, para el revisor "
                      "de interferencias.")
        note.setWordWrap(True)
        layout.addWidget(note)
        self._pedestal_group = group
        return group

    def _build_shear_group(self) -> QGroupBox:
        group = QGroupBox("Llave de corte")
        group.setCheckable(True)
        layout = QFormLayout(group)
        self._add(layout, "shear_lug.width", "Ancho b_sl", Kind.LENGTH)
        self._add(layout, "shear_lug.embedment", "Empotramiento h_sl", Kind.LENGTH)
        self._add(layout, "shear_lug.thickness", "Espesor", Kind.THICKNESS)
        self._add(layout, "shear_lug.weld", "Soldadura de filete", Kind.THICKNESS)
        self._shear_direction = QComboBox()
        self._shear_direction.addItem("Fuerte (N)", "strong")
        self._shear_direction.addItem("Débil (B)", "weak")
        self._shear_direction.addItem("Cruz (N y B)", "both")
        layout.addRow("Dirección", self._shear_direction)
        self._tip(self._shear_direction, "shear_lug.direction")
        self._shear_grade = QComboBox()
        self._shear_grade.addItems(sorted(STEELS))
        layout.addRow("Acero", self._shear_grade)
        self._tip(self._shear_grade, "shear_lug.grade")
        self._lug_electrode = QComboBox()
        self._lug_electrode.addItems(sorted(ELECTRODES))
        layout.addRow("Electrodo", self._lug_electrode)
        self._tip(self._lug_electrode, "shear_lug.electrode")
        self._add(layout, "shear_lug.ca1", "Borde c_a1", Kind.LENGTH, required=False)
        self._add(layout, "shear_lug.ca2.0", "Borde c_a2 izquierdo", Kind.LENGTH,
                  required=False)
        self._add(layout, "shear_lug.ca2.1", "Borde c_a2 derecho", Kind.LENGTH,
                  required=False)
        self._shear_group = group
        return group

    def _build_reinforcement_group(self) -> QGroupBox:
        group = QGroupBox("Refuerzo de anclaje")
        group.setCheckable(True)
        layout = QFormLayout(group)
        self._bars = QLineEdit()
        self._bars.setPlaceholderText("Por ejemplo 4 #6")
        layout.addRow("Barras", self._bars)
        self._tip(self._bars, "reinforcement.bars")
        self._add(layout, "reinforcement.area", "Área total", Kind.AREA)
        self._add(layout, "reinforcement.fy", "fy", Kind.STRESS)
        self._add(layout, "reinforcement.db", "Diámetro db", Kind.LENGTH)
        self._add(layout, "reinforcement.clear_cover", "Recubrimiento", Kind.LENGTH)
        self._add(layout, "reinforcement.anchor_to_bar", "Anclaje a barra", Kind.LENGTH)
        self._add(layout, "reinforcement.le", "Desarrollo disponible le", Kind.LENGTH)
        self._reinforcement_group = group
        return group

    def _build_weak_group(self) -> QGroupBox:
        group = QGroupBox("Base débil sísmica")
        group.setCheckable(True)
        layout = QFormLayout(group)
        self._add(layout, "weak_base.reduced_diameter", "Diámetro reducido", Kind.LENGTH)
        self._add(layout, "weak_base.stretch_length", "Longitud de estiramiento",
                  Kind.LENGTH)
        self._rt = QLineEdit("1.2")
        self._rt.setToolTip("Relación de sobre-resistencia Rt (DG1 §6.4).")
        self._tip(self._rt, "weak_base.Rt")
        layout.addRow("Rt", self._rt)
        self._weak_group = group
        return group

    def _build_embedded_group(self) -> QGroupBox:
        group = QGroupBox("Base empotrada Tipo I")
        layout = QFormLayout(group)
        self._add(layout, "embedded_base.embedment", "Empotramiento", Kind.LENGTH)
        self._add(layout, "embedded_base.foundation_width", "Ancho del pedestal",
                  Kind.LENGTH)
        self._add(layout, "embedded_base.face_plate_thickness",
                  "Espesor de placa frontal", Kind.THICKNESS)
        self._beta1 = QLineEdit("0.85")
        self._beta1.setToolTip("Factor del bloque de compresión del concreto (0 < β1 ≤ 1).")
        self._tip(self._beta1, "embedded_base.beta1")
        layout.addRow("β1", self._beta1)
        self._add(layout, "embedded_base.base_plate_width", "Ancho de placa embebida",
                  Kind.LENGTH, required=False)
        self._add(layout, "embedded_base.base_plate_thickness",
                  "Espesor de placa embebida", Kind.THICKNESS, required=False)
        self._damage = QCheckBox()
        self._damage.setToolTip("Aplica el factor 0.8 de limitación de daño.")
        self._tip(self._damage, "embedded_base.damage_limit")
        layout.addRow("Límite de daño", self._damage)
        self._layer_top = self._build_layer("Refuerzo horizontal superior", "rebar_top")
        self._layer_bottom = self._build_layer("Refuerzo horizontal inferior",
                                               "rebar_bottom")
        layout.addRow(self._layer_top)
        layout.addRow(self._layer_bottom)
        self._embedded_group = group
        return group

    def _build_layer(self, title: str, name: str) -> QGroupBox:
        group = QGroupBox(title)
        group.setCheckable(True)
        layout = QFormLayout(group)
        self._add(layout, f"embedded_base.{name}.area", "Área", Kind.AREA)
        self._add(layout, f"embedded_base.{name}.fy", "fy", Kind.STRESS)
        self._add(layout, f"embedded_base.{name}.depth", "Profundidad", Kind.LENGTH)
        return group

    # -- state ------------------------------------------------------------------
    def set_units(self, system: UnitSystem) -> None:
        self._units = system
        for field in self._fields.values():
            field.unit.setText(unit_label(system, field.kind))
        self._rebar_table.setHorizontalHeaderLabels(self._rebar_headers())

    def set_materials(self, names: list[str]) -> None:
        """Refresh the shear lug steel combo with the project's steels."""
        current = self._shear_grade.currentText()
        with QSignalBlocker(self._shear_grade):
            self._shear_grade.clear()
            self._shear_grade.addItems(names)
            if current:
                index = self._shear_grade.findText(current)
                if index >= 0:
                    self._shear_grade.setCurrentIndex(index)
                else:
                    self._shear_grade.addItem(current)
                    self._shear_grade.setCurrentIndex(self._shear_grade.count() - 1)

    def set_electrodes(self, names: list[str]) -> None:
        """Refresh the electrode combos with the project's electrodes."""
        for combo in (self._electrode, self._lug_electrode):
            current = combo.currentText()
            with QSignalBlocker(combo):
                combo.clear()
                combo.addItems(names)
                if current:
                    index = combo.findText(current)
                    if index >= 0:
                        combo.setCurrentIndex(index)
                    else:
                        combo.addItem(current)
                        combo.setCurrentIndex(combo.count() - 1)

    def set_embedded(self, embedded: bool) -> None:
        """Show the embedded form or the exposed-base optional blocks."""
        self._embedded_group.setVisible(embedded)
        for group in (self._advanced_group, self._pedestal_group, self._shear_group,
                      self._reinforcement_group, self._weak_group):
            group.setVisible(not embedded)

    # -- load and apply ---------------------------------------------------------
    def load(self, project: Project) -> None:
        bp = project.base_plate
        for field in self._fields.values():
            raw = _get(bp, field.path)
            if raw is None:
                field.edit.clear()
                continue
            try:
                value = project.quantity(raw, field.kind)
                field.edit.setText(format_quantity(value, field.kind, self._units))
            except Exception:
                field.edit.setText(str(raw))

        self._select(self._pressure, bp.pressure_model.value)
        self._select(self._bearing, bp.bearing_area_model.value)
        self._electrode.setCurrentText(bp.electrode)
        self._friction.setText(f"{bp.friction_mu:g}")

        lug = bp.shear_lug
        self._shear_group.setChecked(lug is not None)
        self._select(self._shear_direction, "strong" if lug is None else lug.direction)
        self._lug_electrode.setCurrentText("E70XX" if lug is None else lug.electrode)
        if lug is not None:
            self._shear_grade.setCurrentText(lug.grade)

        reinforcement = bp.reinforcement
        self._reinforcement_group.setChecked(reinforcement is not None)
        self._bars.setText("" if reinforcement is None else reinforcement.bars)

        weak = bp.weak_base
        self._weak_group.setChecked(weak is not None)
        self._rt.setText("1.2" if weak is None else f"{weak.Rt:g}")

        embedded = bp.embedded_base
        self._beta1.setText("0.85" if embedded is None else f"{embedded.beta1:g}")
        self._damage.setChecked(embedded is not None and embedded.damage_limit)
        self._layer_top.setChecked(embedded is not None and embedded.rebar_top is not None)
        self._layer_bottom.setChecked(embedded is not None
                                      and embedded.rebar_bottom is not None)

        self._rebar_table.setRowCount(0)
        for bar in bp.pedestal_rebars:
            row = self._rebar_table.rowCount()
            self._rebar_table.insertRow(row)
            values = (project.quantity(bar.x, Kind.LENGTH),
                      project.quantity(bar.y, Kind.LENGTH),
                      project.quantity(bar.diameter, Kind.LENGTH))
            for col, value in enumerate(values):
                self._rebar_table.setItem(
                    row, col, QTableWidgetItem(format_quantity(value, Kind.LENGTH,
                                                               self._units)))

    @staticmethod
    def _select(combo: QComboBox, value: object) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def apply(self, data: Project, errors: list[str], embedded: bool) -> None:
        bp = data.base_plate
        bp.pressure_model = PressureModel(self._pressure.currentData())
        bp.bearing_area_model = BearingAreaModel(self._bearing.currentData())
        bp.electrode = self._electrode.currentText()
        for key in ("rod_bending_lever", "bearing_area", "washer_thickness",
                    "flange_weld"):
            setattr(bp, key, self._read(key, errors, required=False))
        bp.friction_mu = self._read_float(self._friction, "Coef. de fricción", errors,
                                          0.4, minimum=0.0)
        bp.edges = {
            key: text for key in ("left", "right", "bottom", "top")
            if (text := self._read(f"edges.{key}", errors, required=False)) is not None
        }
        bp.pedestal_rebars = [] if embedded else self._read_rebars(errors)

        bp.shear_lug = None
        bp.reinforcement = None
        bp.weak_base = None
        bp.embedded_base = None
        if embedded:
            bp.connection_type = "embedded"
            start = len(errors)
            embedment = self._read("embedded_base.embedment", errors)
            foundation = self._read("embedded_base.foundation_width", errors)
            face = self._read("embedded_base.face_plate_thickness", errors)
            beta1 = self._read_float(self._beta1, "β1", errors, 0.85, minimum=0.0,
                                     maximum=1.0)
            if beta1 <= 0:
                errors.append("β1 debe ser mayor que cero")
            width = self._read("embedded_base.base_plate_width", errors, required=False)
            thickness = self._read("embedded_base.base_plate_thickness", errors,
                                   required=False)
            if (width is None) != (thickness is None):
                errors.append("La placa embebida necesita ancho y espesor, o ninguno")
            top = self._read_layer(self._layer_top, "embedded_base.rebar_top", errors)
            bottom = self._read_layer(self._layer_bottom, "embedded_base.rebar_bottom",
                                      errors)
            if len(errors) == start:
                bp.embedded_base = EmbeddedBaseInput(
                    embedment=embedment, foundation_width=foundation,
                    face_plate_thickness=face, beta1=beta1,
                    base_plate_width=width, base_plate_thickness=thickness,
                    rebar_top=top, rebar_bottom=bottom,
                    damage_limit=self._damage.isChecked())
            return

        bp.connection_type = "exposed"
        if self._shear_group.isChecked():
            start = len(errors)
            width = self._read("shear_lug.width", errors)
            embedment = self._read("shear_lug.embedment", errors)
            thickness = self._read("shear_lug.thickness", errors)
            weld = self._read("shear_lug.weld", errors)
            ca1 = self._read("shear_lug.ca1", errors, required=False)
            ca2 = [self._read("shear_lug.ca2.0", errors, required=False),
                   self._read("shear_lug.ca2.1", errors, required=False)]
            if len(errors) == start:
                bp.shear_lug = ShearLugInput(
                    width=width, embedment=embedment, thickness=thickness, weld=weld,
                    direction=self._shear_direction.currentData(),
                    grade=self._shear_grade.currentText(),
                    electrode=self._lug_electrode.currentText(), ca1=ca1, ca2=ca2)
        if self._reinforcement_group.isChecked():
            start = len(errors)
            area = self._read("reinforcement.area", errors)
            fy = self._read("reinforcement.fy", errors)
            db = self._read("reinforcement.db", errors)
            cover = self._read("reinforcement.clear_cover", errors)
            anchor_to_bar = self._read("reinforcement.anchor_to_bar", errors)
            le = self._read("reinforcement.le", errors)
            if len(errors) == start:
                bp.reinforcement = ReinforcementInput(
                    bars=self._bars.text().strip(), area=area, fy=fy, db=db,
                    clear_cover=cover, anchor_to_bar=anchor_to_bar, le=le)
        if self._weak_group.isChecked():
            start = len(errors)
            reduced = self._read("weak_base.reduced_diameter", errors)
            stretch = self._read("weak_base.stretch_length", errors)
            Rt = self._read_float(self._rt, "Rt", errors, 1.2, minimum=1.0)
            if len(errors) == start:
                bp.weak_base = WeakBaseInput(
                    reduced_diameter=reduced, stretch_length=stretch, Rt=Rt)

    # -- helpers ----------------------------------------------------------------
    def _read(self, key: str, errors: list[str], required: bool | None = None) -> str | None:
        field = self._fields[key]
        text = field.edit.text().strip()
        needed = field.required if required is None else required
        if not text:
            if needed:
                errors.append(f"{field.label}: falta el valor")
            return None
        try:
            parse(text, field.kind, self._units)
        except Exception as exc:
            errors.append(f"{field.label}: {exc}")
            return None
        return text

    @staticmethod
    def _read_float(edit: QLineEdit, label: str, errors: list[str], default: float,
                    minimum: float | None = None,
                    maximum: float | None = None) -> float:
        text = edit.text().strip()
        if not text:
            return default
        try:
            value = float(text)
        except ValueError:
            errors.append(f"{label}: valor no válido")
            return default
        if minimum is not None and value < minimum:
            errors.append(f"{label}: debe ser mayor o igual que {minimum:g}")
        if maximum is not None and value > maximum:
            errors.append(f"{label}: debe ser menor o igual que {maximum:g}")
        return value

    def _read_layer(self, group: QGroupBox, prefix: str,
                    errors: list[str]) -> EmbeddedRebarInput | None:
        if not group.isChecked():
            return None
        start = len(errors)
        area = self._read(f"{prefix}.area", errors)
        fy = self._read(f"{prefix}.fy", errors)
        depth = self._read(f"{prefix}.depth", errors)
        if len(errors) > start:
            return None
        return EmbeddedRebarInput(area=area, fy=fy, depth=depth)

    def _read_rebars(self, errors: list[str]) -> list[PedestalRebarInput]:
        bars: list[PedestalRebarInput] = []
        for row in range(self._rebar_table.rowCount()):
            values = [self._rebar_table.item(row, col).text().strip()
                      if self._rebar_table.item(row, col) is not None else ""
                      for col in range(3)]
            if not any(values):
                continue
            if not all(values):
                errors.append(f"Barra del pedestal {row + 1}: faltan datos")
                continue
            try:
                _x, _y, diameter = (parse(text, Kind.LENGTH, self._units)
                                    for text in values)
            except Exception as exc:
                errors.append(f"Barra del pedestal {row + 1}: {exc}")
                continue
            if diameter <= 0:
                errors.append(f"Barra del pedestal {row + 1}: diámetro no válido")
                continue
            bars.append(PedestalRebarInput(x=values[0], y=values[1],
                                           diameter=values[2]))
        return bars

    # -- unit conversion --------------------------------------------------------
    def convert(self, old: UnitSystem, new: UnitSystem) -> list[str]:
        errors: list[str] = []
        for field in self._fields.values():
            text = field.edit.text().strip()
            if not text:
                continue
            try:
                field.edit.setText(convert_text(text, field.kind, old, new))
            except Exception:
                errors.append(field.label)
        for row in range(self._rebar_table.rowCount()):
            for col in range(3):
                item = self._rebar_table.item(row, col)
                if item is None or not item.text().strip():
                    continue
                try:
                    item.setText(convert_text(item.text(), Kind.LENGTH, old, new))
                except Exception:
                    errors.append(f"Barra del pedestal {row + 1}")
        return errors

    # -- pedestal table ---------------------------------------------------------
    def _rebar_headers(self) -> list[str]:
        unit = unit_label(self._units, Kind.LENGTH)
        return [f"x ({unit})", f"y ({unit})", f"Diámetro ({unit})"]

    def _add_rebar(self) -> None:
        row = self._rebar_table.rowCount()
        self._rebar_table.insertRow(row)
        default = format_quantity(19.05, Kind.LENGTH, self._units)  # 3/4 in
        for col, value in enumerate(("0", "0", default)):
            self._rebar_table.setItem(row, col, QTableWidgetItem(value))

    def _remove_rebar(self) -> None:
        row = self._rebar_table.currentRow()
        if row >= 0:
            self._rebar_table.removeRow(row)
