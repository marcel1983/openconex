# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Editor window for beam and column splice projects.

Quantities are typed as in the project file, text with its unit (``5/8 in``,
``300 kip*ft``); a bare number uses the unit system of the project.
"""

from __future__ import annotations

import copy
from pathlib import Path

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtGui import QAction, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
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

from openconex.core.loads import LoadType, Method
from openconex.core.shapes import ShapeDatabaseError, aisc_shapes
from openconex.gui.exporting import parts_3d, write_3d, write_dxf
from openconex.gui.quantity import convert_fields
from openconex.gui.session import (
    ProjectSessionMixin,
    add_recent_project,
    populate_recent_menu,
    watch_changes,
)
from openconex.gui.start_data import SPLICE_BEAM as BEAM_TEMPLATE
from openconex.gui.start_data import SPLICE_COLUMN as COLUMN_TEMPLATE
from openconex.gui.viewer3d import Viewer3D
from openconex.help import help_text
from openconex.i18n import tr
from openconex.io.project import Project, load_project, save_project
from openconex.io.splice_project import SpliceType
from openconex.report.builder import Report
from openconex.report.docx import write_docx
from openconex.report.html import write_html
from openconex.report.pdf import write_pdf
from openconex.report.splice import build_splice_report
from openconex.units import PRESETS, Kind

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


class SpliceWindow(ProjectSessionMixin, QMainWindow):
    """Editor, calculation and outputs of one splice project."""

    _session_key = "splice"

    def __init__(self, project: Project | None = None, path: str | Path | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project = project or Project.model_validate(BEAM_TEMPLATE)
        self.path = None if path is None else Path(path)
        self.report: Report | None = None
        self._export_actions: list[QAction] = []
        self.resize(1280, 860)
        self._build_menu()
        self._build_body()
        self._fill(self.project)
        self._init_session(self._form)
        # The 3D tab follows the form: it regenerates shortly after each edit.
        watch_changes(self._form, self.viewer.schedule_update)
        self._set_clean()
        self.statusBar().showMessage("Edite el empalme y pulse Calcular (F5).")

    # -- construction ------------------------------------------------------------------
    def _build_menu(self) -> None:
        menu = self.menuBar().addMenu("&Archivo")
        for label, slot, shortcut in (("Nuevo empalme de viga", self.new_project, "Ctrl+N"),
                                      ("Nuevo empalme de columna",
                                       lambda: self.new_project(SpliceType.COLUMN), ""),
                                      ("Abrir…", self.open_dialog, "Ctrl+O"),
                                      ("Guardar", self.save_dialog, "Ctrl+S"),
                                      ("Guardar como…", lambda: self.save_dialog(True), "")):
            action = QAction(label, self)
            if shortcut:
                action.setShortcut(shortcut)
            action.triggered.connect(lambda _c=False, s=slot: s())
            menu.addAction(action)
            if shortcut == "Ctrl+O":
                recent = menu.addMenu("Abrir reciente")
                recent.setToolTipsVisible(True)
                recent.menuAction().setStatusTip(help_text("menu.file.recent"))
                recent.aboutToShow.connect(
                    lambda r=recent: populate_recent_menu(r, self.open))
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

    def _spin(self, form: QFormLayout, label: str, top: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(1, top)
        form.addRow(label, spin)
        return spin

    def _build_body(self) -> None:
        form_widget = QWidget()
        self._form = form_widget
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
        self._units = PRESETS[self.units.currentText()]
        self.units.currentTextChanged.connect(self._change_units)
        row = QWidget()
        box = QHBoxLayout(row)
        box.setContentsMargins(0, 0, 0, 0)
        self._methods = {m: QCheckBox(m.value) for m in Method}
        for check in self._methods.values():
            box.addWidget(check)
        form.addRow("Métodos", row)
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

        cases = QGroupBox("Casos de carga en el empalme (P de compresión positiva; V débil "
                          "solo en columnas)")
        box = QVBoxLayout(cases)
        self.cases = QTableWidget(0, 2 + len(CASE_COLUMNS))
        self.cases.setHorizontalHeaderLabels(["Nombre", "Tipo",
                                              *(label for _, label in CASE_COLUMNS)])
        box.addWidget(self.cases)
        buttons = QHBoxLayout()
        add = QPushButton("Agregar")
        add.clicked.connect(lambda: self._add_case("", "D", {}))
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
        self.viewer = Viewer3D(parts_3d, snapshot=self.project_from_form)
        self.tabs.addTab(self.viewer, "3D")
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(scroll)
        splitter.addWidget(self.tabs)
        splitter.setSizes([480, 800])
        self.setCentralWidget(splitter)

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

    def _change_units(self, name: str) -> None:
        """Convert every value of the form, so a bare number keeps its magnitude."""
        new = PRESETS.get(name)
        if new is None or new.name == self._units.name:
            return
        try:
            convert_fields(self._unit_fields(), self._units, new)
        except ValueError as exc:
            QMessageBox.warning(self, "Unidades", str(exc))
            with QSignalBlocker(self.units):
                self.units.setCurrentText(
                    self._units.name if self._units.name in PRESETS else name)
            return
        self._units = new
        self.statusBar().showMessage(f"Unidades convertidas a {name}.")

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
        info = project.info
        for key, edit in self._info.items():
            edit.setText(_text(getattr(info, key)))
        self.language.setCurrentText(info.language)
        self._units = info.unit_system()
        if isinstance(info.units, str):
            self.units.setCurrentText(info.units)
        for method, check in self._methods.items():
            check.setChecked(method in project.combinations.methods)
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

    def _update_title(self) -> None:
        name = self.path.name if self.path else "sin guardar"
        self.setWindowTitle(f"OpenConex — empalme — {name}[*]")

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
        info = self.project.info.model_dump()
        info.update({k: e.text().strip() for k, e in self._info.items()})
        info.update(language=self.language.currentText(), units=self.units.currentText())
        combinations = self.project.combinations.model_dump()
        combinations["methods"] = [m.value for m, c in self._methods.items() if c.isChecked()]
        data = {"info": info, "materials": [m.model_dump() for m in self.project.materials],
                "bolts": [b.model_dump() for b in self.project.bolts],
                "electrodes": [e.model_dump() for e in self.project.electrodes],
                "splice": splice, "cases": cases, "combinations": combinations}
        try:
            return Project.model_validate(data)
        except Exception as exc:  # pydantic ValidationError and unit errors
            raise ValueError(str(exc)) from exc

    # -- actions -----------------------------------------------------------------------
    def new_project(self, kind: SpliceType = SpliceType.BEAM) -> None:
        if not self.maybe_save():
            return
        template = BEAM_TEMPLATE if kind is SpliceType.BEAM else COLUMN_TEMPLATE
        self.project = Project.model_validate(copy.deepcopy(template))
        self.path, self.report = None, None
        self._fill(self.project)
        self._set_export_enabled(False)
        self._set_clean()

    def open_dialog(self) -> None:
        path = self._open_file_name()
        if path:
            self.open(path)

    def open(self, path: str | Path) -> bool:
        try:
            project = load_project(path)
        except Exception as exc:
            QMessageBox.critical(self, "Error al abrir", str(exc))
            return False
        if project.splice is None:
            QMessageBox.warning(self, "Otro tipo de proyecto", "Ese proyecto no es un empalme.")
            return False
        if not self.maybe_save():
            return False
        self.project, self.path, self.report = project, Path(path), None
        self._fill(project)
        self._set_export_enabled(False)
        self._set_clean()
        add_recent_project(path)
        return True

    def save_dialog(self, save_as: bool = False) -> bool:
        path = self.path
        if save_as or path is None:
            selected = self._save_file_name()
            if not selected:
                return False
            path = Path(selected).with_suffix(".ocnx")
        return self.save_to(path)

    def _session_save(self) -> bool:
        return self.save_dialog()

    def _open_dropped(self, path: Path) -> None:
        self.open(path)

    def save_to(self, path: str | Path) -> bool:
        try:
            project = self.project_from_form()
            save_project(project, path)
        except Exception as exc:
            QMessageBox.critical(self, "Error al guardar", str(exc))
            return False
        self.project, self.path = project, Path(path)
        self._update_title()
        self._set_clean()
        add_recent_project(path)
        self.statusBar().showMessage(f"Proyecto guardado: {path}")
        return True

    def calculate(self) -> bool:
        try:
            self.project = self.project_from_form()
            self.report = build_splice_report(self.project)
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
            selected = self._export_file_name(suffix)
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
