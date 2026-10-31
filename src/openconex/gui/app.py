# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Desktop application for base plate projects."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
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
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from openconex.connections.base_plate.check import optimize_base_plate
from openconex.drawing.base_plate import BasePlateDrawing, write_base_plate_dxf
from openconex.drawing.embedded_base import write_embedded_base_dxf
from openconex.io.project import LoadCaseInput, Project, load_project, save_project
from openconex.report.builder import Report, build_base_plate_report
from openconex.report.docx import write_docx
from openconex.report.html import write_html
from openconex.report.pdf import write_pdf
from openconex.units import Kind, format_value

__all__ = ["MainWindow", "main"]

APP_NAME = "OpenConex"
OPTIONAL_FIELDS = ("N", "B", "tp", "rod_diameter", "f")


class MainWindow(QMainWindow):
    """Small project editor and report viewer for base plates."""

    def __init__(self) -> None:
        super().__init__()
        self.project: Project | None = None
        self.report: Report | None = None
        self.path: Path | None = None
        self._column_label = ""
        self._info_edits: dict[str, QLineEdit] = {}
        self._plate_edits: dict[str, QLineEdit] = {}
        self._plate_boxes: dict[str, QCheckBox] = {}
        self._export_actions: list[QAction] = []
        self._build_ui()

    def _build_ui(self) -> None:
        self.setWindowTitle(APP_NAME)
        self.resize(1280, 820)
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
        splitter.setSizes([430, 850])
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
        self.units = QComboBox()
        from openconex.units import PRESETS
        self.units.addItems(sorted(PRESETS))
        layout.addRow("Unidades", self.units)
        return group

    def _build_plate_group(self) -> QGroupBox:
        group = QGroupBox("Placa base")
        layout = QFormLayout(group)
        fields = (
            ("column", "Columna"),
            ("N", "Largo N"),
            ("B", "Ancho B"),
            ("tp", "Espesor tp"),
            ("plate_grade", "Acero de la placa"),
            ("fc", "f'c"),
            ("A2_over_A1", "A2/A1"),
            ("grout", "Mortero"),
            ("rod_diameter", "Diámetro de anclaje"),
            ("rod_grade", "Grado de anclaje"),
            ("rods_per_side", "Barras por lado"),
            ("f", "Distancia f"),
            ("rod_spacing", "Separación de barras"),
            ("hef", "Empotramiento hef"),
        )
        for key, label in fields:
            edit = QLineEdit()
            self._plate_edits[key] = edit
            layout.addRow(label, edit)
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
        self.cases.setHorizontalHeaderLabels(
            ["Nombre", "Tipo", "P", "V", "M", "V débil", "M débil"])
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
        self.language.setCurrentText(info.language)
        units = info.units if isinstance(info.units, str) else "US"
        self.units.setCurrentText(units)
        bp = project.base_plate
        self._column_label = (bp.column if isinstance(bp.column, str)
                              else getattr(bp.column, "name", str(bp.column)))
        self._plate_edits["column"].setText(self._column_label)
        for key, edit in self._plate_edits.items():
            if key == "column":
                continue
            value = getattr(bp, key, "")
            edit.setText("" if value is None else str(value))
        for key, box in self._plate_boxes.items():
            box.setChecked(bool(getattr(bp, key, False)))
        self.cases.setRowCount(0)
        for case in project.cases:
            row = self.cases.rowCount()
            self.cases.insertRow(row)
            values = (case.name, case.type.value, case.P, case.V, case.M,
                      case.V_weak, case.M_weak)
            for col, value in enumerate(values):
                self.cases.setItem(row, col, QTableWidgetItem(str(value)))
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
        info.units = self.units.currentText()
        bp = data.base_plate
        column = self._plate_edits["column"].text().strip()
        if column and column != self._column_label:
            bp.column = column
        for key, edit in self._plate_edits.items():
            if key == "column":
                continue
            text = edit.text().strip()
            if key in OPTIONAL_FIELDS and not text:
                setattr(bp, key, None)
            elif text and key == "A2_over_A1":
                bp.A2_over_A1 = float(text)
            elif text and key == "rods_per_side":
                bp.rods_per_side = int(text)
            elif text:
                setattr(bp, key, text)
        for key, box in self._plate_boxes.items():
            setattr(bp, key, box.isChecked())
        cases = []
        for row in range(self.cases.rowCount()):
            values = [self.cases.item(row, col).text().strip() if self.cases.item(row, col)
                      else "" for col in range(7)]
            cases.append(LoadCaseInput(name=values[0], type=values[1] or "D", P=values[2] or 0,
                                       V=values[3] or 0, M=values[4] or 0,
                                       V_weak=values[5] or 0, M_weak=values[6] or 0))
        data.cases = cases
        try:
            return Project.model_validate(data.model_dump())
        except Exception as exc:
            QMessageBox.critical(self, "Datos incompletos", str(exc))
            return None

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
            units = project.info.unit_system()
            project.base_plate.N = format_value(bp.N, Kind.LENGTH, units, precision=4)
            project.base_plate.B = format_value(bp.B, Kind.LENGTH, units, precision=4)
            project.base_plate.tp = format_value(bp.tp, Kind.THICKNESS, units, precision=4)
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
