# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Figures for the calculation report, generated from the drawing model."""

from __future__ import annotations

from dataclasses import dataclass

from openconex.connections.base_plate.check import BasePlate
from openconex.drawing.base_plate import BasePlateDrawing, base_plate_dxf
from openconex.i18n import tr
from openconex.io.project import Project
from openconex.units import Kind, UnitSystem

__all__ = ["Figure", "base_plate_figures", "dxf_to_svg"]


@dataclass(frozen=True)
class Figure:
    key: str
    caption: str
    svg: str
    png: bytes | None = None


def dxf_to_svg(doc, width: float = 210, height: float = 150) -> str:
    """Render one DXF document to a standalone SVG string."""
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.layout import Page
    from ezdxf.addons.drawing.svg import SVGBackend

    backend = SVGBackend()
    Frontend(RenderContext(doc), backend).draw_layout(doc.modelspace())
    return backend.get_string(Page(width, height))


def _options(project: Project) -> BasePlateDrawing:
    bp = project.base_plate
    L = Kind.LENGTH

    def q(value):
        return None if value is None else project.quantity(value, L)

    info = project.info
    return BasePlateDrawing(
        pedestal_N=q(bp.pedestal_N), pedestal_B=q(bp.pedestal_B), grout=q(bp.grout),
        title=info.name, number=info.number, revision=info.revision, date=info.date)


def base_plate_figures(project: Project, bp: BasePlate, lang: str,
                       units: UnitSystem) -> list[Figure]:
    """Plan and elevation figures rendered from the same DXF as the report drawing."""
    options = _options(project)
    figures = []
    for key, view in (("plan", "plan"), ("elevation", "elevation")):
        doc = base_plate_dxf(bp, units, lang, options, view=view)
        figures.append(Figure(
            key=key,
            caption=tr(f"report.figure_{key}", lang),
            svg=dxf_to_svg(doc)))
    return figures
