# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Editor window for beam-to-column moment connection projects.

Quantities are typed as in the project file, text with its unit (``3/4 in``,
``252 kip*ft``); a bare number uses the unit system of the project.
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

from openconex.connections.moment.fr_moment import FlangeDetail
from openconex.core.loads import LoadType, Method
from openconex.core.shapes import ShapeDatabaseError, aisc_shapes
from openconex.gui.exporting import parts_3d, write_3d, write_dxf
from openconex.gui.viewer3d import Viewer3D
from openconex.i18n import tr
from openconex.io.project import Project, load_project, save_project
from openconex.report.builder import Report
from openconex.report.docx import write_docx
from openconex.report.html import write_html
from openconex.report.moment import build_moment_report
from openconex.report.pdf import write_pdf
from openconex.units import PRESETS

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
FLANGE_BOLT_FIELDS = (("spacing", "Separación s"), ("gage", "Gramil g"),
                      ("plate_lev", "l_ev de la placa"), ("beam_lev", "l_ev de la viga"))


def _text(value) -> str:
    return "" if value is None else str(value)


class MomentWindow(QMainWindow):
    """Editor, calculation and outputs of one moment connection project."""

    def __init__(self, project: Project | None = None, path: str | Path | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project = project or Project.model_validate(TEMPLATE)
        self.path = None if path is None else Path(path)
        self.report: Report | None = None
        self._export_actions: list[QAction] = []
        self.resize(1280, 860)
        self._build_menu()
        self._build_body()
        self._fill(self.project)
        self.statusBar().showMessage("Edite la conexión y pulse Calcular (F5).")

    # -- construction ------------------------------------------------------------------
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
        action = QAction("Calcular", self)
        action.setShortcut("F5")
        action.triggered.connect(self.calculate)
        calc.addAction(action)
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

    def _line(self, form: QFormLayout, label: str) -> QLineEdit:
        edit = QLineEdit()
        form.addRow(label, edit)
        return edit

    def _section_combo(self) -> QComboBox:
        combo = QComboBox()
        combo.setEditable(True)
        try:
            combo.addItems(aisc_shapes().labels("W"))
        except ShapeDatabaseError:
            pass
        return combo

    def _build_body(self) -> None:
        form_widget = QWidget()
        layout = QVBoxLayout(form_widget)

        info = QGroupBox("Proyecto")
        form = QFormLayout(info)
        self._info = {key: self._line(form, label) for key, label in (
            ("name", "Nombre"), ("number", "Número"), ("client", "Cliente"),
            ("engineer", "Ingeniero"), ("revision", "Revisión"), ("date", "Fecha"))}
        self.language = QComboBox()
        self.language.addItems(["es", "en"])
        form.addRow("Idioma", self.language)
        self.units = QComboBox()
        self.units.addItems(sorted(PRESETS))
        form.addRow("Unidades", self.units)
        row = QWidget()
        box = QHBoxLayout(row)
        box.setContentsMargins(0, 0, 0, 0)
        self._methods = {m: QCheckBox(m.value) for m in Method}
        for check in self._methods.values():
            box.addWidget(check)
        form.addRow("Métodos", row)
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
        form.addRow("Columna (al ala)", self.column)
        self.grade = self._line(form, "Material de las placas")
        self.electrode = self._line(form, "Electrodo")
        self.near_end = QCheckBox("Fuerza de ala cerca del extremo de la columna")
        form.addRow(self.near_end)
        self.two_sided = QCheckBox("Vigas a ambos lados de la columna")
        form.addRow(self.two_sided)
        layout.addWidget(conn)

        web = QGroupBox("Placa del alma")
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

        self.bolts_group = QGroupBox("Pernos de ala")
        form = QFormLayout(self.bolts_group)
        self.flange_bolt = self._line(form, "Diámetro de perno")
        self.flange_rows = QSpinBox()
        self.flange_rows.setRange(1, 20)
        form.addRow("Pernos por línea", self.flange_rows)
        self._flange = {key: self._line(form, label) for key, label in FLANGE_BOLT_FIELDS}
        layout.addWidget(self.bolts_group)

        cases = QGroupBox("Casos de carga (V y M en el extremo de la viga)")
        box = QVBoxLayout(cases)
        self.cases = QTableWidget(0, 4)
        self.cases.setHorizontalHeaderLabels(["Nombre", "Tipo", "V", "M"])
        box.addWidget(self.cases)
        buttons = QHBoxLayout()
        add = QPushButton("Agregar")
        add.clicked.connect(lambda: self._add_case("", "D", "", ""))
        remove = QPushButton("Quitar")
        remove.clicked.connect(lambda: self.cases.removeRow(self.cases.currentRow()))
        buttons.addWidget(add)
        buttons.addWidget(remove)
        box.addLayout(buttons)
        layout.addWidget(cases)
        calculate = QPushButton("Calcular")
        calculate.clicked.connect(self.calculate)
        layout.addWidget(calculate)
        layout.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(form_widget)

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

    def _add_case(self, name: str, kind: str, V: str, M: str) -> None:
        row = self.cases.rowCount()
        self.cases.insertRow(row)
        self.cases.setItem(row, 0, QTableWidgetItem(name))
        combo = QComboBox()
        combo.addItems([t.value for t in LoadType])
        combo.setCurrentText(kind)
        self.cases.setCellWidget(row, 1, combo)
        self.cases.setItem(row, 2, QTableWidgetItem(V))
        self.cases.setItem(row, 3, QTableWidgetItem(M))

    # -- form <-> project ----------------------------------------------------------------
    def _update_visible(self) -> None:
        detail = FlangeDetail(self.type.currentData())
        bolted = detail is FlangeDetail.BOLTED_FLANGE_PLATE
        plates = detail is not FlangeDetail.WELDED_FLANGE
        self.bolts_group.setVisible(bolted)
        self._plate_groups["top"].setVisible(plates)
        self._plate_groups["bottom"].setVisible(plates)
        if detail is FlangeDetail.WELDED_FLANGE_PLATE:
            self._plate_groups["bottom"].setChecked(True)

    def _fill(self, project: Project) -> None:
        info = project.info
        for key, edit in self._info.items():
            edit.setText(_text(getattr(info, key)))
        self.language.setCurrentText(info.language)
        if isinstance(info.units, str):
            self.units.setCurrentText(info.units)
        for method, check in self._methods.items():
            check.setChecked(method in project.combinations.methods)
        mc = project.moment_connection
        self.type.setCurrentIndex(self.type.findData(mc.type.value))
        self.beam.setCurrentText(mc.beam if isinstance(mc.beam, str) else mc.beam.label())
        self.column.setCurrentText(mc.column if isinstance(mc.column, str)
                                   else mc.column.label())
        self.grade.setText(mc.grade)
        self.electrode.setText(mc.electrode)
        self.near_end.setChecked(mc.column_near_end)
        self.two_sided.setChecked(mc.two_sided)
        self.web_bolt.setText(_text(mc.web.bolt.diameter))
        self.web_rows.setValue(mc.web.rows)
        for key, edit in self._web.items():
            edit.setText(_text(getattr(mc.web, key)))
        for key in ("top", "bottom"):
            plate = getattr(mc, key)
            fields = self._plates[key]
            if key == "bottom":
                self._plate_groups[key].setChecked(plate is not None)
            for name, _ in PLATE_FIELDS:
                value = None if plate is None else getattr(plate, name)
                fields[name].setText("" if value in (None, 0, 0.0) else _text(value))
            fields["transverse_weld"].setChecked(bool(plate and plate.transverse_weld))
        self.flange_bolt.setText(_text(mc.bolt.diameter) if mc.bolt else "")
        self.flange_rows.setValue(max(mc.rows, 1))
        for key, edit in self._flange.items():
            edit.setText(_text(getattr(mc, key)))
        self.cases.setRowCount(0)
        for case in project.cases:
            self._add_case(case.name, case.type.value,
                           *("" if v in (0, 0.0) else _text(v) for v in (case.V, case.M)))
        self._update_visible()
        self.setWindowTitle("OpenConex — conexión de momento — "
                            + (self.path.name if self.path else "sin guardar"))

    def project_from_form(self) -> Project:
        detail = FlangeDetail(self.type.currentData())
        connection: dict = {
            "type": detail.value, "beam": self.beam.currentText().strip().upper(),
            "column": self.column.currentText().strip().upper(),
            "grade": self.grade.text().strip(), "electrode": self.electrode.text().strip(),
            "column_near_end": self.near_end.isChecked(),
            "two_sided": self.two_sided.isChecked(),
            "web": {"bolt": {"diameter": self.web_bolt.text().strip()},
                    "rows": self.web_rows.value(),
                    **{k: e.text().strip() for k, e in self._web.items()}},
        }
        if detail is not FlangeDetail.WELDED_FLANGE:
            for key in ("top", "bottom"):
                if key == "bottom" and not self._plate_groups[key].isChecked():
                    continue
                fields = self._plates[key]
                plate = {name: fields[name].text().strip() for name, _ in PLATE_FIELDS
                         if fields[name].text().strip()}
                plate["transverse_weld"] = fields["transverse_weld"].isChecked()
                connection[key] = plate
        if detail is FlangeDetail.BOLTED_FLANGE_PLATE:
            connection["bolt"] = {"diameter": self.flange_bolt.text().strip()}
            connection["rows"] = self.flange_rows.value()
            connection.update({k: e.text().strip() for k, e in self._flange.items()})
        cases = []
        for row in range(self.cases.rowCount()):
            name = (self.cases.item(row, 0) or QTableWidgetItem("")).text().strip()
            if not name:
                continue
            case = {"name": name, "type": self.cases.cellWidget(row, 1).currentText()}
            for col, key in ((2, "V"), (3, "M")):
                text = (self.cases.item(row, col) or QTableWidgetItem("")).text().strip()
                if text:
                    case[key] = text
            cases.append(case)
        info = self.project.info.model_dump()
        info.update({k: e.text().strip() for k, e in self._info.items()})
        info.update(language=self.language.currentText(), units=self.units.currentText())
        combinations = self.project.combinations.model_dump()
        combinations["methods"] = [m.value for m, c in self._methods.items() if c.isChecked()]
        data = {"info": info, "materials": [m.model_dump() for m in self.project.materials],
                "bolts": [b.model_dump() for b in self.project.bolts],
                "electrodes": [e.model_dump() for e in self.project.electrodes],
                "moment_connection": connection, "cases": cases,
                "combinations": combinations}
        try:
            return Project.model_validate(data)
        except Exception as exc:  # pydantic ValidationError and unit errors
            raise ValueError(str(exc)) from exc

    # -- actions -----------------------------------------------------------------------
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
        if project.moment_connection is None:
            QMessageBox.warning(self, "Otro tipo de proyecto",
                                "Ese proyecto no es una conexión de momento.")
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
        self.statusBar().showMessage(f"Proyecto guardado: {path}")
        return True

    def calculate(self) -> bool:
        try:
            self.project = self.project_from_form()
            self.report = build_moment_report(self.project)
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
