# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Ribbon of the OpenConex windows: tabs of command groups, as in office suites.

The ribbon replaces the menu bar. Its buttons show the window's own
:class:`QAction` objects, so a command keeps one tooltip, one shortcut and one
enabled state wherever it appears. The window installs it with
``setMenuWidget``; :meth:`Ribbon.add_page` adds a tab, :meth:`RibbonPage.group`
a labelled group and the group's ``large``/``small`` methods the buttons.

Ctrl+F1 or a double click on a tab folds the ribbon to its tab bar; clicking
a tab of a folded ribbon unfolds it.
"""

from __future__ import annotations

from collections.abc import Iterator

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from openconex.gui.icons import icon
from openconex.help import help_text

__all__ = ["Ribbon", "RibbonButton", "RibbonGroup", "RibbonPage", "add_result_views",
           "add_view_page"]

LARGE_ICON = QSize(32, 32)
SMALL_ICON = QSize(16, 16)
SMALL_ROWS = 3
"""Small buttons stack in columns of this many rows, as in office ribbons."""

_STYLE = """
Ribbon::pane { border: none; border-bottom: 1px solid palette(mid); background: palette(window); }
Ribbon > QTabBar::tab { padding: 5px 16px; margin-right: 1px; border: 1px solid transparent;
                        border-bottom: none; }
Ribbon > QTabBar::tab:selected { border-color: palette(mid); background: palette(window);
                                 font-weight: bold; }
Ribbon > QTabBar::tab:!selected:hover { background: palette(midlight); }
QToolButton#ribbonButton { border: 1px solid transparent; border-radius: 3px; padding: 1px 3px; }
QToolButton#ribbonButton:hover { border-color: palette(mid); background: palette(midlight); }
QToolButton#ribbonButton:checked { border-color: palette(highlight);
                                   background: palette(midlight); }
QLabel#ribbonGroupTitle { color: palette(placeholder-text); font-size: 11px; }
"""


class RibbonButton(QToolButton):
    """Tool button of a ribbon action with its own short caption.

    The caption may differ from the action's text (*Lote* for *Calcular
    lote…*): :class:`QToolButton` copies the text back on every change of the
    action, so the caption is restored after each one.
    """

    def __init__(self, action: QAction, caption: str, large: bool,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ribbonButton")
        self.caption = caption
        self.setDefaultAction(action)
        self.setAutoRaise(True)
        if large:
            self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            self.setIconSize(LARGE_ICON)
        else:
            self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            self.setIconSize(SMALL_ICON)
        action.changed.connect(self._restore_caption)
        self._restore_caption()
        self.fit_caption()

    def _restore_caption(self) -> None:
        if self.text() != self.caption:
            self.setText(self.caption)

    def fit_caption(self) -> None:
        """Reserve the caption's width.

        The style sheet's border and padding are not in the size hint of
        :class:`QToolButton`, which then elides the caption.
        """
        metrics = self.fontMetrics()
        text = max(metrics.horizontalAdvance(line) for line in self.caption.split("\n"))
        menu = 14 if self.menu() is not None else 0
        if self.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonTextUnderIcon:
            width = max(text, self.iconSize().width(), 42) + 14 + menu
        else:
            width = self.iconSize().width() + 6 + text + 16 + menu
        self.setMinimumWidth(width)


class RibbonGroup(QWidget):
    """Labelled group of a ribbon tab: large buttons, then columns of small ones."""

    def __init__(self, title: str, ribbon: Ribbon, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.title = title
        self._ribbon = ribbon
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 2, 4, 0)
        outer.setSpacing(0)
        self._row = QHBoxLayout()
        self._row.setSpacing(2)
        outer.addLayout(self._row, 1)
        label = QLabel(title)
        label.setObjectName("ribbonGroupTitle")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(label)
        self._column: QVBoxLayout | None = None
        self.buttons: list[RibbonButton] = []

    def _button(self, action: QAction, caption: str | None, icon_name: str | None,
                large: bool) -> RibbonButton:
        if icon_name:
            action.setIcon(icon(icon_name))
        self._ribbon.register(action)
        button = RibbonButton(action, caption or action.text(), large, self)
        self.buttons.append(button)
        return button

    def large(self, action: QAction, caption: str | None = None,
              icon_name: str | None = None) -> RibbonButton:
        """Big button: 32 px icon with the caption below."""
        button = self._button(action, caption, icon_name, True)
        self._row.addWidget(button, 0, Qt.AlignmentFlag.AlignTop)
        self._column = None
        return button

    def small(self, action: QAction, caption: str | None = None,
              icon_name: str | None = None) -> RibbonButton:
        """Small button: 16 px icon with the caption beside, stacked three high."""
        button = self._button(action, caption, icon_name, False)
        if self._column is None or self._column.count() >= SMALL_ROWS:
            self._column = QVBoxLayout()
            self._column.setSpacing(0)
            self._column.setAlignment(Qt.AlignmentFlag.AlignTop)
            self._row.addLayout(self._column)
        self._column.addWidget(button)
        return button

    def menu(self, action: QAction, menu: QMenu, caption: str | None = None,
             icon_name: str | None = None) -> RibbonButton:
        """Big button that opens ``menu`` (for example the recent projects)."""
        button = self.large(action, caption, icon_name)
        button.setMenu(menu)
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        button.fit_caption()
        return button


class RibbonPage(QWidget):
    """One tab of the ribbon: groups side by side with a separator between them."""

    def __init__(self, title: str, ribbon: Ribbon) -> None:
        super().__init__()
        self.title = title
        self._ribbon = ribbon
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(2, 2, 2, 2)
        self._layout.setSpacing(0)
        self._layout.addStretch(1)
        self.groups: list[RibbonGroup] = []

    def group(self, title: str) -> RibbonGroup:
        if self.groups:
            line = QFrame()
            line.setFrameShape(QFrame.Shape.VLine)
            line.setFrameShadow(QFrame.Shadow.Sunken)
            self._layout.insertWidget(self._layout.count() - 1, line)
        group = RibbonGroup(title, self._ribbon, self)
        self._layout.insertWidget(self._layout.count() - 1, group)
        self.groups.append(group)
        return group


class Ribbon(QTabWidget):
    """Tab widget of command groups installed as the window's menu widget."""

    EXPANDED_HEIGHT = 112

    def __init__(self, window: QMainWindow) -> None:
        super().__init__(window)
        self._window = window
        self.setObjectName("ribbon")
        self.setDocumentMode(True)
        self.setStyleSheet(_STYLE)
        self.setFixedHeight(self.EXPANDED_HEIGHT)
        self.collapsed = False
        self.pages: list[RibbonPage] = []
        self.tabBarDoubleClicked.connect(lambda _index: self.set_collapsed(not self.collapsed))
        self.tabBarClicked.connect(self._on_tab_clicked)
        toggle = QShortcut(QKeySequence("Ctrl+F1"), window)
        toggle.activated.connect(lambda: self.set_collapsed(not self.collapsed))
        window.setMenuWidget(self)

    def add_page(self, title: str) -> RibbonPage:
        page = RibbonPage(title, self)
        self.addTab(page, title)
        self.pages.append(page)
        return page

    def page(self, title: str) -> RibbonPage:
        return next(page for page in self.pages if page.title == title)

    def register(self, action: QAction) -> None:
        """Keep the shortcut of ``action`` alive while its tab is hidden or folded."""
        if action not in self._window.actions():
            self._window.addAction(action)

    def set_collapsed(self, collapsed: bool) -> None:
        """Fold the ribbon to its tab bar, or unfold it."""
        self.collapsed = collapsed
        height = self.tabBar().sizeHint().height() if collapsed else self.EXPANDED_HEIGHT
        self.setFixedHeight(height)

    def _on_tab_clicked(self, _index: int) -> None:
        if self.collapsed:
            self.set_collapsed(False)

    def buttons(self) -> Iterator[tuple[str, str, RibbonButton]]:
        """Every button as (tab, group, button), in display order."""
        for page in self.pages:
            for group in page.groups:
                for button in group.buttons:
                    yield page.title, group.title, button

    def actions_of(self, title: str) -> list[QAction]:
        """Actions of the tab ``title`` (without repetitions)."""
        found: list[QAction] = []
        for group in self.page(title).groups:
            for button in group.buttons:
                action = button.defaultAction()
                if action not in found:
                    found.append(action)
        return found

    def find(self, caption: str) -> RibbonButton:
        """First button whose caption is ``caption``."""
        return next(button for _t, _g, button in self.buttons() if button.caption == caption)


RESULT_TABS = {
    "Resumen": ("summary", "tab.summary"),
    "Verificaciones": ("checks", "tab.details"),
    "Figuras": ("figures", "tab.figures"),
    "Geometría": ("geometry", "base.ui.geometry"),
    "3D": ("viewer", "tab.viewer"),
}
"""Results tabs: icon and help key of the button that shows each one."""


def add_result_views(window: QMainWindow, group: RibbonGroup, tabs: QTabWidget) -> None:
    """Small buttons that bring each tab of the results panel to the front."""
    for index in range(tabs.count()):
        title = tabs.tabText(index)
        icon_name, key = RESULT_TABS.get(title, ("summary", "tab.summary"))
        item = QAction(title, window)
        item.setToolTip(help_text(key))
        item.setStatusTip(help_text(key))
        widget = tabs.widget(index)
        item.triggered.connect(lambda _checked=False, w=widget: tabs.setCurrentWidget(w))
        group.small(item, title, icon_name)


def add_view_page(ribbon: Ribbon, tabs: QTabWidget, viewer) -> RibbonPage:
    """*Vista 3D* tab with the viewer's controls (they leave the viewer's own bar).

    Every command also brings the 3D tab to the front, so its effect is seen.
    """
    actions = viewer.view_actions
    for item in actions.values():
        item.triggered.connect(lambda _checked=False: tabs.setCurrentWidget(viewer))
    viewer.set_controls_visible(False)
    page = ribbon.add_page("Vista 3D")
    group = page.group("Modelo")
    group.large(actions["refresh"], "Actualizar", "refresh")
    group.large(actions["reset"], "Ajustar\nvista", "fit")
    group = page.group("Vistas")
    group.large(actions["iso"], "Iso", "iso")
    group.small(actions["front"], "Frente", "front")
    group.small(actions["top"], "Planta", "top")
    group.small(actions["side"], "Lado", "side")
    group = page.group("Opciones")
    group.large(actions["explode"], "Separar", "explode")
    group.small(actions["auto"], "Automático", "auto")
    return page
