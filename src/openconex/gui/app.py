# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Desktop application for base plate projects."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from PySide6.QtCore import QSignalBlocker, Qt, QTimer
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
    QProgressDialog,
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
from openconex.core.loads import Method
from openconex.core.materials import BOLTS, STEELS
from openconex.core.shapes import ShapeDatabaseError, aisc_shapes
from openconex.gui.advanced import BasePlateAdvancedForm
from openconex.gui.batch import BatchDialog, BatchSummaryDialog, calculate_batch
from openconex.gui.exporting import parts_3d, write_3d, write_dxf
from openconex.gui.geometry import GeometryEditor, GeometryValues
from openconex.gui.import_supports import ImportSupportsDialog
from openconex.gui.import_table import TableImportDialog
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
from openconex.gui.units import UnitDialog
from openconex.gui.viewer3d import Viewer3D
from openconex.io.csi import import_supports
from openconex.io.csi_projects import Grouping, LoadSource, base_plate_projects
from openconex.io.project import (
    CustomCombinationInput,
    HSSSectionInput,
    LoadCaseInput,
    MaterialInput,
    Project,
    WSectionInput,
    load_project,
    save_project,
)
from openconex.io.table_import import projects_from_table, read_table
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
        self._method_boxes: dict[Method, QCheckBox] = {}
        self._combination_edits: dict[str, QLineEdit] = {}
        self.advanced: BasePlateAdvancedForm | None = None
        self._unit_actions: dict[str, QAction] = {}
        self._export_actions: list[QAction] = []
        self._build_ui()

    # -- construction -----------------------------------------------------------
    def _build_ui(self) -> None:
        self.setWindowTitle(APP_NAME)
        self.resize(1280, 860)
        self._build_menu()
        self._build_body()
        self._geometry_timer = QTimer(self)
        self._geometry_timer.setSingleShot(True)
        self._geometry_timer.timeout.connect(self.refresh_geometry)
        for key in ("N", "B", "tp", "grout", "f", "rod_spacing", "hef",
                    "pedestal_N", "pedestal_B"):
            if key in self._quantity_fields:
                self._quantity_fields[key][0].textChanged.connect(
                    self._schedule_geometry_refresh)
        self._section_combo.currentTextChanged.connect(self._schedule_geometry_refresh)
        if self.advanced is not None:
            self.advanced._shear_group.toggled.connect(self._schedule_geometry_refresh)
            self.advanced._shear_direction.currentIndexChanged.connect(
                self._schedule_geometry_refresh)
            self.advanced._fields["shear_lug.width"].edit.textChanged.connect(
                self._schedule_geometry_refresh)
        self._connection_combo.currentIndexChanged.connect(self._on_connection_changed)
        self._on_connection_changed()
        self.statusBar().showMessage("Abra un proyecto .ocnx o importe apoyos de "
                                     "SAP2000/ETABS.")

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
        import_action = QAction("Importar SAP2000 / ETABS…", self)
        import_action.triggered.connect(self.import_csi_dialog)
        file_menu.addAction(import_action)
        table_action = QAction("Importar Excel / CSV…", self)
        table_action.triggered.connect(self.import_table_dialog)
        file_menu.addAction(table_action)
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
        units_menu.addSeparator()
        configure = QAction("Configurar por magnitud…", self)
        configure.triggered.connect(self.configure_units)
        units_menu.addAction(configure)
        self._check_unit_action(self._units.name)

        calc_menu = self.menuBar().addMenu("&Cálculo")
        self.calc_action = QAction("Calcular", self)
        self.calc_action.setShortcut("F5")
        self.calc_action.triggered.connect(self.calculate)
        calc_menu.addAction(self.calc_action)
        self.opt_action = QAction("Optimizar N, B y tp", self)
        self.opt_action.triggered.connect(self.optimize)
        calc_menu.addAction(self.opt_action)
        calc_menu.addSeparator()
        batch_action = QAction("Calcular lote…", self)
        batch_action.triggered.connect(self.calculate_batch_dialog)
        calc_menu.addAction(batch_action)

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
        form_layout.addWidget(self._build_connection_group())
        self._plate_group = self._build_plate_group()
        form_layout.addWidget(self._plate_group)
        self.advanced = BasePlateAdvancedForm()
        form_layout.addWidget(self.advanced)
        form_layout.addWidget(self._build_cases_group())
        form_layout.addWidget(self._build_combinations_group())
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
        self.geometry = GeometryEditor(self._read_geometry, self._apply_geometry)
        self.tabs.addTab(self.geometry, "Geometría")
        self.viewer = Viewer3D(self._load_3d_parts)
        self.tabs.addTab(self.viewer, "3D")
        self.tabs.currentChanged.connect(self._on_tab_changed)
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

    def _build_connection_group(self) -> QGroupBox:
        group = QGroupBox("Conexión")
        layout = QFormLayout(group)

        self._connection_combo = QComboBox()
        self._connection_combo.addItem("Placa base expuesta", "exposed")
        self._connection_combo.addItem("Base empotrada Tipo I", "embedded")
        layout.addRow("Tipo", self._connection_combo)

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
        layout.addRow("Acero de la placa",
                      self._material_combo("plate_grade", sorted(STEELS)))
        self._add_quantity(layout, "fc", "f'c", Kind.STRESS)
        return group

    def _build_plate_group(self) -> QGroupBox:
        group = QGroupBox("Placa base expuesta")
        layout = QFormLayout(group)

        self._add_quantity(layout, "N", "Largo N", Kind.LENGTH)
        self._add_quantity(layout, "B", "Ancho B", Kind.LENGTH)
        self._add_quantity(layout, "tp", "Espesor tp", Kind.THICKNESS)
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

    def _build_combinations_group(self) -> QGroupBox:
        group = QGroupBox("Combinaciones")
        layout = QFormLayout(group)
        methods_widget = QWidget()
        methods_layout = QHBoxLayout(methods_widget)
        methods_layout.setContentsMargins(0, 0, 0, 0)
        for method, label in ((Method.LRFD, "LRFD"), (Method.ASD, "ASD")):
            box = QCheckBox(label)
            self._method_boxes[method] = box
            methods_layout.addWidget(box)
        methods_layout.addStretch(1)
        layout.addRow("Métodos", methods_widget)
        self._include_code = QCheckBox("Generar combinaciones ASCE 7-22")
        layout.addRow("", self._include_code)
        for key, label, default in (
                ("live_factor", "Factor de carga viva", "1.0"),
                ("SDS", "SDS (g)", ""),
                ("rho", "ρ", "1.0"),
                ("omega0", "Ω0", "")):
            edit = QLineEdit(default)
            self._combination_edits[key] = edit
            layout.addRow(label, edit)
        note = QLabel("SDS es obligatorio si hay casos sísmicos y se generan "
                      "combinaciones del código.")
        note.setWordWrap(True)
        layout.addRow(note)

        self._custom_table = QTableWidget(0, 7)
        self._custom_table.setHorizontalHeaderLabels(
            ["Nombre", "Método", "Factores", "Sísmica", "Sobre-resist.",
             "Incr. ASD", "Fuente"])
        self._custom_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self._custom_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection)
        self._custom_table.verticalHeader().setVisible(False)
        self._custom_table.horizontalHeader().setStretchLastSection(True)
        self._custom_table.setMaximumHeight(150)
        layout.addRow("Propias", self._custom_table)
        buttons = QHBoxLayout()
        add = QPushButton("Añadir")
        add.clicked.connect(self._add_custom_combination)
        duplicate = QPushButton("Duplicar")
        duplicate.clicked.connect(self._duplicate_custom_combination)
        remove = QPushButton("Eliminar")
        remove.clicked.connect(self._remove_custom_combination)
        buttons.addWidget(add)
        buttons.addWidget(duplicate)
        buttons.addWidget(remove)
        buttons.addStretch(1)
        layout.addRow(buttons)
        factors_note = QLabel("Factores por caso: D=1.2; L=1.6. Los casos deben existir "
                              "en la tabla de casos de carga.")
        factors_note.setWordWrap(True)
        layout.addRow(factors_note)
        return group

    def _build_actions(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        calculate = QPushButton("Calcular")
        calculate.clicked.connect(self.calculate)
        self._optimize_button = QPushButton("Optimizar")
        self._optimize_button.clicked.connect(self.optimize)
        layout.addWidget(calculate)
        layout.addWidget(self._optimize_button)
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
        if self.advanced is not None:
            self.advanced.set_units(self._units)
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

    def set_unit_system(self, selection: str | UnitSystem) -> None:
        """Change the display units and convert the form and the project."""
        if isinstance(selection, str):
            if selection not in PRESETS:
                return
            new = PRESETS[selection]
            label = UNIT_PRESET_LABELS[selection]
        else:
            new = selection
            label = "personalizado"
        if new == self._units:
            self._check_unit_action(selection if isinstance(selection, str) else "")
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
        self.geometry.clear_history()
        self.refresh_geometry()
        self._check_unit_action(selection if isinstance(selection, str) else "")
        if project is not None:
            project.info.units = new.name if new.name in PRESETS else new
            self.report = None
            self._set_export_enabled(False)
        if errors:
            QMessageBox.warning(
                self, "Unidades",
                "No se pudieron convertir estos valores; revíselos:\n" + "\n".join(errors))
        self.statusBar().showMessage(f"Unidades del formulario: {label}")

    def configure_units(self) -> None:
        dialog = UnitDialog(self, self._units)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.set_unit_system(dialog.system())

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
        if self.advanced is not None:
            errors.extend(self.advanced.convert(old, new))
        return errors

    # -- connection type and combinations ---------------------------------------
    def _on_connection_changed(self, *_args: object) -> None:
        embedded = self._connection_combo.currentData() == "embedded"
        self._plate_group.setVisible(not embedded)
        if self.advanced is not None:
            self.advanced.set_embedded(embedded)
        self.opt_action.setEnabled(not embedded)
        self._optimize_button.setEnabled(not embedded)
        if hasattr(self, "statusBar"):
            kind = "base empotrada Tipo I" if embedded else "placa base expuesta"
            self.statusBar().showMessage(f"Conexión: {kind}")

    def _fill_combinations(self, project: Project) -> None:
        options = project.combinations
        for method, box in self._method_boxes.items():
            box.setChecked(method in options.methods)
        self._include_code.setChecked(options.include_code)
        values = {
            "live_factor": f"{options.live_factor:g}",
            "SDS": "" if options.SDS is None else f"{options.SDS:g}",
            "rho": f"{options.rho:g}",
            "omega0": "" if options.omega0 is None else f"{options.omega0:g}",
        }
        for key, text in values.items():
            self._combination_edits[key].setText(text)

    def _apply_combinations(self, data: Project, errors: list[str]) -> None:
        options = data.combinations
        methods = [method for method, box in self._method_boxes.items()
                   if box.isChecked()]
        options.include_code = self._include_code.isChecked()
        if options.include_code and not methods:
            errors.append("Combinaciones: active LRFD o ASD")
        options.methods = methods
        for key, label, minimum in (
                ("live_factor", "Factor de carga viva", 0.0),
                ("rho", "ρ", 0.0),
                ("SDS", "SDS", 0.0),
                ("omega0", "Ω0", 0.0)):
            text = self._combination_edits[key].text().strip()
            if not text:
                if key == "SDS":
                    options.SDS = None
                elif key == "omega0":
                    options.omega0 = None
                continue
            try:
                value = float(text)
            except ValueError:
                errors.append(f"{label}: valor no válido")
                continue
            if value < minimum:
                errors.append(f"{label}: debe ser mayor o igual que {minimum:g}")
                continue
            if key == "SDS":
                options.SDS = value
            elif key == "omega0":
                options.omega0 = value
            else:
                setattr(options, key, value)
        self._apply_custom_combinations(options, errors)

    def _fill_custom_combinations(self, project: Project) -> None:
        self._custom_table.setRowCount(0)
        for custom in project.combinations.custom:
            factors = "; ".join(f"{case}={factor:g}"
                                for case, factor in custom.factors.items())
            self._insert_custom_row(custom.name, custom.method.value, factors,
                                    custom.seismic, custom.overstrength,
                                    custom.allowable_increase, custom.source)

    def _unique_custom_name(self, base: str) -> str:
        names = {self._custom_table.item(row, 0).text().strip()
                 for row in range(self._custom_table.rowCount())
                 if self._custom_table.item(row, 0) is not None}
        if base not in names:
            return base
        number = 2
        while f"{base} {number}" in names:
            number += 1
        return f"{base} {number}"

    def _method_cell(self, method: str) -> QComboBox:
        combo = QComboBox()
        combo.addItem("LRFD", Method.LRFD.value)
        combo.addItem("ASD", Method.ASD.value)
        index = combo.findData(method)
        combo.setCurrentIndex(index if index >= 0 else 0)
        return combo

    @staticmethod
    def _check_cell(checked: bool) -> QTableWidgetItem:
        item = QTableWidgetItem()
        item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled
                      | Qt.ItemFlag.ItemIsSelectable)
        item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        return item

    def _insert_custom_row(self, name: str, method: str, factors: str,
                           seismic: bool, overstrength: bool, allowable: float,
                           source: str) -> None:
        row = self._custom_table.rowCount()
        self._custom_table.insertRow(row)
        self._custom_table.setItem(row, 0, QTableWidgetItem(name))
        self._custom_table.setCellWidget(row, 1, self._method_cell(method))
        self._custom_table.setItem(row, 2, QTableWidgetItem(factors))
        self._custom_table.setItem(row, 3, self._check_cell(seismic))
        self._custom_table.setItem(row, 4, self._check_cell(overstrength))
        self._custom_table.setItem(row, 5, QTableWidgetItem(f"{allowable:g}"))
        self._custom_table.setItem(row, 6, QTableWidgetItem(source))

    def _add_custom_combination(self) -> None:
        self._insert_custom_row(self._unique_custom_name("Nueva"), Method.LRFD.value,
                                "", False, False, 1.0, "")
        self._custom_table.setCurrentCell(self._custom_table.rowCount() - 1, 2)

    def _duplicate_custom_combination(self) -> None:
        row = self._custom_table.currentRow()
        if row < 0:
            return
        name = self._custom_table.item(row, 0).text().strip()
        combo = self._custom_table.cellWidget(row, 1)
        method = combo.currentData() if isinstance(combo, QComboBox) else Method.LRFD.value
        factors = self._custom_table.item(row, 2).text()
        seismic = self._custom_table.item(row, 3).checkState() == Qt.CheckState.Checked
        overstrength = self._custom_table.item(row, 4).checkState() == Qt.CheckState.Checked
        try:
            allowable = float(self._custom_table.item(row, 5).text())
        except (TypeError, ValueError):
            allowable = 1.0
        source = self._custom_table.item(row, 6).text()
        self._insert_custom_row(self._unique_custom_name(f"{name} copia"), method,
                                factors, seismic, overstrength, allowable, source)
        self._custom_table.setCurrentCell(self._custom_table.rowCount() - 1, 2)

    def _remove_custom_combination(self) -> None:
        row = self._custom_table.currentRow()
        if row >= 0:
            self._custom_table.removeRow(row)

    def _apply_custom_combinations(self, options: object, errors: list[str]) -> None:
        case_names = {
            self.cases.item(row, 0).text().strip()
            for row in range(self.cases.rowCount())
            if self.cases.item(row, 0) is not None
            and self.cases.item(row, 0).text().strip()
        }
        custom: list[CustomCombinationInput] = []
        names: set[str] = set()
        for row in range(self._custom_table.rowCount()):
            name = (self._custom_table.item(row, 0).text().strip()
                    if self._custom_table.item(row, 0) is not None else "")
            factors_text = (self._custom_table.item(row, 2).text().strip()
                            if self._custom_table.item(row, 2) is not None else "")
            if not name and not factors_text:
                continue
            row_errors: list[str] = []
            if not name:
                row_errors.append(f"combinación {row + 1}: falta el nombre")
            elif name in names:
                row_errors.append(f"combinación {name!r}: nombre repetido")
            names.add(name)
            combo = self._custom_table.cellWidget(row, 1)
            method = combo.currentData() if isinstance(combo, QComboBox) else "LRFD"
            factors: dict[str, float] = {}
            if not factors_text:
                row_errors.append(f"combinación {name!r}: faltan los factores")
            for part in factors_text.replace("\n", ";").split(";"):
                part = part.strip()
                if not part:
                    continue
                if "=" not in part:
                    row_errors.append(f"combinación {name!r}: use Caso=Factor")
                    continue
                case, _, value = part.partition("=")
                case = case.strip()
                try:
                    factor = float(value.strip())
                except ValueError:
                    row_errors.append(f"combinación {name!r}: factor no válido en {case!r}")
                    continue
                if case not in case_names:
                    row_errors.append(f"combinación {name!r}: caso desconocido {case!r}")
                if case in factors:
                    row_errors.append(f"combinación {name!r}: caso repetido {case!r}")
                factors[case] = factor
            if not any(value != 0 for value in factors.values()):
                row_errors.append(f"combinación {name!r}: todos los factores son cero")
            allowable_text = (self._custom_table.item(row, 5).text().strip()
                              if self._custom_table.item(row, 5) is not None else "1")
            try:
                allowable = float(allowable_text or "1")
            except ValueError:
                allowable = 1.0
                row_errors.append(f"combinación {name!r}: incremento ASD no válido")
            if allowable < 1:
                row_errors.append(f"combinación {name!r}: el incremento ASD debe ser ≥ 1")
            seismic = (self._custom_table.item(row, 3).checkState()
                       == Qt.CheckState.Checked)
            overstrength = (self._custom_table.item(row, 4).checkState()
                            == Qt.CheckState.Checked)
            source = (self._custom_table.item(row, 6).text().strip()
                      if self._custom_table.item(row, 6) is not None else "")
            if row_errors:
                errors.extend(row_errors)
                continue
            custom.append(CustomCombinationInput(
                name=name, method=Method(method), factors=factors,
                seismic=seismic, overstrength=overstrength,
                allowable_increase=allowable, source=source))
        options.custom = custom

    # -- geometry ---------------------------------------------------------------
    def _on_tab_changed(self, index: int) -> None:
        if self.tabs.widget(index) is self.geometry:
            self.refresh_geometry()
        elif self.tabs.widget(index) is self.viewer:
            self.viewer.load_model()

    def _load_3d_parts(self):
        if self.project is None:
            raise ValueError("abra o calcule un proyecto antes de ver el modelo 3D")
        return parts_3d(self.project.model_copy(deep=True))

    def _schedule_geometry_refresh(self, *_args: object) -> None:
        if hasattr(self, "_geometry_timer"):
            self._geometry_timer.start(150)

    def refresh_geometry(self) -> None:
        if getattr(self, "geometry", None) is not None:
            self.geometry.refresh()

    def _read_geometry(self) -> GeometryValues | None:
        if self.project is None:
            return None

        def quantity(key: str, kind: Kind) -> float | None:
            field = self._quantity_fields.get(key)
            if field is None:
                return None
            text = field[0].text().strip()
            if not text:
                return None
            try:
                return parse(text, kind, self._units)
            except Exception:
                return None

        length, thickness = Kind.LENGTH, Kind.THICKNESS
        label = self._section_combo.currentText().strip()
        column_d = column_bf = None
        custom = self._custom_sections.get(label)
        try:
            if custom is not None:
                column_d = parse(str(custom.d), length, self._units)
                width = custom.bf if custom.bf is not None else custom.d
                column_bf = parse(str(width), length, self._units)
            elif label:
                section = aisc_shapes().get(label)
                column_d = section.properties.get("d")
                column_bf = section.properties.get("bf")
        except (ShapeDatabaseError, ValueError):
            column_d = column_bf = None

        rods_text = self._plain_edits["rods_per_side"].text().strip()
        try:
            rods = max(int(rods_text), 1)
        except ValueError:
            rods = 2
        lug_width = None
        lug_direction = "strong"
        if self.advanced is not None and self.advanced._shear_group.isChecked():
            text = self.advanced._fields["shear_lug.width"].edit.text().strip()
            try:
                lug_width = parse(text, length, self._units) if text else None
            except Exception:
                lug_width = None
            lug_direction = self.advanced._shear_direction.currentData() or "strong"
        return GeometryValues(
            N=quantity("N", length), B=quantity("B", length),
            tp=quantity("tp", thickness), grout=quantity("grout", length),
            f=quantity("f", length), rod_spacing=quantity("rod_spacing", length),
            hef=quantity("hef", length), rods_per_side=rods,
            column_d=column_d, column_bf=column_bf, column_label=label,
            pedestal_N=quantity("pedestal_N", length),
            pedestal_B=quantity("pedestal_B", length),
            lug_width=lug_width, lug_direction=lug_direction, units=self._units)

    def _apply_geometry(self, changes: dict[str, float]) -> None:
        for key, value in changes.items():
            field = self._quantity_fields.get(key)
            if field is None:
                continue
            edit, _label, kind = field
            with QSignalBlocker(edit):
                edit.setText(format_quantity(value, kind, self._units))
        if hasattr(self, "_geometry_timer"):
            self._geometry_timer.start(0)

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
        if self.advanced is not None:
            self.advanced.set_materials(steels)

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

    def import_csi_dialog(self) -> None:
        if self.project is None:
            QMessageBox.warning(self, "Sin plantilla", "Abra el proyecto que servirá de "
                                "plantilla antes de importar.")
            return
        name = self.project.info.name or (self.path.name if self.path else "")
        dialog = ImportSupportsDialog(self, name)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.import_from_csi(dialog.file, dialog.output, dialog.group, dialog.loads,
                             dialog.include, dialog.envelopes, dialog.method)

    def import_from_csi(self, file: str, output: str, group: str, loads: str,
                        include: str = "", envelopes: bool = False,
                        method: str = "") -> list[Path]:
        """Create base plate projects from a CSI export, using the open project."""
        template = self._project_from_form()
        if template is None:
            return []
        try:
            data = import_supports(file)
            projects, warnings = base_plate_projects(
                data, template, LoadSource(loads), include or None, envelopes,
                Method(method) if method else None, Grouping(group))
        except Exception as exc:
            QMessageBox.critical(self, "Error al importar", str(exc))
            return []
        if not projects:
            detail = "\n".join(warnings[:20]) if warnings else "No hay apoyos con columna."
            QMessageBox.warning(self, "Sin proyectos", detail)
            return []
        out = Path(output)
        written: list[Path] = []
        try:
            out.mkdir(parents=True, exist_ok=True)
            for key, project in projects.items():
                name = f"{group}-{re.sub(r'[^A-Za-z0-9_.-]', '_', key)}.ocnx"
                path = out / name
                save_project(project, path)
                written.append(path)
        except Exception as exc:
            QMessageBox.critical(self, "Error al guardar", str(exc))
            return written
        message = f"Se crearon {len(written)} proyectos en:\n{out}"
        if warnings:
            extra = "\n".join(warnings[:20])
            if len(warnings) > 20:
                extra += f"\n… y {len(warnings) - 20} advertencias más."
            message += f"\n\nAdvertencias:\n{extra}"
        QMessageBox.information(self, "Importación completada", message)
        self.statusBar().showMessage(f"Importados {len(written)} proyectos en {out}")
        return written

    def import_table_dialog(self) -> None:
        if self.project is None:
            QMessageBox.warning(self, "Sin plantilla", "Abra el proyecto que servirá de "
                                "plantilla antes de importar.")
            return
        default = self._units.name if self._units.name in PRESETS else "US"
        dialog = TableImportDialog(self, default)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.import_table_file(dialog.file, dialog.output, dialog.units)

    def import_table_file(self, file: str, output: str,
                          units_name: str = "US") -> list[Path]:
        """Create base plate projects from a generic Excel/CSV table."""
        template = self._project_from_form()
        if template is None:
            return []
        try:
            rows = read_table(file)
            projects, warnings = projects_from_table(rows, template,
                                                     PRESETS[units_name])
        except Exception as exc:
            QMessageBox.critical(self, "Error al importar", str(exc))
            return []
        if not projects:
            detail = "\n".join(warnings[:20]) if warnings else "La tabla no tiene filas válidas."
            QMessageBox.warning(self, "Sin proyectos", detail)
            return []
        out = Path(output)
        written: list[Path] = []
        try:
            out.mkdir(parents=True, exist_ok=True)
            for key, project in projects.items():
                name = f"support-{re.sub(r'[^A-Za-z0-9_.-]', '_', key)}.ocnx"
                path = out / name
                save_project(project, path)
                written.append(path)
        except Exception as exc:
            QMessageBox.critical(self, "Error al guardar", str(exc))
            return written
        message = f"Se crearon {len(written)} proyectos en:\n{out}"
        if warnings:
            extra = "\n".join(warnings[:20])
            if len(warnings) > 20:
                extra += f"\n… y {len(warnings) - 20} advertencias más."
            message += f"\n\nAdvertencias:\n{extra}"
        QMessageBox.information(self, "Importación completada", message)
        self.statusBar().showMessage(f"Importados {len(written)} proyectos en {out}")
        return written

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

        bp = project.base_plate
        embedded = bp.connection_type == "embedded" or bp.embedded_base is not None
        index = self._connection_combo.findData("embedded" if embedded else "exposed")
        with QSignalBlocker(self._connection_combo):
            self._connection_combo.setCurrentIndex(index if index >= 0 else 0)
        if self.advanced is not None:
            self.advanced.set_units(self._units)
            self.advanced.set_materials(self._steel_names())
            self.advanced.load(project)

        for key, (edit, _label, kind) in self._quantity_fields.items():
            raw = getattr(bp, key, None)
            if raw is None:
                edit.setText("")
                continue
            try:
                edit.setText(format_quantity(project.quantity(raw, kind), kind, self._units))
            except Exception:
                edit.setText(str(raw))
        for key, edit in self._plain_edits.items():
            raw = getattr(bp, key, None)
            edit.setText("" if raw is None else str(raw))
        for key, box in self._plate_boxes.items():
            box.setChecked(bool(getattr(bp, key, False)))
        self._fill_combinations(project)
        self._fill_custom_combinations(project)

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
        self._on_connection_changed()
        self._update_unit_labels()
        self._update_title()
        self.geometry.clear_history()
        self.refresh_geometry()

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

        embedded = self._connection_combo.currentData() == "embedded"
        errors: list[str] = []
        required = {"fc"} if embedded else set(REQUIRED_QUANTITY_FIELDS)
        for key, (edit, label, kind) in self._quantity_fields.items():
            text = edit.text().strip()
            if not text:
                if key in required:
                    errors.append(f"{label}: falta el valor")
                elif embedded:
                    if key in ("N", "B", "tp", "rod_diameter", "f", "pedestal_N",
                               "pedestal_B"):
                        setattr(bp, key, None)
                    elif key in ("rod_spacing", "hef"):
                        setattr(bp, key, 0.0)
                elif key in OPTIONAL_FIELDS:
                    setattr(bp, key, None)
                continue
            try:
                parse(text, kind, self._units)
            except Exception as exc:
                errors.append(f"{label}: {exc}")
            else:
                setattr(bp, key, text)
        if embedded:
            for key in ("N", "B", "tp", "rod_diameter", "f", "pedestal_N",
                        "pedestal_B"):
                setattr(bp, key, None)
            bp.rod_spacing = 0.0
            bp.hef = 0.0
            bp.A2_over_A1 = 1.0
            bp.rods_per_side = 2
        else:
            try:
                a2 = self._plain_edits["A2_over_A1"].text().strip()
                bp.A2_over_A1 = float(a2) if a2 else bp.A2_over_A1
                rods = self._plain_edits["rods_per_side"].text().strip()
                bp.rods_per_side = int(rods) if rods else bp.rods_per_side
                if bp.A2_over_A1 <= 0 or bp.rods_per_side < 1:
                    raise ValueError("A2/A1 y el número de barras deben ser positivos")
            except ValueError as exc:
                errors.append(f"A2/A1 o barras por lado: {exc}")

        bp.plate_grade = self._material_combos["plate_grade"].currentText()
        bp.rod_grade = self._material_combos["rod_grade"].currentText()
        for key, box in self._plate_boxes.items():
            setattr(bp, key, box.isChecked())
        if self.advanced is not None:
            self.advanced.apply(data, errors, embedded)
        self._apply_combinations(data, errors)
        if errors:
            QMessageBox.warning(self, "Datos incompletos", "\n".join(errors))
            return None

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

    def calculate_batch_dialog(self) -> None:
        dialog = BatchDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        paths = dialog.paths()
        progress = QProgressDialog("Preparando el lote…", "Cancelar", 0, len(paths), self)
        progress.setWindowTitle("Cálculo por lotes")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()

        def update(done: int, total: int, result: object) -> None:
            progress.setMaximum(total)
            progress.setValue(done)
            name = getattr(result, "name", "")
            status = getattr(result, "status", "")
            progress.setLabelText(f"{done}/{total}: {name} — {status}")
            QApplication.processEvents()

        try:
            results = calculate_batch(paths, dialog.output, dialog.formats(),
                                      progress=update,
                                      should_cancel=progress.wasCanceled)
        except Exception as exc:
            progress.close()
            QMessageBox.critical(self, "Error en el lote", str(exc))
            return
        progress.close()
        BatchSummaryDialog(self, results).exec()
        errors = sum(result.status == "ERROR" for result in results)
        self.statusBar().showMessage(
            f"Lote terminado: {len(results)} proyectos, {errors} con error.")

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
        write_dxf(self.project, path)

    def _write_3d(self, path: Path, kind: str) -> None:
        write_3d(self.project, path, kind)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv if argv is None else argv
    app = QApplication(args)
    window = MainWindow()
    if len(args) > 1:
        window.open_project(args[1])
    window.show()
    return app.exec()
