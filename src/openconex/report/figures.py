# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Figures for the calculation report, generated from the drawing model."""

from __future__ import annotations

import base64
from dataclasses import dataclass

from openconex.connections.base_plate.check import BasePlate
from openconex.drawing.base_plate import BasePlateDrawing, base_plate_dxf
from openconex.drawing.embedded_base import embedded_base_dxf
from openconex.geometry3d.base_plate import (
    base_plate_parts,
    embedded_base_parts,
    isometric_svg,
    occ_available,
)
from openconex.i18n import tr
from openconex.io.project import Project
from openconex.units import Kind, UnitSystem

__all__ = ["Figure", "base_plate_figures", "dxf_to_svg", "svg_to_png"]


@dataclass(frozen=True)
class Figure:
    key: str
    caption: str
    svg: str
    png: bytes | None = None

    @property
    def data_uri(self) -> str:
        encoded = base64.b64encode(self.svg.encode("utf-8")).decode("ascii")
        return f"data:image/svg+xml;base64,{encoded}"


def dxf_to_svg(doc, width: float = 210, height: float = 150) -> str:
    """Render one DXF document to a standalone SVG string."""
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.layout import Page
    from ezdxf.addons.drawing.svg import SVGBackend

    backend = SVGBackend()
    Frontend(RenderContext(doc), backend).draw_layout(doc.modelspace())
    svg = backend.get_string(Page(width, height))
    # ezdxf uses a dark model-space background; reports are printed on white.
    return svg.replace('fill="#212830"', 'fill="#ffffff"')


def svg_to_png(svg: str, width: int = 1600) -> bytes | None:
    """Rasterize an SVG to PNG for DOCX; returns None if QtSvg is unavailable."""
    try:
        from PySide6.QtCore import QBuffer, QByteArray, QIODevice
        from PySide6.QtGui import QColor, QImage, QPainter
        from PySide6.QtSvg import QSvgRenderer
    except ImportError:
        return None
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    if not renderer.isValid():
        return None
    size = renderer.defaultSize()
    height = max(1, round(width * size.height() / max(size.width(), 1)))
    image = QImage(width, height, QImage.Format_ARGB32)
    image.fill(QColor("white"))
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    buffer = QBuffer()
    buffer.open(QIODevice.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data())


def _options(project: Project) -> BasePlateDrawing:
    bp = project.base_plate
    L = Kind.LENGTH

    def q(value):
        return None if value is None else project.quantity(value, L)

    info = project.info
    return BasePlateDrawing(
        pedestal_N=q(bp.pedestal_N), pedestal_B=q(bp.pedestal_B), grout=q(bp.grout),
        title=info.name, number=info.number, revision=info.revision, date=info.date)


def _add_isometric(figures: list[Figure], parts, lang: str) -> None:
    svg = isometric_svg(parts)
    if svg:
        figures.append(Figure("isometric", tr("report.figure_isometric", lang), svg,
                              png=svg_to_png(svg)))


def base_plate_figures(project: Project, bp: BasePlate, lang: str,
                       units: UnitSystem) -> list[Figure]:
    """Plan, elevation and isometric figures of the connection."""
    options = _options(project)
    embedded = bp.embedded_base
    figures = []
    for key, view in (("plan", "plan"), ("elevation", "elevation")):
        doc = (embedded_base_dxf(bp, units, lang, options, view=view)
               if embedded is not None else
               base_plate_dxf(bp, units, lang, options, view=view))
        svg = dxf_to_svg(doc)
        figures.append(Figure(
            key=key,
            caption=tr(f"report.figure_{key}", lang),
            svg=svg, png=svg_to_png(svg)))
    if occ_available():
        if embedded is not None:
            parts = embedded_base_parts(bp, options.pedestal_B)
        else:
            parts = base_plate_parts(bp, options.grout, options.pedestal_N,
                                     options.pedestal_B)
        _add_isometric(figures, parts, lang)
    return figures
