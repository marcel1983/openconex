# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Unsaved changes, preferences and drag and drop of the desktop windows."""

import os
import shutil
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")

from PySide6.QtCore import QMimeData, QUrl
from PySide6.QtWidgets import QMenu, QPushButton

from openconex.gui import session
from openconex.gui.app import MainWindow
from openconex.gui.moment import MomentWindow
from openconex.gui.shear import ShearWindow
from openconex.gui.start import ConnectionStartDialog
from openconex.io.csi import is_csi_export
from openconex.io.project import load_project

EXAMPLE = Path(__file__).parents[2] / "examples" / "base_plate_dg1_4_7_11.ocnx"


@pytest.fixture
def example(tmp_path) -> Path:
    path = tmp_path / "placa.ocnx"
    shutil.copyfile(EXAMPLE, path)
    return path


def _main(qtbot, path: Path | None = None) -> MainWindow:
    window = MainWindow()
    qtbot.addWidget(window)
    if path is not None:
        window.open_project(path)
    return window


# -- unsaved changes --------------------------------------------------------------------
def test_open_is_clean_edit_is_modified_save_is_clean(qtbot, example, tmp_path):
    window = _main(qtbot, example)
    assert not window.is_modified
    window._quantity_fields["N"][0].setText("20 in")
    assert window.is_modified
    assert window.isWindowModified()
    target = tmp_path / "copia.ocnx"
    assert window.save_project_to(target)
    assert not window.is_modified
    assert load_project(target).base_plate.N is not None


def test_gallery_project_starts_clean(qtbot, example):
    window = _main(qtbot)
    window.open_project_model(load_project(example))
    assert not window.is_modified


def test_close_cancel_keeps_window_open(qtbot, example, monkeypatch):
    window = _main(qtbot, example)
    window.show()
    window._info_edits["name"].setText("Otro nombre")
    asked = []
    monkeypatch.setattr(session, "ask_save_changes",
                        lambda parent, name: asked.append(name) or "cancel")
    assert not window.close()
    assert asked == ["placa.ocnx"]
    assert window.isVisible()
    monkeypatch.setattr(session, "ask_save_changes", lambda parent, name: "discard")
    assert window.close()


def test_close_save_writes_the_file(qtbot, example, monkeypatch):
    window = _main(qtbot, example)
    window._info_edits["name"].setText("Guardado al cerrar")
    monkeypatch.setattr(session, "ask_save_changes", lambda parent, name: "save")
    assert window.close()
    assert load_project(example).info.name == "Guardado al cerrar"


def test_clean_window_closes_without_asking(qtbot, example, monkeypatch):
    window = _main(qtbot, example)
    monkeypatch.setattr(session, "ask_save_changes",
                        lambda parent, name: pytest.fail("should not ask"))
    assert window.close()


def test_open_another_project_cancel_keeps_edits(qtbot, example, monkeypatch):
    window = _main(qtbot, example)
    window._info_edits["name"].setText("Editado")
    monkeypatch.setattr(session, "ask_save_changes", lambda parent, name: "cancel")
    window.open_project(EXAMPLE)
    assert window.path == example
    assert window._info_edits["name"].text() == "Editado"


def test_geometry_drag_marks_modified(qtbot, example):
    window = _main(qtbot, example)
    window._apply_geometry({"N": 500.0})
    assert window.is_modified


def test_new_material_marks_modified(qtbot, example):
    from openconex.io.project import MaterialInput

    window = _main(qtbot, example)
    window.add_custom_material(MaterialInput(name="Acero propio", Fy="50 ksi", Fu="65 ksi"))
    assert window.is_modified


def test_shear_window_tracks_changes(qtbot, tmp_path):
    window = ShearWindow()
    qtbot.addWidget(window)
    assert not window.is_modified
    window._fields["thickness"].setText("5/16 in")
    assert window.is_modified
    window._set_clean()
    window.cases.cellWidget(0, 1).setCurrentText("L")
    assert window.is_modified
    assert window.save_to(tmp_path / "corte.ocnx")
    assert not window.is_modified
    assert "*" not in window.windowTitle().replace("[*]", "")


def test_moment_window_tracks_changes(qtbot, tmp_path):
    window = MomentWindow()
    qtbot.addWidget(window)
    assert not window.is_modified
    window._info["name"].setText("Nudo B-3")
    assert window.is_modified
    assert window.save_to(tmp_path / "momento.ocnx")
    assert not window.is_modified
    assert window.windowTitle().endswith("momento.ocnx[*]")


# -- preferences ------------------------------------------------------------------------
def test_recent_projects_are_unique_newest_first_and_existing(tmp_path):
    paths = []
    for index in range(session.MAX_RECENT + 2):
        path = tmp_path / f"p{index}.ocnx"
        path.write_text("{}", encoding="utf-8")
        paths.append(path)
        session.add_recent_project(path)
    session.add_recent_project(paths[-3])
    recent = session.recent_projects()
    assert len(recent) == session.MAX_RECENT
    assert recent[0] == paths[-3].resolve()
    assert len(set(recent)) == len(recent)
    paths[-1].unlink()
    assert paths[-1].resolve() not in session.recent_projects()
    assert session.last_directory() == str(tmp_path.resolve())
    session.clear_recent_projects()
    assert session.recent_projects() == []


def test_open_and_save_fill_the_recent_menu(qtbot, example):
    window = _main(qtbot, example)
    assert session.recent_projects() == [example.resolve()]
    menu = QMenu()
    opened = []
    session.populate_recent_menu(menu, opened.append)
    actions = [action for action in menu.actions() if not action.isSeparator()]
    assert actions[0].text().endswith("placa.ocnx")
    actions[0].trigger()
    assert opened == [example.resolve()]
    assert window.path.resolve() == example.resolve()


def test_empty_recent_menu(qtbot):
    menu = QMenu()
    session.populate_recent_menu(menu, lambda path: None)
    assert [action.isEnabled() for action in menu.actions()] == [False]


def test_unit_preset_is_remembered(qtbot):
    window = _main(qtbot)
    window.set_unit_system("SI_N_mm")
    other = _main(qtbot)
    assert other._units.name == "SI_N_mm"
    assert other._unit_actions["SI_N_mm"].isChecked()


def test_window_geometry_is_saved_on_close(qtbot):
    window = _main(qtbot)
    window.show()
    window.resize(900, 640)
    assert window.close()
    assert not session.app_settings().value("window/main").isEmpty()


def test_start_gallery_lists_recent_projects(qtbot, example):
    session.add_recent_project(example)
    dialog = ConnectionStartDialog()
    qtbot.addWidget(dialog)
    button = next(b for b in dialog.findChildren(QPushButton)
                  if b.objectName() == "recentProject")
    assert button.text().startswith("placa.ocnx")
    button.click()
    assert dialog.selection.kind == "open"
    assert dialog.selection.path == example.resolve()


# -- drag and drop ----------------------------------------------------------------------
def _mime(*paths: Path) -> QMimeData:
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(path)) for path in paths])
    return mime


def test_dropped_paths_filters_by_suffix(tmp_path):
    files = [tmp_path / "a.ocnx", tmp_path / "b.txt", tmp_path / "c.CSV"]
    found = session.dropped_paths(_mime(*files), (".ocnx", ".csv"))
    assert [path.name for path in found] == ["a.ocnx", "c.CSV"]
    assert session.dropped_paths(QMimeData(), (".ocnx",)) == []


def test_drop_routes_files(qtbot, example, tmp_path, monkeypatch):
    window = _main(qtbot)
    calls = []
    monkeypatch.setattr(window, "import_table_dialog",
                        lambda file="": calls.append(("table", file)))
    monkeypatch.setattr(window, "import_csi_dialog",
                        lambda file="": calls.append(("csi", file)))

    window._open_dropped(example)
    assert window.path == example

    table = tmp_path / "reacciones.csv"
    table.write_text("support,case,P\nJ1,D,10\n", encoding="utf-8")
    window._open_dropped(table)

    from openpyxl import Workbook

    csi = tmp_path / "modelo.xlsx"
    book = Workbook()
    book.active["A1"] = "TABLE:  Joint Reactions"
    book.save(csi)
    generic = tmp_path / "tabla.xlsx"
    book = Workbook()
    book.active.append(["support", "case", "P"])
    book.save(generic)
    window._open_dropped(csi)
    window._open_dropped(generic)
    assert calls == [("table", str(table)), ("csi", str(csi)), ("table", str(generic))]


def test_is_csi_export_handles_unreadable_files(tmp_path):
    broken = tmp_path / "roto.xlsx"
    broken.write_text("no es un libro", encoding="utf-8")
    assert not is_csi_export(broken)


def test_import_dialogs_accept_an_initial_file(qtbot, tmp_path):
    from openconex.gui.import_supports import ImportSupportsDialog
    from openconex.gui.import_table import TableImportDialog

    file = str(tmp_path / "modelo.xlsx")
    csi = ImportSupportsDialog(None, "plantilla", file)
    table = TableImportDialog(None, "US", file)
    qtbot.addWidget(csi)
    qtbot.addWidget(table)
    for dialog in (csi, table):
        assert dialog._file.text() == file
        assert dialog._output.text() == str(tmp_path)
