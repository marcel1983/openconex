# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Section and material library dialogs."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from openconex.core.materials import BOLTS, ELECTRODES, STEELS
from openconex.core.model import HSSKind
from openconex.core.shapes import Section, aisc_shapes
from openconex.gui.quantity import format_quantity, stored_quantity, unit_label
from openconex.io.project import HSSSectionInput, MaterialInput, WSectionInput
from openconex.units import Kind, UnitSystem, format_value, parse

__all__ = [
    "MaterialLibraryDialog",
    "NewMaterialDialog",
    "NewSectionDialog",
    "SectionLibraryDialog",
]

SectionInput = WSectionInput | HSSSectionInput

SECTION_TYPES = ("W", "M", "S", "HP")
"""Catalog types accepted by the base plate engine as a column label."""

LENGTH = Kind.LENGTH
THICKNESS = Kind.THICKNESS
STRESS = Kind.STRESS


def _quantity_row(edit: QLineEdit, unit: QLabel) -> QWidget:
    widget = QWidget()
    layout = QHBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(edit, 1)
    layout.addWidget(unit)
    return widget


def _table(headers: list[str]) -> QTableWidget:
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setAlternatingRowColors(True)
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setStretchLastSection(True)
    return table


def _pretty(value: float, kind: Kind, system: UnitSystem) -> str:
    return format_value(value, kind, system, precision=6)


def _custom_dimensions(section: SectionInput, system: UnitSystem) -> str:
    def value(raw: object, kind: Kind) -> str:
        return _pretty(parse(str(raw), kind, system), kind, system)

    if isinstance(section, WSectionInput):
        parts = [value(section.d, LENGTH), value(section.bf, LENGTH),
                 value(section.tf, THICKNESS), value(section.tw, THICKNESS)]
    else:
        parts = ["Ø" + value(section.d, LENGTH)] if section.shape is HSSKind.ROUND else [
            value(section.d, LENGTH)]
        if section.bf is not None:
            parts.append(value(section.bf, LENGTH))
        parts.append(value(section.t, THICKNESS))
    return " × ".join(parts)


class SectionLibraryDialog(QDialog):
    """Browse the AISC shapes database and the project's custom sections."""

    def __init__(self, parent: QWidget | None, system: UnitSystem,
                 custom_sections: Mapping[str, SectionInput],
                 on_created: Callable[[SectionInput], str] | None = None,
                 material_names: list[str] | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Biblioteca de secciones")
        self.resize(880, 580)
        self.selected_label: str | None = None
        self._system = system
        self._custom = custom_sections
        self._on_created = on_created
        self._materials = material_names or sorted(STEELS)
        self._db = aisc_shapes()
        self._cache: dict[str, list[tuple[str, str, str]]] = {}
        self._build_ui()
        self._reload()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        filters = QHBoxLayout()
        filters.addWidget(QLabel("Tipo"))
        self._type = QComboBox()
        self._type.addItems(["Todas", "Personalizadas", *SECTION_TYPES])
        filters.addWidget(self._type)
        filters.addWidget(QLabel("Buscar"))
        self._search = QLineEdit()
        self._search.setPlaceholderText("Etiqueta, por ejemplo W12X96")
        self._search.setClearButtonEnabled(True)
        filters.addWidget(self._search, 1)
        self._count = QLabel()
        filters.addWidget(self._count)
        layout.addLayout(filters)

        self._table = _table(["Etiqueta", "Tipo", "Dimensiones"])
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._table, 1)

        buttons = QHBoxLayout()
        self._new = QPushButton("Nueva sección…")
        self._new.setEnabled(self._on_created is not None)
        buttons.addWidget(self._new)
        buttons.addStretch(1)
        self._use = QPushButton("Usar sección")
        self._use.setEnabled(False)
        buttons.addWidget(self._use)
        close = QPushButton("Cerrar")
        buttons.addWidget(close)
        layout.addLayout(buttons)

        self._type.currentTextChanged.connect(self._reload)
        self._search.textChanged.connect(self._reload)
        self._table.itemSelectionChanged.connect(
            lambda: self._use.setEnabled(self._table.currentRow() >= 0))
        self._table.cellDoubleClicked.connect(lambda *_: self._use_selected())
        self._use.clicked.connect(self._use_selected)
        self._new.clicked.connect(self._new_section)
        close.clicked.connect(self.reject)

    def _db_rows(self, type_name: str) -> list[tuple[str, str, str]]:
        if type_name not in self._cache:
            if type_name == "Todas":
                labels = [label for kind in SECTION_TYPES
                          for label in self._db.labels(kind)]
            else:
                labels = self._db.labels(type_name)
            self._cache[type_name] = [
                (section.label, section.type, self._dimensions(section))
                for section in (self._db.get(label) for label in labels)
            ]
        return self._cache[type_name]

    def _dimensions(self, section: Section) -> str:
        props = section.properties
        lengths = [props.get(key) for key in ("d", "Ht", "OD", "bf", "B")]
        thicknesses = [props.get(key) for key in ("tf", "t", "tdes", "tw")]
        parts = [_pretty(value, LENGTH, self._system) for value in lengths
                 if value is not None]
        parts += [_pretty(value, THICKNESS, self._system) for value in thicknesses
                  if value is not None]
        return " × ".join(parts)

    def _custom_rows(self) -> list[tuple[str, str, str]]:
        return [(label,
                 "W" if isinstance(section, WSectionInput) else "HSS",
                 _custom_dimensions(section, self._system))
                for label, section in self._custom.items()]

    def _reload(self, *_args: object) -> None:
        type_name = self._type.currentText()
        if type_name == "Personalizadas":
            rows = self._custom_rows()
        elif type_name == "Todas":
            rows = [*self._db_rows("Todas"), *self._custom_rows()]
        else:
            rows = self._db_rows(type_name)
        search = self._search.text().strip().casefold()
        if search:
            rows = [row for row in rows
                    if search in row[0].casefold() or search in row[1].casefold()]
        self._table.setRowCount(0)
        self._table.setRowCount(len(rows))
        for row, values in enumerate(rows):
            for col, value in enumerate(values):
                self._table.setItem(row, col, QTableWidgetItem(value))
        self._count.setText(f"{len(rows)} secciones")
        self._use.setEnabled(False)

    def _use_selected(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Sin selección", "Seleccione una sección.")
            return
        self.selected_label = self._table.item(row, 0).text()
        self.accept()

    def _new_section(self) -> None:
        if self._on_created is None:
            return
        dialog = NewSectionDialog(self, self._system, self._materials)
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.section is None:
            return
        try:
            label = self._on_created(dialog.section)
        except ValueError as exc:
            QMessageBox.critical(self, "Sección no válida", str(exc))
            return
        self._cache.clear()
        self._type.setCurrentText("Todas")
        self._reload()
        self._select(label)
        self.selected_label = label

    def _select(self, label: str) -> None:
        for row in range(self._table.rowCount()):
            if self._table.item(row, 0).text() == label:
                self._table.selectRow(row)
                self._table.scrollToItem(self._table.item(row, 0))
                return


class NewSectionDialog(QDialog):
    """Create a generic W or HSS column section."""

    def __init__(self, parent: QWidget | None, system: UnitSystem,
                 material_names: list[str]) -> None:
        super().__init__(parent)
        self.setWindowTitle("Nueva sección")
        self._system = system
        self.section: SectionInput | None = None
        self._fields: dict[str, tuple[QLineEdit, QLabel, Kind]] = {}
        self._rows: dict[str, int] = {}
        self._build_ui(material_names)

    def _build_ui(self, material_names: list[str]) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._form = form
        self._type = QComboBox()
        self._type.addItems(["W", "HSS rectangular", "HSS cuadrada", "HSS redonda"])
        form.addRow("Tipo", self._type)

        self._name = QLineEdit()
        self._name.setPlaceholderText("Por ejemplo BP-COL-1")
        form.addRow("Nombre", self._name)

        for key, label, kind, hint in (
                ("d", "Peralte d", LENGTH, "12"),
                ("bf", "Ancho bf", LENGTH, "8"),
                ("tf", "Ala tf", THICKNESS, "0.5"),
                ("tw", "Alma tw", THICKNESS, "0.3"),
                ("k_des", "k_des (opcional)", LENGTH, "0"),
                ("t", "Espesor t", THICKNESS, "0.5")):
            edit = QLineEdit(hint)
            unit = QLabel(unit_label(self._system, kind))
            self._fields[key] = (edit, unit, kind)
            self._rows[key] = form.rowCount()
            form.addRow(label, _quantity_row(edit, unit))

        self._grade = QComboBox()
        self._grade.addItems(material_names)
        form.addRow("Material", self._grade)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancelar")
        create = QPushButton("Crear")
        create.setDefault(True)
        buttons.addWidget(cancel)
        buttons.addWidget(create)
        layout.addLayout(buttons)

        self._type.currentTextChanged.connect(self._update_rows)
        cancel.clicked.connect(self.reject)
        create.clicked.connect(self._create)
        self._update_rows(self._type.currentText())

    def _update_rows(self, shape: str) -> None:
        hss = shape != "W"
        for key in ("d", "bf", "tf", "tw", "k_des", "t"):
            if key == "d":
                visible = True
            elif key == "t":
                visible = hss
            elif key == "bf":
                visible = shape in {"W", "HSS rectangular"}
            else:
                visible = not hss
            self._form_row_visible(self._rows[key], visible)

    def _form_row_visible(self, row: int, visible: bool) -> None:
        self._form.setRowVisible(row, visible)

    def _read(self, key: str, required: bool = True, allow_zero: bool = False) -> str:
        edit = self._fields[key][0]
        text = edit.text().strip()
        if not text:
            if required:
                raise ValueError(f"falta la dimensión {key}")
            return "0"
        value = parse(text, self._fields[key][2], self._system)
        if value < 0 or (value == 0 and not allow_zero):
            raise ValueError(f"la dimensión {key} debe ser positiva")
        return format_quantity(value, self._fields[key][2], self._system)

    def _create(self) -> None:
        name = self._name.text().strip()
        if not name:
            QMessageBox.warning(self, "Datos incompletos",
                                "Escriba un nombre para la sección.")
            return
        try:
            shape = self._type.currentText()
            d = self._read("d")
            if shape == "W":
                section: SectionInput = WSectionInput(
                    type="W", name=name, d=d, bf=self._read("bf"),
                    tf=self._read("tf"), tw=self._read("tw"),
                    k_des=self._read("k_des", required=False, allow_zero=True),
                    grade=self._grade.currentText())
            else:
                kind = {"HSS rectangular": HSSKind.RECTANGULAR,
                        "HSS cuadrada": HSSKind.SQUARE,
                        "HSS redonda": HSSKind.ROUND}[shape]
                bf = self._read("bf") if kind is HSSKind.RECTANGULAR else None
                section = HSSSectionInput(
                    type="HSS", name=name, shape=kind, d=d, bf=bf,
                    t=self._read("t"), grade=self._grade.currentText())
        except Exception as exc:
            QMessageBox.warning(self, "Datos no válidos", str(exc))
            return
        self.section = section
        self.accept()


class MaterialLibraryDialog(QDialog):
    """Browse the AISC steel, bolt and welding electrode libraries."""

    def __init__(self, parent: QWidget | None, system: UnitSystem,
                 materials: list[MaterialInput],
                 on_created: Callable[[MaterialInput], None] | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Biblioteca de materiales")
        self.resize(760, 500)
        self._system = system
        self._materials = materials
        self._on_created = on_created
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        self._tabs = QTabWidget()
        layout.addWidget(self._tabs, 1)

        steels = QWidget()
        steel_layout = QVBoxLayout(steels)
        unit = unit_label(self._system, STRESS)
        self._steel_table = _table(["Nombre", "Origen", f"Fy ({unit})",
                                    f"Fu ({unit})", f"E ({unit})"])
        steel_layout.addWidget(self._steel_table, 1)
        note = QLabel("Los aceros propios se pueden usar en columnas, placas y "
                      "llaves de corte.")
        note.setWordWrap(True)
        steel_layout.addWidget(note)
        buttons = QHBoxLayout()
        self._new = QPushButton("Nuevo material…")
        self._new.setEnabled(self._on_created is not None)
        buttons.addWidget(self._new)
        buttons.addStretch(1)
        steel_layout.addLayout(buttons)
        self._tabs.addTab(steels, "Columnas y placas")

        bolts = QWidget()
        bolt_layout = QVBoxLayout(bolts)
        self._bolt_table = _table([
            "Nombre", f"Fnt ({unit})", f"Fnv N ({unit})", f"Fnv X ({unit})",
            f"Fu ({unit})", f"Fy ({unit})"])
        bolt_layout.addWidget(self._bolt_table, 1)
        bolt_note = QLabel("Grados de pernos y barras de anclaje de AISC 360-22 "
                           "Tabla J3.2. De momento son de solo lectura.")
        bolt_note.setWordWrap(True)
        bolt_layout.addWidget(bolt_note)
        self._tabs.addTab(bolts, "Pernos y anclajes")

        welds = QWidget()
        weld_layout = QVBoxLayout(welds)
        self._weld_table = _table(["Nombre", f"FEXX ({unit})"])
        weld_layout.addWidget(self._weld_table, 1)
        weld_note = QLabel("Electrodos de soldadura de filete. De momento son de "
                           "solo lectura; se usa E70XX por defecto.")
        weld_note.setWordWrap(True)
        weld_layout.addWidget(weld_note)
        self._tabs.addTab(welds, "Soldadura")

        self._refresh_steels()
        self._refresh_bolts()
        self._refresh_welds()

        footer = QHBoxLayout()
        footer.addStretch(1)
        close = QPushButton("Cerrar")
        footer.addWidget(close)
        layout.addLayout(footer)

        self._new.clicked.connect(self._new_material)
        close.clicked.connect(self.reject)

    def _refresh_steels(self) -> None:
        rows = [(grade.name, "AISC", grade.Fy, grade.Fu, grade.E)
                for grade in STEELS.values()]
        built_in = set(STEELS)
        rows += [(material.name, "Proyecto", *(
            parse(str(material.Fy), STRESS, self._system),
            parse(str(material.Fu), STRESS, self._system),
            parse(str(material.E), STRESS, self._system)))
            for material in self._materials if material.name not in built_in]
        self._steel_table.setRowCount(0)
        self._steel_table.setRowCount(len(rows))
        for row, (name, origin, Fy, Fu, E) in enumerate(rows):
            values = (name, origin, format_quantity(Fy, STRESS, self._system),
                      format_quantity(Fu, STRESS, self._system),
                      format_quantity(E, STRESS, self._system))
            for col, value in enumerate(values):
                self._steel_table.setItem(row, col, QTableWidgetItem(value))

    def _refresh_bolts(self) -> None:
        self._bolt_table.setRowCount(0)
        self._bolt_table.setRowCount(len(BOLTS))
        for row, grade in enumerate(BOLTS.values()):
            values = (grade.name,
                      format_quantity(grade.Fnt, STRESS, self._system),
                      format_quantity(grade.Fnv_N, STRESS, self._system),
                      format_quantity(grade.Fnv_X, STRESS, self._system),
                      format_quantity(grade.Fu, STRESS, self._system),
                      "" if grade.Fy is None else
                      format_quantity(grade.Fy, STRESS, self._system))
            for col, value in enumerate(values):
                self._bolt_table.setItem(row, col, QTableWidgetItem(value))

    def _refresh_welds(self) -> None:
        self._weld_table.setRowCount(0)
        self._weld_table.setRowCount(len(ELECTRODES))
        for row, electrode in enumerate(ELECTRODES.values()):
            values = (electrode.name,
                      format_quantity(electrode.FEXX, STRESS, self._system))
            for col, value in enumerate(values):
                self._weld_table.setItem(row, col, QTableWidgetItem(value))

    def _new_material(self) -> None:
        if self._on_created is None:
            return
        names = [*STEELS, *(material.name for material in self._materials)]
        dialog = NewMaterialDialog(self, self._system, names)
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.material is None:
            return
        try:
            self._on_created(dialog.material)
        except ValueError as exc:
            QMessageBox.critical(self, "Material no válido", str(exc))
            return
        self._refresh_steels()


class NewMaterialDialog(QDialog):
    """Create a custom structural steel for the project."""

    def __init__(self, parent: QWidget | None, system: UnitSystem,
                 existing_names: list[str]) -> None:
        super().__init__(parent)
        self.setWindowTitle("Nuevo material")
        self._system = system
        self._existing = {name.casefold() for name in existing_names}
        self.material: MaterialInput | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        base = STEELS["ASTM A572 Gr. 50"]
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._name = QLineEdit()
        self._name.setPlaceholderText("Por ejemplo Acero del proyecto")
        form.addRow("Nombre", self._name)
        self._fields: dict[str, tuple[QLineEdit, Kind]] = {}
        for key, label, value in (
                ("Fy", "Fy", base.Fy), ("Fu", "Fu", base.Fu), ("E", "E", base.E)):
            edit = QLineEdit(format_quantity(value, STRESS, self._system))
            self._fields[key] = (edit, STRESS)
            form.addRow(label, _quantity_row(edit, QLabel(unit_label(self._system, STRESS))))
        layout.addLayout(form)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancelar")
        create = QPushButton("Crear")
        create.setDefault(True)
        buttons.addWidget(cancel)
        buttons.addWidget(create)
        layout.addLayout(buttons)

        cancel.clicked.connect(self.reject)
        create.clicked.connect(self._create)

    def _create(self) -> None:
        name = self._name.text().strip()
        if not name:
            QMessageBox.warning(self, "Datos incompletos", "Escriba un nombre.")
            return
        if name.casefold() in self._existing:
            QMessageBox.warning(self, "Nombre repetido",
                                f"Ya existe un material llamado {name!r}.")
            return
        try:
            values = {key: parse(edit.text().strip(), kind, self._system)
                      for key, (edit, kind) in self._fields.items()}
            if any(value <= 0 for value in values.values()):
                raise ValueError("Fy, Fu y E deben ser positivos")
            if values["Fu"] < values["Fy"]:
                raise ValueError("Fu debe ser mayor o igual que Fy")
            material = MaterialInput(
                name=name,
                Fy=stored_quantity(self._fields["Fy"][0].text(), STRESS, self._system),
                Fu=stored_quantity(self._fields["Fu"][0].text(), STRESS, self._system),
                E=stored_quantity(self._fields["E"][0].text(), STRESS, self._system))
        except Exception as exc:
            QMessageBox.warning(self, "Datos no válidos", str(exc))
            return
        self.material = material
        self.accept()
