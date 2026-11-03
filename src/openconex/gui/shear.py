# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Editor window for beam-end shear connection projects.

Quantities are typed as in the project file: text with its unit (``3 in``,
``25 kip``); a bare number uses the unit system of the project. The fields
shown follow the connection type.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
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
from openconex.gui.viewer3d import Viewer3D
from openconex.i18n import tr
from openconex.io.project import Project, load_project, save_project
from openconex.io.shear_project import REQUIRED
from openconex.report.builder import Report
from openconex.report.docx import write_docx
from openconex.report.html import write_html
from openconex.report.pdf import write_pdf
from openconex.report.shear import build_shear_report
from openconex.units import PRESETS

__all__ = ["TYPE_FIELDS", "ShearWindow"]

# Quantity fields of ``ShearConnectionInput`` with their label; integers apart.
QUANTITIES = ("spacing", "gage", "length", "thickness", "width", "lev", "leh", "leh_support",
              "a", "beam_leg", "outstanding_leg", "beam_leh", "leg", "vertical_leg",
              "bearing_length", "weld", "support_weld", "beam_weld", "beam_area")
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
}
COPE_FIELDS = ("c", "dc", "dc_bottom", "setback", "lev", "leh")
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
        self.report: Report | None = None
        self._fields: dict[str, QWidget] = {}
        self._rows: dict[str, tuple[QLabel, QWidget]] = {}
        self._cope: dict[str, QLineEdit] = {}
        self._export_actions: list[QAction] = []
        self.setWindowTitle("OpenConex — conexión de corte")
        self.resize(1280, 860)
        self._build_menu()
        self._build_body()
        self._fill(self.project)
        self.statusBar().showMessage("Edite la conexión y pulse Calcular (F5).")

    # -- construction -----------------------------------------------------------
    def _build_menu(self) -> None:
        menu = self.menuBar().addMenu("&Archivo")
        for label, slot, shortcut in (("Nuevo", self.new_project, "Ctrl+N"),
                                      ("Abrir…", self.open_dialog, "Ctrl+O"),
                                      ("Guardar", self.save_dialog, "Ctrl+S"),
                                      ("Guardar como…", lambda: self.save_dialog(True), "")):
            action = QAction(label, self)
            if shortcut:
                action.setShortcut(shortcut)
            action.triggered.connect(slot)
            menu.addAction(action)
        calc = self.menuBar().addMenu("&Cálculo")
        self.calc_action = QAction("Calcular", self)
        self.calc_action.setShortcut("F5")
        self.calc_action.triggered.connect(self.calculate)
        calc.addAction(self.calc_action)
        export = self.menuBar().addMenu("&Exportar")
        for key, label, suffix in (("html", "Memoria HTML…", ".html"),
                                   ("docx", "Memoria Word…", ".docx"),
                                   ("pdf", "Memoria PDF…", ".pdf"),
                                   ("dxf", "Plano DXF…", ".dxf"),
                                   ("step", "Modelo STEP…", ".step"),
                                   ("stl", "Modelo STL…", ".stl")):
            action = QAction(label, self)
            action.setEnabled(False)
            action.triggered.connect(lambda _c=False, k=key, s=suffix: self.export(k, s))
            export.addAction(action)
            self._export_actions.append(action)

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
        self.viewer = Viewer3D(lambda: parts_3d(self.project))
        self.tabs.addTab(self.viewer, "3D")
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
        self.language = QComboBox()
        self.language.addItems(["es", "en"])
        form.addRow("Idioma", self.language)
        self.units = QComboBox()
        self.units.addItems(sorted(PRESETS))
        form.addRow("Unidades", self.units)
        self._methods = {m: QCheckBox(m.value) for m in Method}
        row = QWidget()
        box = QHBoxLayout(row)
        box.setContentsMargins(0, 0, 0, 0)
        for check in self._methods.values():
            box.addWidget(check)
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
        self.beam = self._section_combo()
        form.addRow("Viga", self.beam)
        self.support = self._section_combo()
        form.addRow("Apoyo", self.support)
        self.support_element = QComboBox()
        self.support_element.addItem("Ala", "flange")
        self.support_element.addItem("Alma", "web")
        form.addRow("Unido al", self.support_element)
        self.grade = QLineEdit()
        form.addRow("Material de placa o ángulo", self.grade)
        self.electrode = QLineEdit()
        form.addRow("Electrodo", self.electrode)
        self.bolt_diameter = QLineEdit()
        form.addRow("Diámetro de perno", self.bolt_diameter)
        self.bolt_grade = QLineEdit()
        form.addRow("Grado de perno", self.bolt_grade)
        self.threads = QComboBox()
        for value in Threads:
            self.threads.addItem(value.value, value.value)
        form.addRow("Roscas (N/X)", self.threads)
        self.hole = QComboBox()
        for value in HoleType:
            self.hole.addItem(value.value, value.value)
        form.addRow("Agujero", self.hole)
        self.deformation = QCheckBox("Deformación en el agujero considerada")
        form.addRow(self.deformation)
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
        self._add_row(form, "two_sided", QCheckBox(), "two_sided")
        return group

    def _add_row(self, form: QFormLayout, name: str, widget: QWidget, key: str) -> None:
        label = QLabel(tr(f"input.{key}", "es"))
        form.addRow(label, widget)
        self._fields[name] = widget
        self._rows[name] = (label, widget)

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
        return self.cope_group

    def _build_cases(self) -> QGroupBox:
        group = QGroupBox("Casos de carga (P: tracción negativa)")
        layout = QVBoxLayout(group)
        self.cases = QTableWidget(0, 4)
        self.cases.setHorizontalHeaderLabels(["Nombre", "Tipo", "V", "P"])
        layout.addWidget(self.cases)
        buttons = QHBoxLayout()
        add = QPushButton("Agregar")
        add.clicked.connect(lambda: self._add_case("", "D", "", ""))
        remove = QPushButton("Quitar")
        remove.clicked.connect(lambda: self.cases.removeRow(self.cases.currentRow()))
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

    def _fill(self, project: Project) -> None:
        info = project.info
        for key, edit in self._info.items():
            edit.setText(_text(getattr(info, key)))
        self.language.setCurrentText(info.language)
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
        if self.cope_group.isChecked():
            connection["cope"] = {name: edit.text().strip() for name, edit in self._cope.items()
                                  if edit.text().strip()}
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
