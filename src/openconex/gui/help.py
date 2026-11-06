# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Searchable help dialog for the shear-connection window."""

from __future__ import annotations

import html

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
)

from openconex.help import HELP_ITEMS, HelpItem

__all__ = ["HelpDialog"]


class HelpDialog(QDialog):
    """List of fields, menus or checks with a detail pane and a search box."""

    def __init__(self, section: str = "all", parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ayuda de OpenConex")
        self.resize(980, 620)
        self.section = section
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Busque un campo, menú o verificación. Cada entrada explica qué es, "
            "cómo se usa y cómo afecta al cálculo."))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar…")
        self.search.textChanged.connect(self._filter)
        layout.addWidget(self.search)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.list = QListWidget()
        self.list.currentItemChanged.connect(self._show)
        self.detail = QTextBrowser()
        splitter.addWidget(self.list)
        splitter.addWidget(self.detail)
        splitter.setSizes([300, 680])
        layout.addWidget(splitter, 1)
        self._filter("")

    def _section_items(self) -> list[HelpItem]:
        items = list(HELP_ITEMS.values())
        if self.section == "fields":
            return [item for item in items if item.group not in
                    ("Menú Archivo", "Menú Cálculo", "Menú Exportar", "Menú Ayuda",
                     "Acciones", "Controles", "Verificaciones")]
        if self.section == "menus":
            return [item for item in items if item.group in
                    ("Menú Archivo", "Menú Cálculo", "Menú Exportar", "Menú Principal",
                     "Menú Ayuda", "Acciones", "Controles", "Diálogos")]
        if self.section == "checks":
            return [item for item in items if item.group == "Verificaciones"]
        return items

    def _filter(self, text: str) -> None:
        needle = text.strip().lower()
        self.list.clear()
        for item in self._section_items():
            haystack = " ".join((item.key, item.label, item.what, item.how,
                                 item.effect)).lower()
            if needle and needle not in haystack:
                continue
            entry = QListWidgetItem(f"{item.label}  ·  {item.group}")
            entry.setData(Qt.ItemDataRole.UserRole, item.key)
            self.list.addItem(entry)
        if self.list.count():
            self.list.setCurrentRow(0)
        else:
            self.detail.setHtml("<p>No hay coincidencias.</p>")

    def _show(self, current: QListWidgetItem | None) -> None:
        if current is None:
            return
        item = HELP_ITEMS[current.data(Qt.ItemDataRole.UserRole)]
        self.detail.setHtml(
            f"<h2>{html.escape(item.label)}</h2>"
            f"<p><code>{html.escape(item.key)}</code></p>"
            f"<p><b>Qué es:</b> {html.escape(item.what)}</p>"
            f"<p><b>Cómo se usa:</b> {html.escape(item.how)}</p>"
            f"<p><b>Efecto en el cálculo:</b> {html.escape(item.effect)}</p>"
            f"<p><b>Valor por defecto:</b> {html.escape(item.default)}<br>"
            f"<b>Tipos:</b> {html.escape(item.types)}</p>")
