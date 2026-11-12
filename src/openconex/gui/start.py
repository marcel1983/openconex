# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Visual connection gallery shown before a new project is created.

The gallery is a thin UI layer over the existing base-plate and shear editors.
It never calculates: it only builds a starter :class:`Project` and hands it to
the caller.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from openconex.gui.start_data import FAMILIES, Family, Subtype, build_project
from openconex.io.project import Project

DATA_PACKAGE = "openconex.data"


@dataclass
class StartSelection:
    kind: str
    """``base_plate``, ``shear`` or ``open``."""
    project: Project | None = None
    path: Path | None = None


def connection_pixmap(asset: str, size: QSize) -> QPixmap:
    """Load a packaged thumbnail: a 3D PNG if present, otherwise the SVG."""
    try:
        png = resources.files(DATA_PACKAGE).joinpath(
            "connections", "thumbs", f"{asset}.png")
        if png.is_file():
            with resources.as_file(png) as file_path:
                pixmap = QPixmap(str(file_path))
            if not pixmap.isNull():
                return pixmap.scaled(size, Qt.AspectRatioMode.KeepAspectRatio,
                                     Qt.TransformationMode.SmoothTransformation)
    except (FileNotFoundError, OSError):
        pass
    pixmap = QPixmap(size)
    pixmap.fill(Qt.GlobalColor.transparent)
    try:
        path = resources.files(DATA_PACKAGE).joinpath("connections", f"{asset}.svg")
        with resources.as_file(path) as file_path:
            renderer = QSvgRenderer(str(file_path))
            painter = QPainter(pixmap)
            try:
                renderer.render(painter)
            finally:
                painter.end()
    except (FileNotFoundError, OSError):
        pass
    return pixmap


class ConnectionCard(QFrame):
    """Clickable card with an isometric image, title and description."""

    clicked = Signal()

    def __init__(self, title: str, description: str, asset: str, *,
                 enabled: bool = True, badge: str = "",
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._enabled = enabled
        self.setObjectName("connectionCard")
        self.setProperty("disabled", not enabled)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFixedSize(252, 268)
        self.setCursor(Qt.CursorShape.PointingHandCursor if enabled
                       else Qt.CursorShape.ForbiddenCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)
        image = QLabel()
        image.setObjectName("cardImage")
        image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image.setPixmap(connection_pixmap(asset, QSize(228, 132)))
        layout.addWidget(image)

        heading = QHBoxLayout()
        heading.setSpacing(6)
        title_label = QLabel(title)
        title_label.setObjectName("cardTitle")
        title_label.setWordWrap(True)
        heading.addWidget(title_label, 1)
        if badge:
            badge_label = QLabel(badge)
            badge_label.setObjectName("cardBadge")
            heading.addWidget(badge_label, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(heading)

        text = QLabel(description)
        text.setObjectName("cardText")
        text.setWordWrap(True)
        text.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(text, 1)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._enabled and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class ConnectionStartDialog(QDialog):
    """Two-step visual gallery: family, then connection subtype."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.selection: StartSelection | None = None
        self.setWindowTitle("OpenConex — Nueva conexión")
        self.setModal(True)
        self.resize(1120, 760)
        self.setMinimumSize(900, 620)
        self.setStyleSheet(_STYLE)
        self._family: Family | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("¿Qué quieres calcular?")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Elija una familia y después el tipo de conexión. "
                          "Los campos se adaptan al tipo elegido.")
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)
        header_text = QVBoxLayout()
        header_text.addWidget(title)
        header_text.addWidget(subtitle)
        header.addLayout(header_text)
        header.addStretch(1)
        layout.addLayout(header)

        self._stack = QStackedWidget()
        self._family_page = self._build_family_page()
        self._subtype_content = QWidget()
        self._subtype_layout = QVBoxLayout(self._subtype_content)
        self._subtype_layout.setContentsMargins(0, 0, 0, 0)
        self._subtype_scroll = QScrollArea()
        self._subtype_scroll.setWidgetResizable(True)
        self._subtype_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._subtype_scroll.setWidget(self._subtype_content)
        self._stack.addWidget(self._family_page)
        self._stack.addWidget(self._subtype_scroll)
        layout.addWidget(self._stack, 1)

        footer = QHBoxLayout()
        open_button = QPushButton("Abrir proyecto…")
        open_button.setObjectName("secondary")
        open_button.clicked.connect(self._open_project)
        footer.addWidget(open_button)
        footer.addStretch(1)
        cancel = QPushButton("Salir")
        cancel.setObjectName("secondary")
        cancel.clicked.connect(self.reject)
        footer.addWidget(cancel)
        layout.addLayout(footer)

    def _build_family_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        grid = QGridLayout()
        grid.setSpacing(14)
        for index, family in enumerate(FAMILIES):
            card = ConnectionCard(family.label, family.description, family.asset,
                                  enabled=family.enabled, badge=family.badge)
            if family.enabled:
                card.clicked.connect(lambda f=family: self._show_family(f))
            grid.addWidget(card, index // 3, index % 3,
                           Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        layout.addLayout(grid)
        layout.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(page)
        return scroll

    def _show_family(self, family: Family) -> None:
        self._family = family
        while self._subtype_layout.count():
            item = self._subtype_layout.takeAt(0)
            widget = None if item is None else item.widget()
            if widget is not None:
                widget.deleteLater()
        top = QHBoxLayout()
        back = QPushButton("← Volver")
        back.setObjectName("secondary")
        back.clicked.connect(lambda: self._stack.setCurrentIndex(0))
        top.addWidget(back)
        title = QLabel(family.label)
        title.setObjectName("sectionTitle")
        top.addWidget(title)
        top.addStretch(1)
        self._subtype_layout.addLayout(top)
        description = QLabel(family.description)
        description.setObjectName("pageSubtitle")
        description.setWordWrap(True)
        self._subtype_layout.addWidget(description)
        grid = QGridLayout()
        grid.setSpacing(14)
        for index, subtype in enumerate(family.subtypes):
            card = ConnectionCard(subtype.label, subtype.description, subtype.asset)
            card.clicked.connect(lambda s=subtype: self._select_subtype(s))
            grid.addWidget(card, index // 3, index % 3,
                           Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._subtype_layout.addLayout(grid)
        self._subtype_layout.addStretch(1)
        self._stack.setCurrentIndex(1)

    def _select_subtype(self, subtype: Subtype) -> None:
        if self._family is None:
            return
        try:
            project = build_project(self._family.id, subtype.id)
        except Exception as exc:
            QMessageBox.critical(self, "No se pudo crear el proyecto", str(exc))
            return
        kind = "base_plate" if self._family.id == "base_plate" else "shear"
        self.selection = StartSelection(kind=kind, project=project)
        self.accept()

    def _open_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Abrir proyecto", "",
                                               "OpenConex (*.ocnx);;Todos (*)")
        if path:
            self.selection = StartSelection(kind="open", path=Path(path))
            self.accept()


_STYLE = """
QDialog { background: #f4f7fb; }
QLabel#pageTitle { font-size: 22px; font-weight: 600; color: #172b3a; }
QLabel#pageSubtitle { font-size: 12px; color: #5d6d7e; }
QLabel#sectionTitle { font-size: 18px; font-weight: 600; color: #172b3a; }
QFrame#connectionCard {
    background: #ffffff;
    border: 1px solid #d6dee8;
    border-radius: 10px;
}
QFrame#connectionCard:hover {
    background: #f7fbff;
    border: 2px solid #1565c0;
}
QFrame#connectionCard[disabled="true"] {
    background: #f0f2f4;
    border-color: #e0e4e8;
}
QLabel#cardImage { background: #fafafa; border-radius: 6px; }
QLabel#cardTitle { font-size: 14px; font-weight: 600; color: #1f2d3d; }
QLabel#cardText { font-size: 11px; color: #5d6d7e; }
QLabel#cardBadge {
    font-size: 9px; font-weight: 700; color: #b26a00;
    background: #fff3e0; border-radius: 4px; padding: 1px 5px;
}
QPushButton#secondary {
    background: #ffffff; border: 1px solid #c7d1dd; border-radius: 5px;
    padding: 6px 14px; color: #1f2d3d;
}
QPushButton#secondary:hover { border-color: #1565c0; color: #1565c0; }
"""
