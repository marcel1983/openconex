# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Elevation drawing of a beam-end shear connection (ezdxf, DXF R2013).

The view looks at the beam web: x runs along the beam from the face of the
support (x = 0), y is up with the bottom of the beam at y = 0. The same
:func:`shear_layout` feeds the 3D model. Model space at 1:1 in the project
length unit. Layers SC-*.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from openconex.connections.shear.check import ShearConnection, ShearType
from openconex.connections.shear.double_angle import DoubleAngle
from openconex.connections.shear.end_plate import EndPlate
from openconex.connections.shear.extended_single_plate import ExtendedSinglePlate
from openconex.connections.shear.seated import SeatedAngle
from openconex.connections.shear.single_plate import SinglePlate
from openconex.connections.shear.stiffened_seat import StiffenedSeat
from openconex.i18n import tr
from openconex.units import Kind, UnitSystem, format_value, to_internal

from .base_plate import _Sheet

__all__ = ["LAYERS", "ShearDrawing", "ShearLayout", "shear_dxf", "shear_layout",
           "write_shear_dxf"]

LAYERS = {
    "SC-VIGA": (5, "Continuous"),
    "SC-APOYO": (4, "Continuous"),
    "SC-PLACA": (1, "Continuous"),
    "SC-PERNO": (3, "Continuous"),
    "SC-SOLDADURA": (30, "Continuous"),
    "SC-COTAS": (8, "Continuous"),
    "SC-TEXTO": (7, "Continuous"),
}

INCH = to_internal(1.0, "in", Kind.LENGTH)


@dataclass(frozen=True)
class ShearDrawing:
    title: str = ""
    number: str = ""
    revision: str = "0"
    date: str = ""


@dataclass
class ShearLayout:
    """2D geometry of the elevation [mm]."""

    beam_d: float
    beam_tf: float
    beam_start: float
    """Beam end, measured from the support face."""
    beam_length: float
    support_t: float
    cope_top: tuple[float, float] | None = None
    """(c, dc) of the top cope."""
    cope_bottom: tuple[float, float] | None = None
    plates: list[tuple[float, float, float, float, str]] = field(default_factory=list)
    """Rectangles (x0, y0, x1, y1, name) of the connecting elements."""
    plate_thickness: float = 0.0
    bolts: list[tuple[float, float]] = field(default_factory=list)
    """Bolts through the beam web (x, y)."""
    support_bolts: list[float] = field(default_factory=list)
    """Heights of the bolts through the support (shown edge-on)."""
    support_bolt_end: float = 0.0
    """Thickness the support bolts go through, from the support face."""
    bolt_diameter: float = 0.0
    welds: list[tuple[float, float, float, float]] = field(default_factory=list)
    """Weld lines (x0, y0, x1, y1)."""
    two_angles: bool = False


def _web_window(conn: ShearConnection, d: float, tf: float) -> tuple[float, float]:
    top = d - tf if conn.cope is None else d - max(conn.cope.dc, tf)
    bottom = tf if conn.cope is None or not conn.cope.dc_bottom else conn.cope.dc_bottom
    return bottom, top


def _bolt_column(x: float, top: float, rows: int, spacing: float) -> list[tuple[float, float]]:
    return [(x, top - i * spacing) for i in range(rows)]


def shear_layout(conn: ShearConnection) -> ShearLayout:
    beam = conn.beam
    assert beam is not None
    d, tf = beam.d, beam.tf
    support_t = 0.0
    if conn.support is not None:
        support_t = conn.support.tf if conn.support_element == "flange" else conn.support.tw
    el = conn.element
    half = INCH / 2
    lay = ShearLayout(beam_d=d, beam_tf=tf, beam_start=half, beam_length=max(1.25 * d, 18 * INCH),
                      support_t=support_t)
    bolt = getattr(el, "bolt", None)
    if bolt is not None:
        lay.bolt_diameter = bolt.diameter
    if conn.cope is not None:
        lay.cope_top = (conn.cope.c, conn.cope.dc)
        if conn.cope.dc_bottom:
            lay.cope_bottom = (conn.cope.c, conn.cope.dc_bottom)
    bottom, top = _web_window(conn, d, tf)
    mid = (bottom + top) / 2

    if isinstance(el, (SinglePlate, ExtendedSinglePlate)):
        lines = el.lines if isinstance(el, ExtendedSinglePlate) else 1
        gage = el.gage if isinstance(el, ExtendedSinglePlate) else 0.0
        width = el.a + (lines - 1) * gage + el.leh
        y1 = mid + el.length / 2
        lay.plates.append((0.0, y1 - el.length, width, y1, "plate"))
        lay.plate_thickness = el.thickness
        for j in range(lines):
            lay.bolts += _bolt_column(el.a + j * gage, y1 - el.lev, el.rows, el.spacing)
        lay.welds.append((0.0, y1 - el.length, 0.0, y1))
        lay.beam_start = min(half, el.a - el.leh) if el.a > el.leh else half
    elif isinstance(el, DoubleAngle):
        leg = el.beam_leg or (half + INCH * 1.5 + el.leh_beam)
        y1 = mid + el.length / 2
        lay.plates.append((0.0, y1 - el.length, leg, y1, "angles"))
        lay.plate_thickness = el.thickness
        lay.two_angles = True
        if el.beam_weld > 0:
            lay.welds += [(leg, y1 - el.length, leg, y1)]
        else:
            lay.bolts += _bolt_column(leg - el.leh_beam, y1 - el.lev, el.rows, el.spacing)
        if el.support_weld > 0:
            lay.welds.append((0.0, y1 - el.length, 0.0, y1))
        else:
            lay.support_bolts = [y1 - el.lev - i * el.spacing for i in range(el.rows)]
            lay.support_bolt_end = el.thickness
    elif isinstance(el, EndPlate):
        y1 = mid + el.length / 2
        lay.plates.append((0.0, y1 - el.length, el.thickness, y1, "end_plate"))
        lay.plate_thickness = el.thickness
        lay.beam_start = el.thickness
        lay.support_bolts = [y1 - el.lev - i * el.spacing for i in range(el.rows)]
        lay.support_bolt_end = el.thickness
        lay.welds.append((el.thickness, y1 - el.length + el.weld, el.thickness, y1 - el.weld))
    elif isinstance(el, SeatedAngle):
        t = el.thickness
        lay.beam_start = el.setback - INCH / 4
        lay.plates += [(0.0, -t, el.leg, 0.0, "seat"),
                       (0.0, -(el.vertical_leg or el.leg + 2 * INCH), t, -t, "seat")]
        lay.plate_thickness = el.length
        if el.support_weld > 0:
            lay.welds.append((0.0, -(el.vertical_leg or el.leg), 0.0, 0.0))
        else:
            lay.support_bolts = [-t - 1.5 * INCH] if el.bolts <= 2 else [
                -t - 1.5 * INCH, -t - 4.5 * INCH]
            lay.support_bolt_end = t
    elif isinstance(el, StiffenedSeat):
        seat = 3 * INCH / 8
        lay.beam_start = el.setback
        lay.plates += [(0.0, -seat, el.width, 0.0, "seat"),
                       (0.0, -seat - el.length, el.width, -seat, "stiffener")]
        lay.plate_thickness = el.thickness
        lay.welds.append((0.0, -seat - el.length, 0.0, 0.0))
    return lay


def _draw(s: _Sheet, conn: ShearConnection, lay: ShearLayout, opt: ShearDrawing,
          lang: str) -> None:
    u = s.u
    d, tf, x0, xl = u(lay.beam_d), u(lay.beam_tf), u(lay.beam_start), u(lay.beam_length)
    ys = [y for p in lay.plates for y in (p[1], p[3])] + [0.0, lay.beam_d]
    lo, hi = u(min(ys)) - u(4 * INCH), u(max(ys)) + u(4 * INCH)
    # support
    st = max(u(lay.support_t), u(INCH / 2))
    s.rect(-st, lo, 0.0, hi, "SC-APOYO")
    # beam outline with copes
    top_c = lay.cope_top
    bot_c = lay.cope_bottom
    xe = x0 + xl
    pts = []
    if bot_c:
        c, dc = u(bot_c[0]), u(bot_c[1])
        pts += [(x0 + c, 0.0), (x0 + c, dc), (x0, dc)]
    else:
        pts += [(x0, 0.0)]
    if top_c:
        c, dc = u(top_c[0]), u(top_c[1])
        pts += [(x0, d - dc), (x0 + c, d - dc), (x0 + c, d)]
    else:
        pts += [(x0, d)]
    pts += [(xe, d), (xe, 0.0)]
    s.msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": "SC-VIGA"})
    for y in (tf, d - tf):
        start = x0 + (u(top_c[0]) if top_c and y > d / 2 else 0.0)
        start = start if not (bot_c and y < d / 2) else x0 + u(bot_c[0])
        s.msp.add_line((start, y), (xe, y), dxfattribs={"layer": "SC-VIGA"})
    # elements
    for x_0, y_0, x_1, y_1, _ in lay.plates:
        s.rect(u(x_0), u(y_0), u(x_1), u(y_1), "SC-PLACA")
    r = u(lay.bolt_diameter) / 2 if lay.bolt_diameter else u(INCH * 0.375)
    for x, y in lay.bolts:
        s.msp.add_circle((u(x), u(y)), r, dxfattribs={"layer": "SC-PERNO"})
    for y in lay.support_bolts:
        s.msp.add_line((-st - 2 * r, u(y)), (u(lay.support_bolt_end) + 2 * r, u(y)),
                       dxfattribs={"layer": "SC-PERNO"})
    for x_0, y_0, x_1, y_1 in lay.welds:
        s.msp.add_line((u(x_0), u(y_0)), (u(x_1), u(y_1)),
                       dxfattribs={"layer": "SC-SOLDADURA", "lineweight": 70})
    # dimensions
    if lay.plates:
        x_0, y_0, x_1, y_1, _ = lay.plates[0]
        s.vdim(u(y_0), u(y_1), u(x_1), u(x_1) + 3 * s.text_h)
        s.hdim(u(x_0), u(x_1), u(y_0), u(y_0) - 3 * s.text_h)
    if len(lay.bolts) > 1:
        xs = sorted({x for x, _ in lay.bolts})
        col = sorted(y for x, y in lay.bolts if x == xs[0])
        s.vdim(u(col[0]), u(col[-1]), u(xs[0]), u(xs[0]) - 6 * s.text_h)
    if top_c:
        s.hdim(x0, x0 + u(top_c[0]), d, d + 3 * s.text_h)
        s.vdim(d - u(top_c[1]), d, x0 + u(top_c[0]), x0 + u(top_c[0]) + 3 * s.text_h)
    # notes and title
    s.text(tr("drawing.elevation", lang), -st, hi + 2 * s.text_h, height=1.4 * s.text_h,
           layer="SC-TEXTO")
    lines = [tr(f"shear.type.{conn.type.value}", lang)]
    if conn.beam is not None:
        lines.append(f"{tr('input.beam', lang)}: {conn.beam.name}")
    if conn.support is not None:
        lines.append(f"{tr('input.support', lang)}: {conn.support.name} "
                     f"({tr(f'input.support_{conn.support_element}', lang)})")
    for line in _description(conn, s, lang):
        lines.append(line)
    y = lo - 3 * s.text_h
    for line in lines:
        s.text(line, -st, y, layer="SC-TEXTO")
        y -= 1.6 * s.text_h
    title = " · ".join(v for v in (opt.title, opt.number, f"Rev. {opt.revision}", opt.date) if v)
    if title:
        s.text(title, -st, y - s.text_h, height=1.2 * s.text_h, layer="SC-TEXTO")


def _description(conn: ShearConnection, s: _Sheet, lang: str) -> list[str]:
    el = conn.element
    q = s.label
    out = []
    bolt = getattr(el, "bolt", None)
    if bolt is not None and conn.type is not ShearType.STIFFENED_SEAT:
        count = {ShearType.END_PLATE: 2 * getattr(el, "rows", 0),
                 ShearType.SEATED: getattr(el, "bolts", 0)}.get(
            conn.type, getattr(el, "rows", 0) * getattr(el, "lines", 1))
        if not (isinstance(el, DoubleAngle) and el.beam_weld and el.support_weld) and not (
                isinstance(el, SeatedAngle) and el.support_weld):
            out.append(f"{tr('input.bolts', lang)}: {count} × Ø {q(bolt.diameter)} "
                       f"{bolt.grade}")
    thickness = getattr(el, "thickness", None)
    length = getattr(el, "length", None)
    if thickness and length:
        out.append(f"{tr('input.thickness', lang)} {q(thickness)} · "
                   f"{tr('input.length', lang)} {q(length)}")
    for key in ("weld", "support_weld", "beam_weld"):
        value = getattr(el, key, 0.0)
        if value:
            out.append(f"{tr(f'input.{key}', lang)}: {q(value)}")
    return out


def shear_dxf(conn: ShearConnection, units: UnitSystem, lang: str = "es",
              options: ShearDrawing | None = None):
    """DXF document with the elevation of the connection."""
    s = _Sheet(units, lang)
    for name, (color, ltype) in LAYERS.items():
        if name not in s.doc.layers:
            s.doc.layers.add(name, color=color, linetype=ltype)
    lay = shear_layout(conn)
    s.setup_dims(s.u(max(lay.beam_d, 300.0)) / 60)
    _draw(s, conn, lay, options or ShearDrawing(), lang)
    return s.doc


def write_shear_dxf(conn: ShearConnection, path: str | Path, units: UnitSystem,
                    lang: str = "es", options: ShearDrawing | None = None) -> Path:
    path = Path(path)
    shear_dxf(conn, units, lang, options).saveas(path)
    return path


def length_text(value: float, units: UnitSystem) -> str:
    return format_value(value, Kind.LENGTH, units, 4)
