# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Main window and entry point of the desktop application.

:class:`MainWindow` edits base plate projects (its form, calculation and
outputs come from :class:`openconex.gui.base_plate.BasePlateEditor`) and is
the application shell: ribbon, opening and saving, the start gallery, the
windows of the other families and the batch calculation.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressDialog,
)

from openconex.core.loads import Method
from openconex.families import ConnectionFamily, family, family_of
from openconex.gui.advanced import BasePlateAdvancedForm
from openconex.gui.base_plate import (
    UNIT_PRESET_LABELS,
    BasePlateEditor,
    SectionInput,
)
from openconex.gui.batch import BatchDialog, BatchSummaryDialog, calculate_batch
from openconex.gui.branding import app_icon, show_splash, splash_pixmap
from openconex.gui.help import HelpDialog
from openconex.gui.ribbon import Ribbon, add_result_views, add_view_page
from openconex.gui.session import (
    ProjectSessionMixin,
    add_recent_project,
    populate_recent_menu,
    preferred_units,
    watch_changes,
)
from openconex.io.csi import is_csi_export
from openconex.io.project import Project, load_project, save_project
from openconex.report.builder import Report
from openconex.units import PRESETS, Kind, UnitSystem

__all__ = ["MainWindow", "main"]

APP_NAME = "OpenConex"


class MainWindow(BasePlateEditor, ProjectSessionMixin, QMainWindow):
    """Small project editor and report viewer for base plates."""

    _session_key = "main"
    _drop_suffixes = (".ocnx", ".xlsx", ".csv")

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
        self._suspend_grade_sync = False
        self._method_boxes: dict[Method, QCheckBox] = {}
        self._combination_edits: dict[str, QLineEdit] = {}
        self.advanced: BasePlateAdvancedForm | None = None
        self._unit_actions: dict[str, QAction] = {}
        self._export_actions: list[QAction] = []
        self._build_ui()

    # -- construction -----------------------------------------------------------
    def _build_ui(self) -> None:
        self.setWindowTitle(f"{APP_NAME}[*]")
        self.setWindowIcon(app_icon())
        self.resize(1280, 860)
        self._build_body()
        self._build_ribbon()
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
        preset = preferred_units()
        if preset in PRESETS and preset != self._units.name:
            self.set_unit_system(preset)
        self._init_session(self._form)
        # The 3D tab follows the form: it regenerates shortly after each edit.
        watch_changes(self._form, self.viewer.schedule_update)
        self._set_clean()
        self.statusBar().showMessage("Abra un proyecto .ocnx o importe apoyos de "
                                     "SAP2000/ETABS.")

    def _build_ribbon(self) -> None:
        """Ribbon with the commands of the window (see :mod:`openconex.gui.ribbon`)."""
        def action(label: str, slot, shortcut: str, key: str) -> QAction:
            item = QAction(label, self)
            if shortcut:
                item.setShortcut(shortcut)
            item.triggered.connect(lambda _checked=False: slot())
            self._tip(item, key)
            return item

        new = action("Nueva conexión…", self.new_connection_dialog, "Ctrl+N", "main.file.new")
        open_ = action("Abrir…", self.open_project_dialog, "Ctrl+O", "main.file.open")
        recent = QMenu("Abrir reciente", self)
        recent.setToolTipsVisible(True)
        recent.aboutToShow.connect(lambda: populate_recent_menu(recent, self.open_project))
        recent_action = action("Abrir reciente", lambda: None, "", "main.file.recent")
        save = action("Guardar", self.save_project_dialog, "Ctrl+S", "main.file.save")
        save_as = action("Guardar como…", lambda: self.save_project_dialog(save_as=True), "",
                         "main.file.save_as")
        csi = action("Importar SAP2000 / ETABS…", self.import_csi_dialog, "",
                     "main.file.import_csi")
        table = action("Importar Excel / CSV…", self.import_table_dialog, "",
                       "main.file.import_table")
        exit_ = action("Salir", self.close, "", "main.file.exit")
        self.calc_action = action("Calcular", self.calculate, "F5", "main.calc.run")
        self.opt_action = action("Optimizar N, B y tp", self.optimize, "",
                                 "main.calc.optimize")
        self.global_opt_action = action("Optimización global…", self.optimize_global, "",
                                        "main.calc.optimize_global")
        batch = action("Calcular lote…", self.calculate_batch_dialog, "", "main.calc.batch")
        exports: dict[str, QAction] = {}
        for key, label, suffix in (
                ("html", "Memoria HTML…", ".html"),
                ("docx", "Memoria Word…", ".docx"),
                ("pdf", "Memoria PDF…", ".pdf"),
                ("dxf", "Plano DXF…", ".dxf"),
                ("step", "Modelo STEP…", ".step"),
                ("stl", "Modelo STL…", ".stl")):
            item = action(label, lambda k=key, s=suffix: self.export(k, s), "",
                          f"main.export.{key}")
            item.setEnabled(False)
            exports[key] = item
            self._export_actions.append(item)

        ribbon = self.ribbon = Ribbon(self)
        home = ribbon.add_page("Inicio")
        group = home.group("Proyecto")
        group.large(new, "Nueva", "new")
        group.large(open_, "Abrir", "open")
        group.menu(recent_action, recent, "Recientes", "recent")
        group.large(save, "Guardar", "save")
        group.small(save_as, "Guardar como", "save_as")
        group.small(exit_, "Salir", "exit")
        group = home.group("Importar")
        group.large(csi, "SAP2000\nETABS", "import_csi")
        group.large(table, "Excel\nCSV", "import_table")
        group = home.group("Calcular")
        group.large(self.calc_action, "Calcular\n(F5)", "calculate")
        group.small(self.opt_action, "Optimizar N, B, tp", "optimize")
        group.small(self.global_opt_action, "Optimización global", "optimize_global")
        group.small(batch, "Calcular lote", "batch")
        group = home.group("Memoria")
        group.large(exports["pdf"], "PDF", "pdf")
        group.small(exports["docx"], "Word", "docx")
        group.small(exports["html"], "HTML", "html")

        connections = ribbon.add_page("Conexiones")
        connections.group("Nueva conexión").large(new, "Galería", "gallery")
        group = connections.group("Familias")
        group.large(action("Placa base…", lambda: self.new_connection_dialog("base_plate"),
                           "", "main.file.base_plate"), "Placa\nbase", "base_plate")
        group.large(action("Nueva conexión de corte…", lambda: self.open_shear_window(), "",
                           "main.file.shear"), "Corte", "shear")
        group.large(action("Nueva conexión de momento…", lambda: self.open_moment_window(),
                           "", "main.file.moment"), "Momento", "moment")
        group.large(action("Nuevo empalme…", lambda: self.open_splice_window(), "",
                           "main.file.splice"), "Empalme", "splice")
        group = connections.group("Bibliotecas")
        group.large(action("Secciones…", self.open_section_library, "",
                           "main.library.sections"), "Secciones", "sections")
        group.large(action("Materiales…", self.open_material_library, "",
                           "main.library.materials"), "Materiales", "materials")

        calc = ribbon.add_page("Cálculo")
        group = calc.group("Ejecutar")
        group.large(self.calc_action, "Calcular\n(F5)", "calculate")
        group.large(batch, "Lote", "batch")
        group = calc.group("Optimizar")
        group.large(self.opt_action, "N, B, tp", "optimize")
        group.large(self.global_opt_action, "Global", "optimize_global")
        add_result_views(self, calc.group("Ver resultados"), self.tabs)

        add_view_page(ribbon, self.tabs, self.viewer)

        export = ribbon.add_page("Exportar")
        group = export.group("Memoria de cálculo")
        for key, caption in (("pdf", "PDF"), ("docx", "Word"), ("html", "HTML")):
            group.large(exports[key], caption, key)
        group = export.group("Planos y modelos")
        for key, caption in (("dxf", "Plano\nDXF"), ("step", "STEP"), ("stl", "STL")):
            group.large(exports[key], caption, key)

        settings = ribbon.add_page("Configuración")
        group = settings.group("Sistema de unidades")
        self._unit_group = QActionGroup(self)
        self._unit_group.setExclusive(True)
        for name in ("SI_kN_m", "SI_N_mm", "MKS", "US"):
            item = QAction(UNIT_PRESET_LABELS[name], self)
            item.setCheckable(True)
            item.triggered.connect(
                lambda _checked=False, preset=name: self.set_unit_system(preset))
            self._unit_group.addAction(item)
            self._unit_actions[name] = item
            self._tip(item, "main.units.presets")
            group.small(item, UNIT_PRESET_LABELS[name], "units")
        group = settings.group("Unidades por magnitud")
        group.large(action("Configurar por magnitud…", self.configure_units, "",
                           "main.units.configure"), "Por\nmagnitud", "units_config")
        self._check_unit_action(self._units.name)

        help_ = ribbon.add_page("Ayuda")
        group = help_.group("Ayuda")
        group.large(action("Guía rápida", self._show_guide, "F1", "main.help.guide"),
                    "Guía rápida\n(F1)", "guide")
        group.small(action("Referencia de campos", lambda: HelpDialog("fields", self).exec(),
                           "", "main.help.fields"), "Referencia de campos", "help_fields")
        group.small(action("Comandos del ribbon", lambda: HelpDialog("menus", self).exec(), "",
                           "main.help.menus"), "Comandos del ribbon", "help_menus")
        group.small(action("Verificaciones", lambda: HelpDialog("checks", self).exec(), "",
                           "main.help.checks"), "Verificaciones", "help_checks")
        help_.group("Programa").large(action("Acerca de", self._show_about, "",
                                             "main.help.about"), "Acerca de", "about")

    def _show_guide(self) -> None:
        QMessageBox.information(
            self, "Guía rápida",
            "1. Elija el tipo de base y la columna.\n"
            "2. Complete dimensiones, anclajes, concreto y bloques opcionales.\n"
            "3. Defina casos y combinaciones LRFD/ASD.\n"
            "4. Pulse Calcular (F5).\n"
            "5. Revise Resumen, Verificaciones y Figuras; exporte la memoria o el plano.\n\n"
            "Cada campo tiene un tooltip y la pestaña Ayuda → Referencia de campos "
            "explica qué es, cómo se usa y cómo afecta al cálculo.")

    def _show_about(self) -> None:
        from openconex import __version__
        QMessageBox.about(
            self, "Acerca de OpenConex",
            f"OpenConex {__version__}\n\n"
            "Cálculo de conexiones metálicas según AISC 360-22, "
            "AISC Design Guide 1 y ACI 318-19.\n\n"
            "Software libre bajo GPL-3.0-or-later. La responsabilidad del "
            "diseño corresponde al profesional que lo firma.")

    # -- files, windows and batches ---------------------------------------------
    def open_project_dialog(self) -> None:
        path = self._open_file_name()
        if path:
            self.open_project(path)

    def open_project(self, path: str | Path) -> None:
        try:
            project = load_project(path)
        except Exception as exc:
            QMessageBox.critical(self, "Error al abrir", str(exc))
            return
        if family_of(project).window is not None:
            add_recent_project(path)
            self.open_family_window(family_of(project), project, path)
            return
        if not self.maybe_save():
            return
        self.project = project
        self.path = Path(path)
        self._fill_form(project)
        self._clear_report()
        self._set_clean()
        add_recent_project(path)
        self.statusBar().showMessage(f"Proyecto abierto: {self.path}")

    def open_project_model(self, project: Project,
                           path: str | Path | None = None) -> None:
        """Load an in-memory project, for example from the connection gallery."""
        self.project = project
        self.path = None if path is None else Path(path)
        self._fill_form(project)
        self._clear_report()
        self._set_clean()
        self.statusBar().showMessage(
            f"Proyecto creado: {project.info.name or 'sin nombre'}")

    def maybe_save(self) -> bool:
        return self.project is None or super().maybe_save()

    def _session_name(self) -> str:
        if self.path is not None:
            return self.path.name
        return (self.project.info.name if self.project else "") or "sin guardar"

    def _session_save(self) -> bool:
        return self.save_project_dialog()

    def _open_dropped(self, path: Path) -> None:
        suffix = path.suffix.lower()
        if suffix == ".ocnx":
            self.open_project(path)
        elif suffix == ".xlsx" and is_csi_export(path):
            self.import_csi_dialog(str(path))
        else:
            self.import_table_dialog(str(path))

    def new_connection_dialog(self, family_id: str | None = None) -> None:
        """Start gallery; ``family_id`` opens it on that family's subtypes."""
        from openconex.gui.start import ConnectionStartDialog

        dialog = ConnectionStartDialog(self, family_id)
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.selection is None:
            return
        selection = dialog.selection
        if selection.kind == "open" and selection.path is not None:
            self.open_project(selection.path)
        elif selection.kind == "base_plate" and selection.project is not None:
            if not self.maybe_save():
                return
            self.open_project_model(selection.project)
        elif selection.project is not None:
            self.open_family_window(family_of(selection.project), selection.project)

    def open_family_window(self, fam: ConnectionFamily, project: Project | None = None,
                           path: str | Path | None = None):
        """Open a project of a family with its own window (shear, moment, splice)."""
        window = fam.window_class()(project, path, parent=self)
        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        attr = f"_{fam.command}_windows"
        setattr(self, attr, [*getattr(self, attr, []), window])
        window.show()
        self.statusBar().showMessage(f"Se abrió {fam.name_es} en otra ventana.")
        return window

    def open_shear_window(self, project: Project | None = None,
                          path: str | Path | None = None):
        """Open a beam-end shear connection project in its own window."""
        return self.open_family_window(family("shear_connection"), project, path)

    def open_moment_window(self, project: Project | None = None,
                           path: str | Path | None = None):
        """Open a beam-to-column moment connection project in its own window."""
        return self.open_family_window(family("moment_connection"), project, path)

    def open_splice_window(self, project: Project | None = None,
                           path: str | Path | None = None):
        """Open a beam or column splice project in its own window."""
        return self.open_family_window(family("splice"), project, path)

    def _update_title(self) -> None:
        name = self.project.info.name if self.project else ""
        self.setWindowTitle(f"{APP_NAME} — {name}[*]" if name else f"{APP_NAME}[*]")

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

    def save_project_dialog(self, save_as: bool = False) -> bool:
        if self.project is None:
            QMessageBox.warning(self, "Sin proyecto", "Abra un proyecto .ocnx primero.")
            return False
        path = self.path
        if save_as or path is None:
            selected = self._save_file_name()
            if not selected:
                return False
            path = Path(selected)
            if path.suffix.lower() != ".ocnx":
                path = path.with_suffix(".ocnx")
        return self.save_project_to(path)

    def save_project_to(self, path: str | Path) -> bool:
        project = self._project_from_form()
        if project is None:
            return False
        try:
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


def _start_window(project: Project, path: Path | None = None):
    """The window that opens ``project`` at start-up, according to its family."""
    fam = family_of(project)
    if fam.window is not None:
        return fam.window_class()(project, path)
    window = MainWindow()
    window.open_project_model(project, path)
    return window


def main(argv: list[str] | None = None) -> int:
    args = sys.argv if argv is None else argv
    no_splash = "--no-splash" in args[1:]
    no_start = "--no-start" in args[1:]
    check_assets = "--check-assets" in args[1:]
    qt_args = [arg for arg in args
               if arg not in {"--no-splash", "--check-assets", "--no-start"}]
    if "--version" in qt_args[1:]:
        from openconex import __version__
        if sys.stdout is not None:
            print(f"OpenConex {__version__}")
        return 0

    from openconex import __version__

    app = QApplication(qt_args)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setOrganizationName(APP_NAME)
    app.setWindowIcon(app_icon())

    if check_assets:
        return 0 if not app_icon().isNull() and not splash_pixmap().isNull() else 1

    splash = None if no_splash else show_splash(app)
    try:
        projects = [arg for arg in qt_args[1:] if not arg.startswith("-")]
        if projects or no_start:
            window = MainWindow()
            if projects:
                window.open_project(projects[0])
            window.show()
            if splash is not None:
                splash.finish(window)
            return app.exec()

        from openconex.gui.start import ConnectionStartDialog

        start = ConnectionStartDialog()
        if splash is not None:
            splash.finish(start)
        if start.exec() != QDialog.DialogCode.Accepted or start.selection is None:
            return 0
        selection = start.selection
        window = None
        if selection.kind == "open" and selection.path is not None:
            try:
                project = load_project(selection.path)
            except Exception as exc:
                QMessageBox.critical(None, "Error al abrir", str(exc))
                return 1
            add_recent_project(selection.path)
            window = _start_window(project, selection.path)
        elif selection.project is not None:
            window = _start_window(selection.project)
        if window is None:
            return 0
        window.show()
        if splash is not None:
            splash.finish(window)
        return app.exec()
    finally:
        if splash is not None:
            splash.close()
