# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Desktop application for base plate projects."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtGui import QAction, QActionGroup, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
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
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from openconex.connections.base_plate.check import optimize_base_plate
from openconex.core.materials import BOLTS, STEELS
from openconex.core.shapes import ShapeDatabaseError, aisc_shapes
from openconex.drawing.base_plate import BasePlateDrawing, write_base_plate_dxf
from openconex.drawing.embedded_base import write_embedded_base_dxf
from openconex.gui.library import (
    SECTION_TYPES,
    MaterialLibraryDialog,
    SectionLibraryDialog,
)
from openconex.gui.quantity import (
    convert_project,
    convert_section,
    convert_text,
    format_quantity,
    unit_label,
)
from openconex.io.project import (
    HSSSectionInput,
    LoadCaseInput,
    MaterialInput,
    Project,
    WSectionInput,
    load_project,
    save_project,
)
from openconex.report.builder import Report, build_base_plate_report
from openconex.report.docx import write_docx
from openconex.report.html import write_html
from openconex.report.pdf import write_pdf
from openconex.units import PRESETS, Kind, UnitSystem, parse

__all__ = ["MainWindow", "main"]

APP_NAME = "OpenConex"
OPTIONAL_FIELDS = ("pedestal_N", "pedestal_B")
REQUIRED_QUANTITY_FIELDS = ("N", "B", "tp", "fc", "grout", "rod_diameter",
                           "f", "rod_spacing", "hef")
QUANTITY_KINDS: dict[str, Kind] = {
    "N": Kind.LENGTH,
    "B": Kind.LENGTH,
    "tp": Kind.THICKNESS,
    "fc": Kind.STRESS,
    "grout": Kind.LENGTH,
    "pedestal_N": Kind.LENGTH,
    "pedestal_B": Kind.LENGTH,
    "rod_diameter": Kind.LENGTH,
    "f": Kind.LENGTH,
    "rod_spacing": Kind.LENGTH,
    "hef": Kind.LENGTH,
}
CASE_FIELDS = (
    ("P", 2, Kind.FORCE),
    ("V", 3, Kind.FORCE),
    ("M", 4, Kind.MOMENT),
    ("V_weak", 5, Kind.FORCE),
    ("M_weak", 6, Kind.MOMENT),
)
UNIT_PRESET_LABELS = {
    "SI_kN_m": "SI (kN, m)",
    "SI_N_mm": "SI (N, mm)",
    "MKS": "MKS (tf, m)",
    "US": "US (kip, in)",
}
SectionInput = WSectionInput | HSSSectionInput


def _quantity_row(edit: QLineEdit, unit: QLabel) -> QWidget:
    widget = QWidget()
    layout = QHBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(edit, 1)
    layout.addWidget(unit)
    return widget


class MainWindow(QMainWindow):
    """Small project editor and report viewer for base plates."""

    def __init__(self) -> None:
        super().__init__()
        self.project: Project | None = None
        self.report: Report | None = None
        self.path: Path | None = None
        self._units: UnitSystem = PRESETS["US"]
        self._info_edits: dict[str, QLineEdit] = {}
        self._quantity_fields: dict[str, tuple[QLineEdit, QLabel, Kind]] = {}
        self._plain_edits: dict[str, QLineEdit] = {}
        self._plate_boxes: dict[str, QCheckBox] = {}
        self._material_combos: dict[str, QComboBox] = {}
        self._custom_sections: dict[str, SectionInput] = {}
        self._section_labels: list[str] | None = None
        self._unit_actions: dict[str, QAction] = {}
        self._export_actions: list[QAction] = []
        self._build_ui()

    # -- construction -----------------------------------------------------------
    def _build_ui(self) -> None:
        self.setWindowTitle(APP_NAME)
        self.resize(1280, 860)
        self._build_menu()
        self._build_body()
        self.statusBar().showMessage("Abra un proyecto .ocnx o cree uno desde la plantilla.")

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&Archivo")
        open_action = QAction("Abrir…", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_project_dialog)
        file_menu.addAction(open_action)
        save_action = QAction("Guardar", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_project_dialog)
        file_menu.addAction(save_action)
        save_as = QAction("Guardar como…", self)
        save_as.triggered.connect(lambda: self.save_project_dialog(save_as=True))
        file_menu.addAction(save_as)
        file_menu.addSeparator()
        exit_action = QAction("Salir", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        library_menu = self.menuBar().addMenu("&Bibliotecas")
        sections_action = QAction("Secciones…", self)
        sections_action.triggered.connect(self.open_section_library)
        library_menu.addAction(sections_action)
        materials_action = QAction("Materiales…", self)
        materials_action.triggered.connect(self.open_material_library)
        library_menu.addAction(materials_action)

        units_menu = self.menuBar().addMenu("&Unidades")
        self._unit_group = QActionGroup(self)
        self._unit_group.setExclusive(True)
        for name in ("SI_kN_m", "SI_N_mm", "MKS", "US"):
            action = QAction(UNIT_PRESET_LABELS[name], self)
            action.setCheckable(True)
            action.triggered.connect(
                lambda _checked=False, preset=name: self.set_unit_system(preset))
            self._unit_group.addAction(action)
            units_menu.addAction(action)
            self._unit_actions[name] = action
        self._check_unit_action(self._units.name)

        calc_menu = self.menuBar().addMenu("&Cálculo")
        self.calc_action = QAction("Calcular", self)
        self.calc_action.setShortcut("F5")
        self.calc_action.triggered.connect(self.calculate)
        calc_menu.addAction(self.calc_action)
        self.opt_action = QAction("Optimizar N, B y tp", self)
        self.opt_action.triggered.connect(self.optimize)
        calc_menu.addAction(self.opt_action)

        export_menu = self.menuBar().addMenu("&Exportar")
        for key, label, suffix in (
                ("html", "Memoria HTML…", ".html"),
                ("docx", "Memoria Word…", ".docx"),
                ("pdf", "Memoria PDF…", ".pdf"),
                ("dxf", "Plano DXF…", ".dxf"),
                ("step", "Modelo STEP…", ".step"),
                ("stl", "Modelo STL…", ".stl")):
            action = QAction(label, self)
            action.triggered.connect(lambda _checked=False, k=key, s=suffix: self.export(k, s))
            action.setEnabled(False)
            export_menu.addAction(action)
            self._export_actions.append(action)

    def _build_body(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        form = QWidget()
        form_layout = QVBoxLayout(form)
        form_layout.addWidget(self._build_info_group())
        form_layout.addWidget(self._build_plate_group())
        form_layout.addWidget(self._build_cases_group())
        form_layout.addWidget(self._build_actions())
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(form)
        splitter.addWidget(scroll)

        self.tabs = QTabWidget()
        self.summary = QTableWidget(0, 6)
        self.summary.setHorizontalHeaderLabels(
            ["Verificación", "Combinación", "Demanda", "Capacidad", "Relación", "Estado"])
        self.summary.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.summary.horizontalHeader().setStretchLastSection(True)
        self.tabs.addTab(self.summary, "Resumen")
        self.details = QTextBrowser()
        self.tabs.addTab(self.details, "Verificaciones")
        self.figure_container = QWidget()
        self.figure_layout = QVBoxLayout(self.figure_container)
        self.figure_layout.addWidget(QLabel("Sin figuras."))
        figure_scroll = QScrollArea()
        figure_scroll.setWidgetResizable(True)
        figure_scroll.setWidget(self.figure_container)
        self.tabs.addTab(figure_scroll, "Figuras")
        splitter.addWidget(self.tabs)
        splitter.setSizes([460, 820])
        self.setCentralWidget(splitter)

    def _build_info_group(self) -> QGroupBox:
        group = QGroupBox("Proyecto")
        layout = QFormLayout(group)
        for key, label in (("name", "Nombre"), ("number", "Número"), ("client", "Cliente"),
                           ("engineer", "Ingeniero"), ("revision", "Revisión"),
                           ("date", "Fecha")):
            edit = QLineEdit()
            self._info_edits[key] = edit
            layout.addRow(label, edit)
        self.language = QComboBox()
        self.language.addItems(["es", "en"])
        layout.addRow("Idioma", self.language)
        return group

    def _material_combo(self, key: str, names: list[str]) -> QComboBox:
        combo = QComboBox()
        combo.addItems(names)
        self._material_combos[key] = combo
        return combo

    def _add_quantity(self, layout: QFormLayout, key: str, label: str,
                      kind: Kind) -> None:
        edit = QLineEdit()
        unit = QLabel(unit_label(self._units, kind))
        unit.setMinimumWidth(42)
        layout.addRow(label, _quantity_row(edit, unit))
        self._quantity_fields[key] = (edit, unit, kind)

    def _build_plate_group(self) -> QGroupBox:
        group = QGroupBox("Placa base")
        layout = QFormLayout(group)

        section_row = QWidget()
        section_layout = QHBoxLayout(section_row)
        section_layout.setContentsMargins(0, 0, 0, 0)
        self._section_combo = QComboBox()
        self._section_combo.setEditable(True)
        self._section_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        completer = self._section_combo.completer()
        if completer is not None:
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
        section_layout.addWidget(self._section_combo, 1)
        self._section_combo.currentTextChanged.connect(self._on_section_changed)
        library = QPushButton("…")
        library.setFixedWidth(30)
        library.setToolTip("Abrir la biblioteca de secciones")
        library.clicked.connect(self.open_section_library)
        section_layout.addWidget(library)
        layout.addRow("Columna", section_row)
        layout.addRow("Grado de columna",
                      self._material_combo("column_grade", sorted(STEELS)))

        self._add_quantity(layout, "N", "Largo N", Kind.LENGTH)
        self._add_quantity(layout, "B", "Ancho B", Kind.LENGTH)
        self._add_quantity(layout, "tp", "Espesor tp", Kind.THICKNESS)
        layout.addRow("Acero de la placa",
                      self._material_combo("plate_grade", sorted(STEELS)))
        self._add_quantity(layout, "fc", "f'c", Kind.STRESS)
        a2 = QLineEdit()
        self._plain_edits["A2_over_A1"] = a2
        layout.addRow("A2/A1", a2)
        self._add_quantity(layout, "pedestal_N", "Pedestal N", Kind.LENGTH)
        self._add_quantity(layout, "pedestal_B", "Pedestal B", Kind.LENGTH)
        self._add_quantity(layout, "grout", "Mortero", Kind.LENGTH)
        self._add_quantity(layout, "rod_diameter", "Diámetro de anclaje", Kind.LENGTH)
        layout.addRow("Grado de anclaje",
                      self._material_combo("rod_grade", sorted(BOLTS)))
        rods = QLineEdit()
        self._plain_edits["rods_per_side"] = rods
        layout.addRow("Barras por lado", rods)
        self._add_quantity(layout, "f", "Distancia f", Kind.LENGTH)
        self._add_quantity(layout, "rod_spacing", "Separación de barras", Kind.LENGTH)
        self._add_quantity(layout, "hef", "Empotramiento hef", Kind.LENGTH)
        for key, label in (("grout_pad", "Con mortero"),
                           ("cracked", "Concreto fisurado"),
                           ("seismic", "Opción sísmica")):
            box = QCheckBox()
            self._plate_boxes[key] = box
            layout.addRow(label, box)
        return group

    def _build_cases_group(self) -> QGroupBox:
        group = QGroupBox("Casos de carga")
        layout = QVBoxLayout(group)
        self.cases = QTableWidget(0, 7)
        self.cases.setHorizontalHeaderLabels(self._case_headers())
        self.cases.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.cases)
        buttons = QHBoxLayout()
        add = QPushButton("Añadir caso")
        add.clicked.connect(self._add_case)
        remove = QPushButton("Eliminar")
        remove.clicked.connect(self._remove_case)
        buttons.addWidget(add)
        buttons.addWidget(remove)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        return group

    def _build_actions(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        calculate = QPushButton("Calcular")
        calculate.clicked.connect(self.calculate)
        optimize = QPushButton("Optimizar")
        optimize.clicked.connect(self.optimize)
        layout.addWidget(calculate)
        layout.addWidget(optimize)
        layout.addStretch(1)
        return widget

    # -- units ------------------------------------------------------------------
    def _case_headers(self) -> list[str]:
        force = unit_label(self._units, Kind.FORCE)
        moment = unit_label(self._units, Kind.MOMENT)
        return ["Nombre", "Tipo", f"P ({force})", f"V ({force})", f"M ({moment})",
                f"V débil ({force})", f"M débil ({moment})"]

    def _update_unit_labels(self) -> None:
        for _key, (_edit, label, kind) in self._quantity_fields.items():
            label.setText(unit_label(self._units, kind))
        self.cases.setHorizontalHeaderLabels(self._case_headers())

    def _check_unit_action(self, name: str) -> None:
        action = self._unit_actions.get(name)
        if action is not None:
            action.setChecked(True)
            return
        self._unit_group.setExclusive(False)
        for item in self._unit_actions.values():
            item.setChecked(False)
        self._unit_group.setExclusive(True)

    def set_unit_system(self, name: str) -> None:
        """Change the display units and convert the form and the project."""
        if name not in PRESETS:
            return
        new = PRESETS[name]
        if new == self._units:
            self._check_unit_action(name)
            return
        old = self._units
        project = self.project
        if project is not None:
            try:
                project = convert_project(project, old, new)
            except Exception as exc:
                QMessageBox.critical(self, "No se pudieron cambiar las unidades", str(exc))
                self._check_unit_action(old.name)
                return
        errors = self._convert_form_quantities(old, new)
        self._units = new
        self.project = project
        self._update_unit_labels()
        self._check_unit_action(name)
        if project is not None:
            project.info.units = name
            self.report = None
            self._set_export_enabled(False)
        if errors:
            QMessageBox.warning(
                self, "Unidades",
                "No se pudieron convertir estos valores; revíselos:\n" + "\n".join(errors))
        self.statusBar().showMessage(f"Unidades del formulario: {UNIT_PRESET_LABELS[name]}")

    def _convert_form_quantities(self, old: UnitSystem, new: UnitSystem) -> list[str]:
        errors: list[str] = []
        for key, (edit, _label, kind) in self._quantity_fields.items():
            text = edit.text().strip()
            if not text:
                continue
            try:
                edit.setText(convert_text(text, kind, old, new))
            except Exception:
                errors.append(key)
        for row in range(self.cases.rowCount()):
            for attr, col, kind in CASE_FIELDS:
                item = self.cases.item(row, col)
                if item is None or not item.text().strip():
                    continue
                try:
                    item.setText(convert_text(item.text(), kind, old, new))
                except Exception:
                    errors.append(f"caso {row + 1} ({attr})")
        for label, section in list(self._custom_sections.items()):
            try:
                self._custom_sections[label] = convert_section(section, old, new)
            except Exception:
                errors.append(label)
        return errors

    # -- sections and materials -------------------------------------------------
    def _catalog_labels(self) -> list[str]:
        if self._section_labels is None:
            database = aisc_shapes()
            self._section_labels = [label for kind in SECTION_TYPES
                                    for label in database.labels(kind)]
        return self._section_labels

    def _steel_names(self) -> list[str]:
        names = set(STEELS)
        if self.project is not None:
            names.update(material.name for material in self.project.materials)
        names.update(section.grade for section in self._custom_sections.values())
        return sorted(names)

    @staticmethod
    def _fill_combo(combo: QComboBox, names: list[str], current: str | None) -> None:
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

    def _refresh_material_combos(self,
                                 current: dict[str, str] | None = None) -> None:
        values = current or {key: combo.currentText()
                             for key, combo in self._material_combos.items()}
        steels = self._steel_names()
        if "column_grade" in self._material_combos:
            self._fill_combo(self._material_combos["column_grade"], steels,
                             values.get("column_grade"))
        if "plate_grade" in self._material_combos:
            self._fill_combo(self._material_combos["plate_grade"], steels,
                             values.get("plate_grade"))
        if "rod_grade" in self._material_combos:
            self._fill_combo(self._material_combos["rod_grade"], sorted(BOLTS),
                             values.get("rod_grade"))

    def _refresh_section_combo(self, select: str | None = None) -> None:
        current = select or self._section_combo.currentText()
        labels = list(self._catalog_labels())
        labels.extend(label for label in self._custom_sections if label not in labels)
        with QSignalBlocker(self._section_combo):
            self._section_combo.clear()
            self._section_combo.addItems(labels)
            if current:
                index = self._section_combo.findText(current)
                if index >= 0:
                    self._section_combo.setCurrentIndex(index)
                else:
                    self._section_combo.setEditText(current)

    def _register_custom_section(self, section: SectionInput) -> SectionInput:
        section = section.model_copy(deep=True)
        if not section.name.strip():
            section = section.model_copy(update={"name": section.label()})
        self._custom_sections[section.label()] = section
        return section

    def add_custom_section(self, section: SectionInput) -> str:
        """Add a section to the project library and select it."""
        if self.project is None:
            raise ValueError("abra un proyecto .ocnx antes de crear secciones")
        section = section.model_copy(deep=True)
        name = section.name.strip()
        if not name:
            name = section.label()
            section = section.model_copy(update={"name": name})
        label = section.label()
        if label in self._custom_sections:
            raise ValueError(f"Ya existe una sección {label!r} en el proyecto.")
        try:
            aisc_shapes().get(label)
        except ShapeDatabaseError:
            pass
        else:
            raise ValueError(f"La sección {label!r} ya existe en el catálogo AISC.")
        self._custom_sections[label] = section
        self._refresh_material_combos()
        self._refresh_section_combo(select=label)
        self._on_section_changed(label)
        if self.project is not None:
            self.project.sections = [item.model_copy(deep=True)
                                     for item in self._custom_sections.values()]
        return label

    def add_custom_material(self, material: MaterialInput) -> None:
        """Add a custom steel to the project and to the material combos."""
        if self.project is None:
            raise ValueError("abra un proyecto .ocnx antes de crear materiales")
        name = material.name.strip()
        existing = {*STEELS, *(item.name for item in self.project.materials),
                    *(section.grade for section in self._custom_sections.values())}
        if name in existing:
            raise ValueError(f"Ya existe un material llamado {name!r}.")
        self.project.materials.append(material.model_copy(update={"name": name}))
        self._refresh_material_combos()

    def _on_section_changed(self, label: str) -> None:
        section = self._custom_sections.get(label)
        if section is not None and "column_grade" in self._material_combos:
            self._fill_combo(self._material_combos["column_grade"],
                             self._steel_names(), section.grade)

    def open_section_library(self) -> None:
        callback = self.add_custom_section if self.project is not None else None
        dialog = SectionLibraryDialog(self, self._units, self._custom_sections,
                                      callback, self._steel_names())
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_label:
            self._section_combo.setCurrentText(dialog.selected_label)
            self._on_section_changed(dialog.selected_label)

    def open_material_library(self) -> None:
        materials = [] if self.project is None else self.project.materials
        callback = self.add_custom_material if self.project is not None else None
        dialog = MaterialLibraryDialog(self, self._units, materials, callback)
        dialog.exec()

    # -- project form -----------------------------------------------------------
    def _add_case(self) -> None:
        row = self.cases.rowCount()
        self.cases.insertRow(row)
        for col, value in enumerate(("Nuevo", "D", "0", "0", "0", "0", "0")):
            self.cases.setItem(row, col, QTableWidgetItem(value))

    def _remove_case(self) -> None:
        row = self.cases.currentRow()
        if row >= 0:
            self.cases.removeRow(row)

    def open_project_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Abrir proyecto", "",
                                               "OpenConex (*.ocnx);;Todos (*)")
        if path:
            self.open_project(path)

    def open_project(self, path: str | Path) -> None:
        try:
            project = load_project(path)
        except Exception as exc:
            QMessageBox.critical(self, "Error al abrir", str(exc))
            return
        self.project = project
        self.path = Path(path)
        self._fill_form(project)
        self._clear_report()
        self.statusBar().showMessage(f"Proyecto abierto: {self.path}")

    def _fill_form(self, project: Project) -> None:
        info = project.info
        for key, edit in self._info_edits.items():
            edit.setText(str(getattr(info, key) or ""))
        self.language.setCurrentText(info.language if info.language in ("es", "en") else "es")
        self._units = project.info.unit_system()
        self._check_unit_action(self._units.name)

        self._custom_sections.clear()
        for section in project.sections:
            self._register_custom_section(section)
        column = project.base_plate.column
        if isinstance(column, str):
            column_label = column
            column_grade = project.base_plate.column_grade
        else:
            section = self._register_custom_section(column)
            column_label = section.label()
            column_grade = section.grade
        self._refresh_section_combo(select=column_label)
        self._refresh_material_combos({
            "column_grade": column_grade,
            "plate_grade": project.base_plate.plate_grade,
            "rod_grade": project.base_plate.rod_grade,
        })
        self._section_combo.setCurrentText(column_label)
        self._on_section_changed(column_label)

        for key, (edit, _label, kind) in self._quantity_fields.items():
            raw = getattr(project.base_plate, key, None)
            if raw is None:
                edit.setText("")
                continue
            try:
                edit.setText(format_quantity(project.quantity(raw, kind), kind, self._units))
            except Exception:
                edit.setText(str(raw))
        for key, edit in self._plain_edits.items():
            raw = getattr(project.base_plate, key, None)
            edit.setText("" if raw is None else str(raw))
        for key, box in self._plate_boxes.items():
            box.setChecked(bool(getattr(project.base_plate, key, False)))

        self.cases.setRowCount(0)
        for case in project.cases:
            row = self.cases.rowCount()
            self.cases.insertRow(row)
            values = [case.name, case.type.value]
            for _attr, _col, kind in CASE_FIELDS:
                values.append(format_quantity(project.quantity(getattr(case, _attr), kind),
                                              kind, self._units))
            for col, value in enumerate(values):
                self.cases.setItem(row, col, QTableWidgetItem(str(value)))
        self._update_unit_labels()
        self._update_title()

    def _update_title(self) -> None:
        name = self.project.info.name if self.project else ""
        self.setWindowTitle(f"{APP_NAME} — {name}" if name else APP_NAME)

    def _project_from_form(self) -> Project | None:
        if self.project is None:
            QMessageBox.warning(self, "Sin proyecto", "Abra un proyecto .ocnx primero.")
            return None
        data = self.project.model_copy(deep=True)
        info = data.info
        for key, edit in self._info_edits.items():
            setattr(info, key, edit.text().strip())
        info.language = self.language.currentText()
        info.units = self._units.name if self._units.name in PRESETS else self._units
        bp = data.base_plate

        column_text = self._section_combo.currentText().strip()
        if not column_text:
            QMessageBox.warning(self, "Datos incompletos", "Seleccione una sección de columna.")
            return None
        grade = self._material_combos["column_grade"].currentText()
        custom = self._custom_sections.get(column_text)
        if custom is not None:
            custom = custom.model_copy(update={"grade": grade})
            self._custom_sections[column_text] = custom
            bp.column = custom
        else:
            try:
                bp.column = aisc_shapes().get(column_text).label
            except ShapeDatabaseError:
                QMessageBox.critical(self, "Sección desconocida",
                                     f"No se encontró la sección {column_text!r}.")
                return None
            bp.column_grade = grade

        errors: list[str] = []
        for key, (edit, label, kind) in self._quantity_fields.items():
            text = edit.text().strip()
            if not text:
                if key in OPTIONAL_FIELDS:
                    setattr(bp, key, None)
                elif key in REQUIRED_QUANTITY_FIELDS:
                    errors.append(f"{label}: falta el valor")
                continue
            try:
                parse(text, kind, self._units)
            except Exception as exc:
                errors.append(f"{label}: {exc}")
            else:
                setattr(bp, key, text)
        try:
            a2 = self._plain_edits["A2_over_A1"].text().strip()
            bp.A2_over_A1 = float(a2) if a2 else bp.A2_over_A1
            rods = self._plain_edits["rods_per_side"].text().strip()
            bp.rods_per_side = int(rods) if rods else bp.rods_per_side
            if bp.A2_over_A1 <= 0 or bp.rods_per_side < 1:
                raise ValueError("A2/A1 y el número de barras deben ser positivos")
        except ValueError as exc:
            errors.append(f"A2/A1 o barras por lado: {exc}")
        if errors:
            QMessageBox.warning(self, "Datos incompletos", "\n".join(errors))
            return None

        bp.plate_grade = self._material_combos["plate_grade"].currentText()
        bp.rod_grade = self._material_combos["rod_grade"].currentText()
        for key, box in self._plate_boxes.items():
            setattr(bp, key, box.isChecked())

        cases: list[LoadCaseInput] = []
        for row in range(self.cases.rowCount()):
            values = [self.cases.item(row, col).text().strip() if self.cases.item(row, col)
                      else "" for col in range(7)]
            name = values[0]
            if not name:
                errors.append(f"caso {row + 1}: falta el nombre")
                continue
            quantities = []
            for (attr, col, kind) in CASE_FIELDS:
                text = values[col] or "0"
                try:
                    parse(text, kind, self._units)
                except Exception as exc:
                    errors.append(f"{name} ({attr}): {exc}")
                quantities.append(text)
            cases.append(LoadCaseInput(
                name=name, type=values[1] or "D", P=quantities[0], V=quantities[1],
                M=quantities[2], V_weak=quantities[3], M_weak=quantities[4]))
        if errors:
            QMessageBox.warning(self, "Datos incompletos", "\n".join(errors))
            return None

        data.cases = cases
        data.sections = [section.model_copy(deep=True)
                         for section in self._custom_sections.values()]
        try:
            return Project.model_validate(data.model_dump())
        except Exception as exc:
            QMessageBox.critical(self, "Datos incompletos", str(exc))
            return None

    # -- calculation and report -------------------------------------------------
    def calculate(self) -> None:
        project = self._project_from_form()
        if project is None:
            return
        try:
            report = build_base_plate_report(project)
        except Exception as exc:
            QMessageBox.critical(self, "Error de cálculo", str(exc))
            return
        self.project = project
        self.report = report
        self._show_report(report)
        self._set_export_enabled(True)
        self.statusBar().showMessage("Cálculo correcto." if report.ok else "Hay verificaciones NG.")

    def optimize(self) -> None:
        project = self._project_from_form()
        if project is None:
            return
        try:
            bp = optimize_base_plate(project.base_plate_model(),
                                     project.load_combinations(), project.case_forces())
            project.base_plate.N = format_quantity(bp.N, Kind.LENGTH, self._units)
            project.base_plate.B = format_quantity(bp.B, Kind.LENGTH, self._units)
            project.base_plate.tp = format_quantity(bp.tp, Kind.THICKNESS, self._units)
            self.project = project
            self._fill_form(project)
            self.calculate()
        except Exception as exc:
            QMessageBox.critical(self, "Error al optimizar", str(exc))

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
        self.details.setPlainText("\n".join(lines) or "Sin verificaciones.")
        self._show_figures(report)
        self.tabs.setCurrentIndex(0)

    def _show_figures(self, report: Report) -> None:
        while self.figure_layout.count():
            item = self.figure_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        found = False
        for figure in report.figures:
            if not figure.png:
                continue
            pixmap = QPixmap()
            if not pixmap.loadFromData(figure.png):
                continue
            label = QLabel()
            label.setPixmap(pixmap.scaledToWidth(760, Qt.TransformationMode.SmoothTransformation))
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.figure_layout.addWidget(label)
            caption = QLabel(figure.caption)
            caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.figure_layout.addWidget(caption)
            found = True
        if not found:
            self.figure_layout.addWidget(QLabel("Sin figuras."))
        self.figure_layout.addStretch(1)

    def _clear_report(self) -> None:
        self.report = None
        self.summary.setRowCount(0)
        self.details.clear()
        while self.figure_layout.count():
            item = self.figure_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.figure_layout.addWidget(QLabel("Sin figuras."))
        self._set_export_enabled(False)

    def _set_export_enabled(self, enabled: bool) -> None:
        for action in self._export_actions:
            action.setEnabled(enabled)

    def save_project_dialog(self, save_as: bool = False) -> None:
        if self.project is None:
            QMessageBox.warning(self, "Sin proyecto", "Abra un proyecto .ocnx primero.")
            return
        path = self.path
        if save_as or path is None:
            selected, _ = QFileDialog.getSaveFileName(self, "Guardar proyecto", "",
                                                       "OpenConex (*.ocnx)")
            if not selected:
                return
            path = Path(selected)
            if path.suffix.lower() != ".ocnx":
                path = path.with_suffix(".ocnx")
        self.save_project_to(path)

    def save_project_to(self, path: str | Path) -> None:
        project = self._project_from_form()
        if project is None:
            return
        try:
            save_project(project, path)
        except Exception as exc:
            QMessageBox.critical(self, "Error al guardar", str(exc))
            return
        self.project, self.path = project, Path(path)
        self._update_title()
        self.statusBar().showMessage(f"Proyecto guardado: {path}")

    def export(self, kind: str, suffix: str) -> None:
        if self.report is None or self.project is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exportar", "", f"*{suffix}")
        if not path:
            return
        target = Path(path)
        if target.suffix.lower() != suffix:
            target = target.with_suffix(suffix)
        try:
            if kind == "html":
                write_html(self.report, target)
            elif kind == "docx":
                write_docx(self.report, target)
            elif kind == "pdf":
                write_pdf(self.report, target)
            elif kind == "dxf":
                self._write_dxf(target)
            else:
                self._write_3d(target, kind)
        except Exception as exc:
            QMessageBox.critical(self, "Error al exportar", str(exc))
            return
        self.statusBar().showMessage(f"Exportado: {target}")

    def _write_dxf(self, path: Path) -> None:
        project = self.project
        bp = project.base_plate_model()
        info = project.info
        data = project.base_plate
        options = BasePlateDrawing(
            pedestal_N=(None if data.pedestal_N is None else
                        project.quantity(data.pedestal_N, Kind.LENGTH)),
            pedestal_B=(None if data.pedestal_B is None else
                        project.quantity(data.pedestal_B, Kind.LENGTH)),
            grout=project.quantity(data.grout, Kind.LENGTH),
            title=info.name, number=info.number, revision=info.revision, date=info.date)
        if bp.embedded_base is not None:
            write_embedded_base_dxf(bp, path, info.unit_system(), info.language, options)
        else:
            write_base_plate_dxf(bp, path, info.unit_system(), info.language, options)

    def _write_3d(self, path: Path, kind: str) -> None:
        from openconex.geometry3d.base_plate import (
            base_plate_parts,
            embedded_base_parts,
            write_step,
            write_stl,
        )
        project = self.project
        bp = project.base_plate_model()
        if bp.embedded_base is not None:
            parts = embedded_base_parts(bp)
        else:
            data = project.base_plate
            parts = base_plate_parts(
                bp, project.quantity(data.grout, Kind.LENGTH),
                None if data.pedestal_N is None else project.quantity(data.pedestal_N, Kind.LENGTH),
                None if data.pedestal_B is None else project.quantity(data.pedestal_B, Kind.LENGTH))
        (write_step if kind == "step" else write_stl)(parts, path)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv if argv is None else argv
    app = QApplication(args)
    window = MainWindow()
    if len(args) > 1:
        window.open_project(args[1])
    window.show()
    return app.exec()
