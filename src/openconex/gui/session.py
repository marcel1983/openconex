# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Session conveniences shared by the editor windows.

- unsaved-change tracking and the *Save / Discard / Cancel* prompt;
- user preferences kept between sessions with :class:`QSettings` (recent
  projects, last folder, unit preset and window geometry);
- drag and drop of project and table files.

Preferences live in an INI file in the user's configuration folder, never in
the project, so they do not change any result.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path

from PySide6.QtCore import QByteArray, QSettings
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractSpinBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QLineEdit,
    QMenu,
    QMessageBox,
    QTableWidget,
    QWidget,
)

__all__ = [
    "MAX_RECENT",
    "ProjectSessionMixin",
    "add_recent_project",
    "app_settings",
    "ask_save_changes",
    "clear_recent_projects",
    "dropped_paths",
    "last_directory",
    "populate_recent_menu",
    "preferred_units",
    "recent_projects",
    "remember_directory",
    "set_preferred_units",
    "watch_changes",
]

MAX_RECENT = 8
_RECENT_KEY = "recent/projects"
_DIR_KEY = "paths/last_directory"
_UNITS_KEY = "units/preset"


def app_settings() -> QSettings:
    """User preferences (INI file in the user's configuration folder)."""
    return QSettings(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                     "OpenConex", "OpenConex")


def _string_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    return [str(item) for item in value if item]


# -- recent projects and folders ------------------------------------------------
def recent_projects() -> list[Path]:
    """Recent projects, newest first; files that no longer exist are skipped."""
    paths = [Path(item) for item in _string_list(app_settings().value(_RECENT_KEY))]
    return [path for path in paths if path.is_file()][:MAX_RECENT]


def add_recent_project(path: str | Path) -> None:
    """Put ``path`` first in the recent list and remember its folder."""
    target = Path(path).resolve()
    settings = app_settings()
    items = [item for item in _string_list(settings.value(_RECENT_KEY))
             if Path(item) != target]
    settings.setValue(_RECENT_KEY, [str(target), *items][:MAX_RECENT])
    settings.setValue(_DIR_KEY, str(target.parent))


def clear_recent_projects() -> None:
    app_settings().remove(_RECENT_KEY)


def last_directory() -> str:
    """Folder of the last project opened or saved ('' if unknown)."""
    value = app_settings().value(_DIR_KEY)
    return str(value) if value and Path(str(value)).is_dir() else ""


def remember_directory(path: str | Path) -> None:
    target = Path(path)
    folder = target if target.is_dir() else target.parent
    app_settings().setValue(_DIR_KEY, str(folder))


def populate_recent_menu(menu: QMenu, open_path: Callable[[Path], object]) -> None:
    """Fill ``menu`` with the recent projects; called each time it is shown."""
    menu.clear()
    paths = recent_projects()
    if not paths:
        empty = menu.addAction("(sin proyectos recientes)")
        empty.setEnabled(False)
        return
    for index, path in enumerate(paths, start=1):
        action = menu.addAction(f"&{index} {path.name}")
        action.setToolTip(str(path))
        action.setStatusTip(str(path))
        action.triggered.connect(lambda _checked=False, p=path: open_path(p))
    menu.addSeparator()
    menu.addAction("Borrar la lista", clear_recent_projects)


# -- units preference ---------------------------------------------------------------
def preferred_units() -> str:
    """Last unit preset chosen in the main window ('' if none)."""
    value = app_settings().value(_UNITS_KEY)
    return str(value) if value else ""


def set_preferred_units(name: str) -> None:
    app_settings().setValue(_UNITS_KEY, name)


# -- unsaved changes ------------------------------------------------------------------
def ask_save_changes(parent: QWidget | None, name: str) -> str:
    """Ask what to do with unsaved changes: ``save``, ``discard`` or ``cancel``."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle("Cambios sin guardar")
    box.setText(f"El proyecto «{name}» tiene cambios sin guardar.")
    box.setInformativeText("¿Desea guardarlos antes de continuar?")
    box.setStandardButtons(QMessageBox.StandardButton.Save
                           | QMessageBox.StandardButton.Discard
                           | QMessageBox.StandardButton.Cancel)
    box.setDefaultButton(QMessageBox.StandardButton.Save)
    box.button(QMessageBox.StandardButton.Save).setText("Guardar")
    box.button(QMessageBox.StandardButton.Discard).setText("Descartar")
    box.button(QMessageBox.StandardButton.Cancel).setText("Cancelar")
    answer = box.exec()
    if answer == QMessageBox.StandardButton.Save:
        return "save"
    if answer == QMessageBox.StandardButton.Discard:
        return "discard"
    return "cancel"


def watch_changes(root: QWidget, callback: Callable[[], object]) -> None:
    """Call ``callback`` when any editable widget under ``root`` changes."""
    def changed(*_args) -> None:
        callback()

    for edit in root.findChildren(QLineEdit):
        edit.textChanged.connect(changed)
    for combo in root.findChildren(QComboBox):
        combo.currentIndexChanged.connect(changed)
        if combo.isEditable():
            combo.editTextChanged.connect(changed)
    for button in root.findChildren(QAbstractButton):
        if button.isCheckable():
            button.toggled.connect(changed)
    for group in root.findChildren(QGroupBox):
        if group.isCheckable():
            group.toggled.connect(changed)
    for spin in root.findChildren(QAbstractSpinBox):
        signal = getattr(spin, "valueChanged", None)
        if signal is not None:
            signal.connect(changed)
    for table in root.findChildren(QTableWidget):
        table.itemChanged.connect(changed)
        table.model().rowsInserted.connect(changed)
        table.model().rowsRemoved.connect(changed)


# -- drag and drop --------------------------------------------------------------------
def dropped_paths(mime, suffixes: Iterable[str]) -> list[Path]:
    """Local files of a drag-and-drop payload whose suffix is in ``suffixes``."""
    if mime is None or not mime.hasUrls():
        return []
    allowed = {suffix.lower() for suffix in suffixes}
    paths = []
    for url in mime.urls():
        if url.isLocalFile():
            path = Path(url.toLocalFile())
            if path.suffix.lower() in allowed:
                paths.append(path)
    return paths


class ProjectSessionMixin:
    """Unsaved-change tracking, geometry memory and file drops for a window.

    The window calls :meth:`_init_session` once its widgets exist and
    :meth:`_set_clean` after opening, creating or saving a project. It
    implements :meth:`_session_save` (returns ``True`` when saved) and
    :meth:`_open_dropped`.
    """

    _session_key = "main"
    _drop_suffixes: tuple[str, ...] = (".ocnx",)

    def _init_session(self, form: QWidget) -> None:
        self._modified = False
        self.setAcceptDrops(True)
        watch_changes(form, self._mark_modified)
        geometry = app_settings().value(f"window/{self._session_key}")
        if isinstance(geometry, QByteArray) and not geometry.isEmpty():
            self.restoreGeometry(geometry)

    # state --------------------------------------------------------------------------
    @property
    def is_modified(self) -> bool:
        return getattr(self, "_modified", False)

    def _mark_modified(self) -> None:
        self._modified = True
        self.setWindowModified(True)

    def _set_clean(self) -> None:
        self._modified = False
        self.setWindowModified(False)

    def _session_name(self) -> str:
        path = getattr(self, "path", None)
        return path.name if path else "sin guardar"

    def _session_save(self) -> bool:  # pragma: no cover - overridden
        raise NotImplementedError

    def maybe_save(self) -> bool:
        """``True`` when it is safe to discard the form (saved, discarded or clean)."""
        if not self.is_modified:
            return True
        answer = ask_save_changes(self, self._session_name())
        if answer == "save":
            return self._session_save() and not self.is_modified
        return answer == "discard"

    # dialogs --------------------------------------------------------------------------
    def _open_file_name(self, caption: str = "Abrir proyecto") -> str:
        path, _ = QFileDialog.getOpenFileName(self, caption, last_directory(),
                                               "OpenConex (*.ocnx);;Todos (*)")
        return path

    def _save_file_name(self, caption: str = "Guardar proyecto") -> str:
        start = last_directory()
        path = getattr(self, "path", None)
        if path is not None:
            start = str(path)
        selected, _ = QFileDialog.getSaveFileName(self, caption, start, "OpenConex (*.ocnx)")
        return selected

    def _export_file_name(self, suffix: str) -> str:
        start = last_directory()
        path = getattr(self, "path", None)
        if path is not None:
            start = str(path.with_suffix(suffix))
        selected, _ = QFileDialog.getSaveFileName(self, "Exportar", start, f"*{suffix}")
        if selected:
            remember_directory(selected)
        return selected

    # Qt events ------------------------------------------------------------------------
    def closeEvent(self, event) -> None:  # noqa: N802
        if not self.maybe_save():
            event.ignore()
            return
        app_settings().setValue(f"window/{self._session_key}", self.saveGeometry())
        event.accept()

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if dropped_paths(event.mimeData(), self._drop_suffixes):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        self.dragEnterEvent(event)

    def dropEvent(self, event) -> None:  # noqa: N802
        paths = dropped_paths(event.mimeData(), self._drop_suffixes)
        if not paths:
            event.ignore()
            return
        event.acceptProposedAction()
        self._open_dropped(paths[0])

    def _open_dropped(self, path: Path) -> None:  # pragma: no cover - overridden
        raise NotImplementedError
