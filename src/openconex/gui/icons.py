# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
# ruff: noqa: E501  (SVG path data reads better on one line per shape)
"""Icons of the ribbon, drawn for OpenConex as small SVG line drawings.

Every icon is a 24 × 24 drawing in two colors: ``{fg}`` (the outline, taken
from the palette so it reads in light and dark themes) and ``{ac}`` (the
accent). :func:`icon` renders it with :class:`QSvgRenderer` into pixmaps, so
no Qt image plugin is needed in the portable builds.
"""

from __future__ import annotations

from functools import cache

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPalette, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

__all__ = ["ICONS", "icon", "svg"]

ACCENT = "#2f7bd6"
"""Accent of the icons: the blue of the OpenConex brand."""

_S = 'fill="none" stroke="{fg}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"'
_A = 'fill="none" stroke="{ac}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"'
_F = 'fill="{ac}" stroke="none"'


def _doc(label: str) -> str:
    """Sheet with a folded corner and a short label (PDF, DOC, HTML…)."""
    return (f'<path {_S} d="M6 2.5h8.5L19 7v14.5H6z M14.5 2.5V7H19"/>'
            f'<rect x="2.5" y="11" width="15" height="7" rx="1" {_F}/>'
            f'<text x="10" y="16.6" font-family="sans-serif" font-size="5.6" '
            f'font-weight="bold" fill="#ffffff" text-anchor="middle">{label}</text>')


ICONS: dict[str, str] = {
    # -- project ----------------------------------------------------------------
    "new": f'<path {_S} d="M6 2.5h8.5L19 7v14.5H6z M14.5 2.5V7H19"/>'
           f'<path {_A} d="M12.5 11v7 M9 14.5h7"/>',
    "open": f'<path {_S} d="M2.5 6.5V19a1 1 0 0 0 1 1h15l3-9H7l-3 9 M2.5 6.5V5a1 1 0 0 1 1-1h5l2 2h8'
            f'a1 1 0 0 1 1 1v4"/>',
    "recent": f'<circle cx="12" cy="12" r="9" {_S}/><path {_A} d="M12 7v5l3.5 2"/>',
    "save": f'<path {_S} d="M4 3.5h13l3 3V20a.5.5 0 0 1-.5.5h-15A.5.5 0 0 1 4 20z'
            f' M7.5 3.5v5h8v-5"/><rect x="7.5" y="13" width="9" height="7.5" {_F}/>',
    "save_as": f'<path {_S} d="M4 3.5h13l3 3V11 M4 3.5V20.5h7 M7.5 3.5v5h8v-5"/>'
               f'<path {_A} d="M13 21l1-3.5 6-6 2.5 2.5-6 6z"/>',
    "import_csi": f'<rect x="3" y="3" width="18" height="18" rx="1.5" {_S}/>'
                  f'<path {_S} d="M3 9h18 M9 9v12"/><path {_A} d="M15 12v6 M12.5 15.5 15 18l2.5-2.5"/>',
    "import_table": f'<rect x="3" y="3" width="18" height="18" rx="1.5" {_S}/>'
                    f'<path {_S} d="M3 9h18 M3 15h18 M9 3v18 M15 3v18"/>'
                    f'<rect x="3" y="3" width="18" height="6" {_F} opacity=".55"/>',
    "exit": f'<path {_S} d="M14 4H5v16h9"/><path {_A} d="M10 12h11 M17.5 8.5 21 12l-3.5 3.5"/>',
    # -- calculation ------------------------------------------------------------
    "calculate": f'<circle cx="12" cy="12" r="9.5" {_S}/><path {_F} d="M9.5 7.5v9l7.5-4.5z"/>',
    "optimize": f'<circle cx="12" cy="12" r="8.5" {_S}/><circle cx="12" cy="12" r="4.5" {_S}/>'
                f'<circle cx="12" cy="12" r="1.8" {_F}/><path {_S} d="M12 1.5v3 M12 19.5v3 '
                f'M1.5 12h3 M19.5 12h3"/>',
    "optimize_global": f'<circle cx="12" cy="12" r="9" {_S}/><path {_S} d="M3 12h18 M12 3c3 3 3 15 0 18'
                       f' M12 3c-3 3-3 15 0 18"/><path {_A} d="M15 15l4 4 M19 15v4h-4"/>',
    "batch": f'<path {_S} d="M8 2.5h10v14 M5.5 5h10v14"/>'
             f'<rect x="3" y="7.5" width="10" height="14" rx=".5" {_S}/>'
             f'<path {_A} d="M5.5 14.5l2 2 3.5-4"/>',
    # -- results ----------------------------------------------------------------
    "summary": f'<rect x="3" y="3.5" width="18" height="17" rx="1.5" {_S}/>'
               f'<path {_S} d="M7 8.5h10 M7 12h10 M7 15.5h6"/>',
    "checks": f'<path {_S} d="M10 6h11 M10 12h11 M10 18h11"/>'
              f'<path {_A} d="M3 6l1.5 1.5L7 5 M3 12l1.5 1.5L7 11 M3 18l1.5 1.5L7 17"/>',
    "figures": f'<rect x="3" y="4" width="18" height="16" rx="1.5" {_S}/>'
               f'<path {_A} d="M5.5 17l4.5-6 3.5 4 2.5-3 3 5"/><circle cx="16" cy="8.5" r="1.5" {_F}/>',
    "geometry": f'<rect x="7" y="7" width="10" height="10" {_S}/>'
                f'<path {_A} d="M7 3.5h10 M7 2.5v2 M17 2.5v2 M20.5 7v10 M19.5 7h2 M19.5 17h2"/>',
    "viewer": f'<path {_S} d="M12 2.5l8.5 4.75v9.5L12 21.5l-8.5-4.75v-9.5z M3.5 7.25 12 12l8.5-4.75'
              f' M12 12v9.5"/><path {_F} opacity=".5" d="M12 12l8.5-4.75v9.5L12 21.5z"/>',
    # -- exports ----------------------------------------------------------------
    "pdf": _doc("PDF"),
    "docx": _doc("DOC"),
    "html": _doc("HTML").replace('font-size="5.6"', 'font-size="4.6"'),
    "dxf": f'<rect x="2.5" y="4" width="19" height="16" rx="1" {_S}/>'
           f'<path {_A} d="M6 16V8h5v4h7v4z"/><path {_S} d="M6 18h12 M6 17v2 M18 17v2"/>',
    "step": f'<path {_S} d="M12 2.5l8.5 4.75v9.5L12 21.5l-8.5-4.75v-9.5z M3.5 7.25 12 12l8.5-4.75'
            f' M12 12v9.5"/><path {_F} opacity=".85" d="M3.5 7.25 12 2.5l8.5 4.75L12 12z"/>',
    "stl": f'<path {_S} d="M12 2.5l8.5 4.75v9.5L12 21.5l-8.5-4.75v-9.5z M3.5 7.25 12 12l8.5-4.75'
           f' M12 12v9.5"/><path {_A} d="M3.5 7.25 20.5 16.75 M12 2.5v9.5 M3.5 16.75 12 12"/>',
    # -- connections and libraries -------------------------------------------------
    "gallery": f'<rect x="3" y="3" width="7.5" height="7.5" rx="1" {_S}/>'
               f'<rect x="13.5" y="3" width="7.5" height="7.5" rx="1" {_S}/>'
               f'<rect x="3" y="13.5" width="7.5" height="7.5" rx="1" {_S}/>'
               f'<path {_A} d="M17.25 13.5v7.5 M13.5 17.25H21"/>',
    "base_plate": f'<path {_S} d="M8 2.5h8 M8 13.5h8 M12 2.5v11"/>'
                  f'<rect x="3" y="13.5" width="18" height="2.5" {_F}/>'
                  f'<path {_S} d="M6 16v6 M18 16v6 M2 22h20" stroke-dasharray="0"/>',
    "shear": f'<path {_S} d="M3 2.5v19 M7 2.5v19 M3 2.5h4 M3 21.5h4 M7 10h14 M7 14h14"/>'
             f'<rect x="7" y="8" width="5" height="8" {_F} opacity=".8"/>'
             f'<circle cx="10.5" cy="10.5" r=".9" fill="#ffffff"/><circle cx="10.5" cy="13.5" r=".9" '
             f'fill="#ffffff"/>',
    "moment": f'<path {_S} d="M3 2.5v19 M7 2.5v19 M7 8h14 M7 16h14"/>'
              f'<rect x="7" y="5" width="2.5" height="14" {_F}/>'
              f'<path {_A} d="M13 12a4 4 0 1 1 4 4"/><path {_A} d="M16 14.5l1 1.5-1.6.8"/>',
    "splice": f'<path {_S} d="M2 8h9 M2 16h9 M13 8h9 M13 16h9 M11 8v8 M13 8v8"/>'
              f'<rect x="7" y="5.5" width="10" height="2.5" {_F}/>'
              f'<rect x="7" y="16" width="10" height="2.5" {_F}/>',
    "sections": f'<path {_S} d="M5 3.5h14 M5 20.5h14 M12 3.5v17"/>'
                f'<path {_A} d="M5 3.5h14v2.5H5z M5 18h14v2.5H5z"/>',
    "materials": f'<path {_S} d="M12 3 21 7.5 12 12 3 7.5z M3 12l9 4.5 9-4.5"/>'
                 f'<path {_A} d="M3 16.5l9 4.5 9-4.5"/>',
    # -- 3D view ------------------------------------------------------------------
    "refresh": f'<path {_S} d="M20 12a8 8 0 1 1-2.35-5.65"/><path {_A} d="M20.5 3.5v5h-5"/>',
    "fit": f'<path {_S} d="M3 8V3h5 M16 3h5v5 M21 16v5h-5 M8 21H3v-5"/>'
           f'<rect x="8" y="8" width="8" height="8" {_F} opacity=".8"/>',
    "iso": f'<path {_S} d="M12 2.5l8.5 4.75v9.5L12 21.5l-8.5-4.75v-9.5z M3.5 7.25 12 12l8.5-4.75'
           f' M12 12v9.5"/>',
    "front": f'<rect x="4" y="4" width="16" height="16" {_S}/><path {_F} d="M4 4h16v16H4z" opacity=".3"/>'
             f'<path {_A} d="M12 9v6 M9 12h6"/>',
    "top": f'<rect x="4" y="4" width="16" height="16" {_S}/><path {_A} d="M4 12h16 M12 4v16"/>'
           f'<circle cx="12" cy="12" r="2.5" {_F}/>',
    "side": f'<rect x="4" y="4" width="16" height="16" {_S}/><path {_F} d="M14 4h6v16h-6z" opacity=".55"/>',
    "explode": f'<rect x="2.5" y="9" width="7" height="7" {_S}/><rect x="14.5" y="9" width="7" '
               f'height="7" {_S}/><path {_A} d="M10.5 12.5h3 M6 6V3 M18 6V3"/>',
    "auto": f'<path {_F} d="M13 2 5 13.5h6L10 22l9-12h-6z"/>',
    # -- units and help --------------------------------------------------------------
    "units": f'<rect x="2" y="8" width="20" height="8" rx="1" {_S}/>'
             f'<path {_A} d="M6 8v3 M10 8v4.5 M14 8v3 M18 8v4.5"/>',
    "units_config": f'<path {_S} d="M4 6h16 M4 12h16 M4 18h16"/><circle cx="9" cy="6" r="2" {_F}/>'
                    f'<circle cx="15" cy="12" r="2" {_F}/><circle cx="7" cy="18" r="2" {_F}/>',
    "guide": f'<circle cx="12" cy="12" r="9" {_S}/><circle cx="12" cy="12" r="4" {_S}/>'
             f'<path {_A} d="M5.6 5.6l3.6 3.6 M18.4 5.6l-3.6 3.6 M5.6 18.4l3.6-3.6 M18.4 18.4l-3.6-3.6"/>',
    "help_fields": f'<rect x="3" y="3.5" width="18" height="17" rx="1.5" {_S}/>'
                   f'<path {_S} d="M10 8.5h7 M10 12h7 M10 15.5h7"/>'
                   f'<circle cx="6.5" cy="8.5" r="1.2" {_F}/><circle cx="6.5" cy="12" r="1.2" {_F}/>'
                   f'<circle cx="6.5" cy="15.5" r="1.2" {_F}/>',
    "help_menus": f'<rect x="3" y="3.5" width="18" height="17" rx="1.5" {_S}/>'
                  f'<path {_S} d="M3 8h18"/><path {_A} d="M7 12h6 M7 15.5h9"/>',
    "help_checks": f'<path {_S} d="M6 2.5h8.5L19 7v14.5H6z M14.5 2.5V7H19"/>'
                   f'<path {_A} d="M9 14l2.2 2.2L16 11.5"/>',
    "about": f'<circle cx="12" cy="12" r="9.5" {_S}/><path {_A} d="M12 11v6"/>'
             f'<circle cx="12" cy="7.5" r="1.2" {_F}/>',
}


def svg(name: str, fg: str = "#33414f", ac: str = ACCENT) -> str:
    """SVG document of the icon ``name`` with the given colors."""
    body = ICONS[name].replace("{fg}", fg).replace("{ac}", ac)
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
            f'width="24" height="24">{body}</svg>')


def _foreground() -> str:
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        return "#33414f"
    color = app.palette().color(QPalette.ColorRole.WindowText)
    return QColor(color).name()


@cache
def _icon(name: str, fg: str) -> QIcon:
    renderer = QSvgRenderer(QByteArray(svg(name, fg).encode("utf-8")))
    result = QIcon()
    for size in (16, 20, 24, 32, 48, 64):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer.render(painter, QRectF(0, 0, size, size))
        painter.end()
        result.addPixmap(pixmap)
    return result


def icon(name: str) -> QIcon:
    """Icon ``name`` of :data:`ICONS`, outlined in the palette's text color."""
    return _icon(name, _foreground())
