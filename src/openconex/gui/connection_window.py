# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Common window of the connection families that open in their own window.

:class:`ConnectionWindow` holds everything the shear, moment and splice
windows share: the *Archivo*, *Cálculo* and *Exportar* menus, opening and
saving projects, the calculation, the results tabs (summary, checks,
figures and 3D), the exports and the conversion of the form when the unit
preset changes. A subclass sets :attr:`family_key`, its template and its
names, and builds its form in ``_build_body`` (calling
:meth:`_build_results`); it also implements ``_fill``, ``project_from_form``
and ``_unit_fields``.
"""

from __future__ import annotations

import copy
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, ClassVar

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
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from openconex.core.loads import Method
from openconex.core.shapes import ShapeDatabaseError, aisc_shapes
from openconex.families import family, family_of
from openconex.gui.exporting import parts_3d, write_3d, write_dxf
from openconex.gui.quantity import TextField, convert_fields
from openconex.gui.session import (
    ProjectSessionMixin,
    add_recent_project,
    populate_recent_menu,
    watch_changes,
)
from openconex.gui.viewer3d import Viewer3D
from openconex.help import help_text
from openconex.io.project import Project, load_project, save_project
from openconex.report.builder import Report
from openconex.report.docx import write_docx
from openconex.report.html import write_html
from openconex.report.pdf import write_pdf
from openconex.units import PRESETS, Kind

__all__ = ["CUSTOM_UNITS", "EXPORTS", "ConnectionWindow"]

CUSTOM_UNITS = "(del proyecto)"
"""Entry of the unit combo for a project whose system is not a preset."""

EXPORTS = (("html", "Memoria HTML…", ".html"),
           ("docx", "Memoria Word…", ".docx"),
           ("pdf", "Memoria PDF…", ".pdf"),
           ("dxf", "Plano DXF…", ".dxf"),
           ("step", "Modelo STEP…", ".step"),
           ("stl", "Modelo STL…", ".stl"))

INFO_FIELDS = (("name", "Nombre"), ("number", "Número"), ("client", "Cliente"),
               ("engineer", "Ingeniero"), ("revision", "Revisión"), ("date", "Fecha"))


class ConnectionWindow(ProjectSessionMixin, QMainWindow):
    """Editor, calculation and outputs of one connection project."""

    family_key = ""
    """Project block of the family (see :mod:`openconex.families`)."""
    template: ClassVar[dict[str, Any]] = {}
    """Project data of *Nuevo*."""
    noun = "conexión"
    """Name shown in the window title (``conexión de corte``)."""
    start_message = "Edite la conexión y pulse Calcular (F5)."

    # Built by the subclass in _build_body.
    _form: QWidget
    units: QComboBox

    def __init__(self, project: Project | None = None, path: str | Path | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project = project or self._new_model()
        self.path = None if path is None else Path(path)
        self._units = self.project.info.unit_system()
        self.report: Report | None = None
        self._export_actions: list[QAction] = []
        self._init_state()
        self.setWindowTitle(f"OpenConex — {self.noun}")
        self.resize(1280, 860)
        self._build_menu()
        self._build_body()
        self._fill(self.project)
        self._init_session(self._form)
        # The 3D tab follows the form: it regenerates shortly after each edit.
        watch_changes(self._form, self.viewer.schedule_update)
        self._set_clean()
        self.statusBar().showMessage(self.start_message)

    # -- hooks of the subclass ---------------------------------------------------------
    def _init_state(self) -> None:
        """Create the attributes that ``_build_body`` fills (before the menus)."""

    def _build_body(self) -> None:
        raise NotImplementedError

    def _fill(self, project: Project) -> None:
        raise NotImplementedError

    def project_from_form(self) -> Project:
        raise NotImplementedError

    def _unit_fields(self) -> Iterator[tuple[TextField | None, Kind]]:
        """Every quantity field of the form with its magnitude."""
        raise NotImplementedError

    def _new_actions(self) -> list[tuple[str, Callable[[], object], str, str]]:
        """Entries of *Archivo* that create a project: label, slot, shortcut, help key."""
        return [("Nuevo", self.new_project, "Ctrl+N", "menu.file.new")]

    def _build_extra_menus(self) -> None:
        """Menus after *Exportar* (the shear window adds *Ayuda*)."""

    # -- construction ------------------------------------------------------------------
    def _action(self, label: str, slot: Callable[[], object], shortcut: str = "",
                key: str = "") -> QAction:
        item = QAction(label, self)
        if shortcut:
            item.setShortcut(shortcut)
        if key:
            item.setToolTip(help_text(key))
            item.setStatusTip(help_text(key))
        # ``triggered`` passes ``checked``: keep it away from slots with defaults.
        item.triggered.connect(lambda _checked=False, s=slot: s())
        return item

    def _build_menu(self) -> None:
        menu = self.menuBar().addMenu("&Archivo")
        for label, slot, shortcut, key in self._new_actions():
            menu.addAction(self._action(label, slot, shortcut, key))
        menu.addAction(self._action("Abrir…", self.open_dialog, "Ctrl+O", "menu.file.open"))
        recent = menu.addMenu("Abrir reciente")
        recent.setToolTipsVisible(True)
        recent.menuAction().setStatusTip(help_text("menu.file.recent"))
        recent.aboutToShow.connect(lambda: populate_recent_menu(recent, self.open))
        menu.addAction(self._action("Guardar", self.save_dialog, "Ctrl+S", "menu.file.save"))
        menu.addAction(self._action("Guardar como…", lambda: self.save_dialog(True), "",
                                    "menu.file.save_as"))
        calc = self.menuBar().addMenu("&Cálculo")
        self.calc_action = self._action("Calcular", self.calculate, "F5", "menu.calc.run")
        calc.addAction(self.calc_action)
        export = self.menuBar().addMenu("&Exportar")
        for key, label, suffix in EXPORTS:
            item = self._action(label, lambda k=key, s=suffix: self.export(k, s), "",
                                f"menu.export.{key}")
            item.setEnabled(False)
            export.addAction(item)
            self._export_actions.append(item)
        self._build_extra_menus()

    def _line(self, form: QFormLayout, label: str) -> QLineEdit:
        edit = QLineEdit()
        form.addRow(label, edit)
        return edit

    def _tip(self, widget: QWidget, key: str) -> None:
        """Tooltip and status tip from the help text ``key``, if it exists."""
        try:
            text = help_text(key)
        except KeyError:
            return
        widget.setToolTip(text)
        widget.setStatusTip(text)

    def _build_info_group(self) -> tuple[QGroupBox, QFormLayout]:
        """Project data, language, unit preset and methods; the form takes more rows."""
        info = QGroupBox("Proyecto")
        form = QFormLayout(info)
        self._info: dict[str, QLineEdit] = {}
        for key, label in INFO_FIELDS:
            self._info[key] = self._line(form, label)
            self._tip(self._info[key], f"project.{key}")
        self.language = QComboBox()
        self.language.addItems(["es", "en"])
        form.addRow("Idioma", self.language)
        self._tip(self.language, "ui.language")
        self.units = QComboBox()
        self.units.addItems(sorted(PRESETS))
        self.units.currentTextChanged.connect(self._change_units)
        form.addRow("Unidades", self.units)
        self._tip(self.units, "ui.units")
        self._methods = {m: QCheckBox(m.value) for m in Method}
        row = QWidget()
        box = QHBoxLayout(row)
        box.setContentsMargins(0, 0, 0, 0)
        for check in self._methods.values():
            box.addWidget(check)
            self._tip(check, "ui.methods")
        form.addRow("Métodos", row)
        return info, form

    def _section_combo(self) -> QComboBox:
        combo = QComboBox()
        combo.setEditable(True)
        try:
            combo.addItems(aisc_shapes().labels("W"))
        except ShapeDatabaseError:
            pass
        return combo

    def _build_cases_group(self, title: str, headers: list[str],
                           blank: Callable[[], object]) -> QGroupBox:
        """Table of load cases (``self.cases``) with its *Agregar* and *Quitar* buttons."""
        group = QGroupBox(title)
        box = QVBoxLayout(group)
        self.cases = QTableWidget(0, len(headers))
        self.cases.setHorizontalHeaderLabels(headers)
        box.addWidget(self.cases)
        self._tip(self.cases, "ui.cases")
        buttons = QHBoxLayout()
        for label, slot in (("Agregar", blank),
                            ("Quitar", lambda: self.cases.removeRow(self.cases.currentRow()))):
            button = QPushButton(label)
            button.clicked.connect(lambda _checked=False, s=slot: s())
            self._tip(button, "ui.cases")
            buttons.addWidget(button)
        box.addLayout(buttons)
        return group

    def _end_form(self, layout: QVBoxLayout) -> None:
        """*Calcular* button at the end of the form."""
        calculate = QPushButton("Calcular")
        calculate.clicked.connect(self.calculate)
        self._tip(calculate, "action.calculate")
        layout.addWidget(calculate)
        layout.addStretch(1)

    def _build_results(self, form: QWidget, **viewer: Any) -> None:
        """Results tabs beside the scrolled form; ``viewer`` goes to :class:`Viewer3D`."""
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
        self.viewer = Viewer3D(parts_3d, snapshot=self.project_from_form, **viewer)
        self.tabs.addTab(self.viewer, "3D")
        for index, key in enumerate(("tab.summary", "tab.details", "tab.figures",
                                     "tab.viewer")):
            self.tabs.setTabToolTip(index, help_text(key))
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(scroll)
        splitter.addWidget(self.tabs)
        splitter.setSizes([480, 800])
        self.setCentralWidget(splitter)

    def _fill_info(self, project: Project) -> None:
        """Project data, language, unit preset and methods of the form."""
        info = project.info
        for key, edit in self._info.items():
            value = getattr(info, key)
            edit.setText("" if value is None else str(value))
        self.language.setCurrentText(info.language)
        self._units = info.unit_system()
        with QSignalBlocker(self.units):
            if isinstance(info.units, str):
                self.units.setCurrentText(info.units)
            else:
                if self.units.findText(CUSTOM_UNITS) < 0:
                    self.units.addItem(CUSTOM_UNITS)
                self.units.setCurrentText(CUSTOM_UNITS)
        for method, check in self._methods.items():
            check.setChecked(method in project.combinations.methods)

    def _project_data(self, **blocks: Any) -> dict[str, Any]:
        """Project data of the form: info and methods, the kept lists and ``blocks``."""
        info = self.project.info.model_dump()
        info.update({k: e.text().strip() for k, e in self._info.items()})
        info["language"] = self.language.currentText()
        if self.units.currentText() != CUSTOM_UNITS:
            info["units"] = self.units.currentText()
        combinations = self.project.combinations.model_dump()
        combinations["methods"] = [m.value for m, c in self._methods.items() if c.isChecked()]
        return {"info": info, "materials": [m.model_dump() for m in self.project.materials],
                "bolts": [b.model_dump() for b in self.project.bolts],
                "electrodes": [e.model_dump() for e in self.project.electrodes],
                "combinations": combinations, **blocks}

    @staticmethod
    def _validated(data: dict[str, Any]) -> Project:
        """The project of ``data``; raises ``ValueError`` when it is not valid."""
        try:
            return Project.model_validate(data)
        except Exception as exc:  # pydantic ValidationError and unit errors
            raise ValueError(str(exc)) from exc

    # -- units -------------------------------------------------------------------------
    def _change_units(self, name: str) -> None:
        """Convert every value of the form, so a bare number keeps its magnitude."""
        if name == CUSTOM_UNITS:
            return
        new = PRESETS.get(name)
        if new is None or new.name == self._units.name:
            return
        try:
            convert_fields(self._unit_fields(), self._units, new)
        except ValueError as exc:
            QMessageBox.warning(self, "Unidades", str(exc))
            with QSignalBlocker(self.units):
                self.units.setCurrentText(
                    self._units.name if self._units.name in PRESETS else CUSTOM_UNITS)
            return
        self._units = new
        self.project.info.units = name
        custom = self.units.findText(CUSTOM_UNITS)
        if custom >= 0:
            self.units.removeItem(custom)
        self.statusBar().showMessage(f"Unidades convertidas a {name}.")

    # -- files -------------------------------------------------------------------------
    def _new_model(self, template: dict[str, Any] | None = None) -> Project:
        return Project.model_validate(copy.deepcopy(template or self.template))

    def _update_title(self) -> None:
        name = self.path.name if self.path else "sin guardar"
        self.setWindowTitle(f"OpenConex — {self.noun} — {name}[*]")

    def new_project(self, template: dict[str, Any] | None = None) -> None:
        if not self.maybe_save():
            return
        self.project, self.path, self.report = self._new_model(template), None, None
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
        if getattr(project, self.family_key) is None:
            found = family_of(project)
            where = ("la ventana principal" if found.window is None else
                     "su propia ventana (Archivo > Abrir de la ventana principal)")
            QMessageBox.warning(self, "Otro tipo de proyecto",
                                f"Ese proyecto es {found.name_es}; ábralo en {where}.")
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

    # -- calculation and outputs -------------------------------------------------------
    def calculate(self) -> bool:
        try:
            self.project = self.project_from_form()
            self.report = family(self.family_key).build_report(self.project)
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
