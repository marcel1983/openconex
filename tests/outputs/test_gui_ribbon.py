# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Ribbon of the main window and of the family windows (``openconex.gui.ribbon``)."""

import os
from pathlib import Path
from xml.dom import minidom

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")

from PySide6.QtWidgets import QMessageBox

from openconex.gui.app import MainWindow
from openconex.gui.icons import ICONS, icon, svg
from openconex.gui.moment import MomentWindow
from openconex.gui.shear import ShearWindow
from openconex.gui.splice import SpliceWindow
from openconex.gui.start import ConnectionStartDialog
from openconex.io.project import load_project

EXAMPLES = Path(__file__).parents[2] / "examples"
TABS = ["Inicio", "Conexiones", "Cálculo", "Vista 3D", "Exportar", "Configuración", "Ayuda"]


def test_every_icon_is_valid_svg_and_renders(qapp):
    for name in ICONS:
        minidom.parseString(svg(name))
        pixmap = icon(name).pixmap(32, 32)
        assert not pixmap.isNull(), name
        assert pixmap.toImage().pixelColor(0, 0).alpha() == 0, name


def test_main_window_tabs_and_shortcuts(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    assert [page.title for page in window.ribbon.pages] == TABS
    assert window.menuWidget() is window.ribbon
    assert not window.menuBar().actions()
    # Shortcuts work from any tab: the actions belong to the window.
    for action in (window.calc_action, window.opt_action, *window._export_actions):
        assert action in window.actions()
    assert window.calc_action.shortcut().toString() == "F5"
    captions = {button.caption for _t, _g, button in window.ribbon.buttons()}
    assert {"Calcular\n(F5)", "Galería", "Placa\nbase", "Secciones", "PDF",
            "Por\nmagnitud", "Guía rápida\n(F1)"} <= captions
    for _tab, _group, button in window.ribbon.buttons():
        assert not button.icon().isNull(), button.caption


def test_caption_survives_action_changes(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    button = window.ribbon.find("PDF")
    assert button.text() == "PDF"
    window._export_actions[2].setEnabled(True)
    assert button.text() == "PDF"
    assert button.isEnabled()
    assert button.minimumWidth() >= button.fontMetrics().horizontalAdvance("PDF")


def test_collapse_and_expand(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    ribbon = window.ribbon
    full = ribbon.height()
    ribbon.set_collapsed(True)
    assert ribbon.collapsed and ribbon.height() < full
    ribbon.tabBarClicked.emit(2)
    assert not ribbon.collapsed and ribbon.height() == full
    ribbon.tabBarDoubleClicked.emit(0)
    assert ribbon.collapsed
    ribbon.tabBarDoubleClicked.emit(0)
    assert not ribbon.collapsed


def test_result_and_view_buttons_bring_their_tab_forward(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.ribbon.find("Verificaciones").click()
    assert window.tabs.currentWidget() is window.details
    window.ribbon.find("Figuras").click()
    assert window.tabs.tabText(window.tabs.currentIndex()) == "Figuras"
    window.ribbon.find("Planta").click()
    assert window.tabs.currentWidget() is window.viewer
    # The viewer's own bar gives its buttons to the ribbon.
    assert all(widget.isHidden() for widget in window.viewer._controls)


def test_view_toggles_follow_the_viewer(qtbot):
    window = ShearWindow(load_project(EXAMPLES / "shear_single_plate.ocnx"))
    qtbot.addWidget(window)
    actions = window.viewer.view_actions
    actions["auto"].setChecked(False)
    assert not window.viewer.auto_update
    window.viewer.set_auto_update(True)
    assert actions["auto"].isChecked()
    window.viewer.set_controls_visible(True)
    assert not window.viewer._controls[0].isHidden()


def test_unit_presets_of_a_family_window(qtbot):
    path = EXAMPLES / "shear_single_plate.ocnx"
    window = ShearWindow(load_project(path), path)
    qtbot.addWidget(window)
    actions = window._unit_actions
    assert actions[window.units.currentText()].isChecked()
    actions["SI_N_mm"].trigger()
    assert window.units.currentText() == "SI_N_mm"
    assert actions["SI_N_mm"].isChecked()
    assert sum(action.isChecked() for action in actions.values()) == 1
    window.units.setCurrentText("US")
    assert actions["US"].isChecked() and not actions["SI_N_mm"].isChecked()


def test_family_window_reaches_the_main_window(qtbot, monkeypatch):
    main = MainWindow()
    qtbot.addWidget(main)
    calls = []
    monkeypatch.setattr(main, "open_moment_window", lambda: calls.append("moment"))
    monkeypatch.setattr(main, "new_connection_dialog",
                        lambda family_id=None: calls.append(family_id))
    window = MomentWindow(parent=main)
    assert [g.title for g in window.ribbon.page("Conexiones").groups] == [
        "Nuevo proyecto", "Nueva conexión", "Familias", "Bibliotecas"]
    window.ribbon.find("Momento").click()
    window.ribbon.find("Placa\nbase").click()
    window.ribbon.find("Galería").click()
    assert calls == ["moment", "base_plate", None]
    window.close()


def test_family_window_without_main_window(qtbot):
    window = SpliceWindow()
    qtbot.addWidget(window)
    groups = [g.title for g in window.ribbon.page("Conexiones").groups]
    assert groups == ["Nuevo proyecto"]


def test_about_of_every_family_window(qtbot, monkeypatch):
    shown = []
    monkeypatch.setattr(QMessageBox, "about", lambda _parent, title, _text: shown.append(title))
    for window_type in (ShearWindow, MomentWindow, SpliceWindow):
        window = window_type()
        qtbot.addWidget(window)
        window.ribbon.find("Acerca de").click()
    assert shown == ["Acerca de OpenConex"] * 3


def test_gallery_opens_on_a_family(qtbot):
    dialog = ConnectionStartDialog(None, "base_plate")
    qtbot.addWidget(dialog)
    assert dialog._stack.currentIndex() == 1
    assert dialog._family is not None and dialog._family.id == "base_plate"
    plain = ConnectionStartDialog(None)
    qtbot.addWidget(plain)
    assert plain._stack.currentIndex() == 0


def test_help_dialog_lists_ribbon_commands_apart_from_fields(qtbot):
    from PySide6.QtCore import Qt

    from openconex.gui.help import HelpDialog

    def keys(section):
        dialog = HelpDialog(section)
        qtbot.addWidget(dialog)
        return {dialog.list.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(dialog.list.count())}

    commands, fields = keys("menus"), keys("fields")
    assert {"main.calc.run", "menu.calc.run", "main.file.base_plate",
            "menu.units.presets", "viewer.iso"} <= commands
    # Dialog controls are listed in both sections, as before the ribbon.
    assert all(key.startswith("dialog.") for key in commands & fields)
    assert "N" in fields or any(key.startswith("base.") for key in fields)
