# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Elevation drawing of a beam-end shear connection (ezdxf, DXF R2013).

The view looks at the beam web: x runs along the beam from the face of the
support (x = 0), y is up with the bottom of the beam at y = 0. The same
:func:`shear_layout` feeds the 3D model. Model space at 1:1 in the project
length unit. Layers SC-*.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

from ezdxf.enums import TextEntityAlignment

from openconex.connections.shear.check import ShearConnection, ShearType
from openconex.connections.shear.double_angle import DoubleAngle
from openconex.connections.shear.end_plate import EndPlate
from openconex.connections.shear.extended_single_plate import ExtendedSinglePlate
from openconex.connections.shear.seated import SeatedAngle
from openconex.connections.shear.single_plate import SinglePlate
from openconex.connections.shear.stiffened_seat import StiffenedSeat, seat_plate_width
from openconex.i18n import tr
from openconex.units import Kind, UnitSystem, format_value, to_internal

from .base_plate import STEEL_DENSITY, _Sheet

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
    bom: bool = True
    """Include the bill of materials and weld schedule in the DXF."""


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
    cope_doubler: tuple[float, float, float, float] | None = None
    """Elevation rectangle (x0, y0, x1, y1) of the doubler plate."""
    cope_stiffener: tuple[float, float, float, float] | None = None
    """Elevation rectangle (x0, y0, x1, y1) of the longitudinal stiffener."""
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
                       (0.0, -(el.vertical_leg or el.leg + 2 * INCH), t, -t, "seat"),
                       (el.setback - INCH / 4, el.beam_d, el.setback - INCH / 4
                        + el.top_angle_length, el.beam_d + el.top_angle_thickness,
                        "top_angle"),
                       (0.0, el.beam_d, el.top_angle_thickness, el.beam_d + el.top_angle_leg,
                        "top_angle")]
        lay.plate_thickness = el.length
        if el.support_weld > 0:
            lay.welds.append((0.0, -(el.vertical_leg or el.leg), 0.0, 0.0))
        else:
            lay.support_bolts = [-t - 1.5 * INCH] if el.bolts <= 2 else [
                -t - 1.5 * INCH, -t - 4.5 * INCH]
            lay.support_bolt_end = t
    elif isinstance(el, StiffenedSeat):
        seat = el.seat_plate_thickness
        lay.beam_start = el.setback
        lay.plates += [(0.0, -seat, el.width, 0.0, "seat"),
                       (0.0, -seat - el.length, el.width, -seat, "stiffener"),
                       (el.setback, el.beam_d, el.setback + el.top_angle_length,
                        el.beam_d + el.top_angle_thickness, "top_angle"),
                       (0.0, el.beam_d, el.top_angle_thickness,
                        el.beam_d + el.top_angle_leg, "top_angle")]
        lay.plate_thickness = el.thickness
        lay.welds.append((0.0, -seat - el.length, 0.0, 0.0))
    if conn.cope is not None:
        x_start = lay.beam_start
        length = conn.cope.c + conn.cope.dc
        if conn.cope.doubler is not None:
            dp = conn.cope.doubler
            y1 = d - conn.cope.dc - dp.gap
            lay.cope_doubler = (x_start, y1 - dp.depth, x_start + length, y1)
            lay.welds += [(x_start, y1 - dp.depth, x_start, y1),
                          (x_start + length, y1 - dp.depth, x_start + length, y1)]
        if conn.cope.stiffener is not None:
            st = conn.cope.stiffener
            length = st.length if st.length is not None else length
            y1 = d - conn.cope.dc
            lay.cope_stiffener = (x_start, y1 - st.thickness, x_start + length, y1)
            lay.welds.append((x_start, y1, x_start + length, y1))
    return lay


def _steel(s: _Sheet, stress: float) -> str:
    return f"Fy={format_value(stress, Kind.STRESS, s.units, 4)}"


def _bom_rows(conn: ShearConnection, s: _Sheet, lang: str) -> list[tuple[str, ...]]:
    el = conn.element
    rows: list[tuple[str, ...]] = []

    def add(qty: int | str, description: str, material: str = "",
            mass: float | None = None) -> None:
        rows.append((str(len(rows) + 1), str(qty), description, material,
                     "" if mass is None else f"{mass:.1f} kg"))

    def t(key: str, **kw) -> str:
        return tr(f"drawing.{key}", lang, **kw)

    if isinstance(el, (SinglePlate, ExtendedSinglePlate)):
        lines = el.lines if isinstance(el, ExtendedSinglePlate) else 1
        gage = el.gage if isinstance(el, ExtendedSinglePlate) else 0.0
        width = el.a + el.leh + (lines - 1) * gage
        add(1, f"{t('shear_plate')} {s.label(width)} x {s.label(el.length)} x "
               f"{s.label(el.thickness)}", _steel(s, el.plate_Fy),
            width * el.length * el.thickness * STEEL_DENSITY)
    elif isinstance(el, EndPlate):
        add(1, f"{t('end_plate')} {s.label(el.length)} x {s.label(el.thickness)}",
            _steel(s, el.plate_Fy))
    elif isinstance(el, DoubleAngle):
        leg = el.beam_leg or el.weld_e or el.leh_beam
        outstanding = el.weld_e or el.leh_support or leg
        mass = None
        if leg and outstanding:
            mass = (2 * (leg + outstanding - el.thickness) * el.thickness * el.length
                    * STEEL_DENSITY)
        description = (f"2L {s.label(leg)} x {s.label(outstanding)} x "
                       f"{s.label(el.thickness)} x {s.label(el.length)}"
                       if leg and outstanding else
                       f"2L {s.label(el.thickness)} x {s.label(el.length)}")
        add(2, description, _steel(s, el.angle_Fy), mass)
    elif isinstance(el, SeatedAngle):
        vertical = el.vertical_leg or el.leg + 2 * INCH
        mass = (el.leg + vertical - el.thickness) * el.thickness * el.length * STEEL_DENSITY
        add(1, f"L {s.label(el.leg)} x {s.label(vertical)} x {s.label(el.thickness)}",
            _steel(s, el.Fy), mass)
        top_mass = ((2 * el.top_angle_leg - el.top_angle_thickness)
                    * el.top_angle_thickness * el.top_angle_length * STEEL_DENSITY)
        add(1, f"L {s.label(el.top_angle_leg)} x {s.label(el.top_angle_leg)} x "
               f"{s.label(el.top_angle_thickness)} x {s.label(el.top_angle_length)}",
            _steel(s, el.Fy), top_mass)
    elif isinstance(el, StiffenedSeat):
        add(1, f"{t('stiffener')} {s.label(el.width)} x {s.label(el.length)} x "
               f"{s.label(el.thickness)}", _steel(s, el.stiffener_Fy),
            el.width * el.length * el.thickness * STEEL_DENSITY)
        plate_width = seat_plate_width(el)
        add(1, f"{t('seat_plate')} {s.label(el.seat_plate_thickness)} x "
               f"{s.label(el.width)} x {s.label(plate_width)}",
            _steel(s, el.stiffener_Fy),
            el.width * plate_width * el.seat_plate_thickness * STEEL_DENSITY)
        top_mass = ((2 * el.top_angle_leg - el.top_angle_thickness)
                    * el.top_angle_thickness * el.top_angle_length * STEEL_DENSITY)
        add(1, f"L {s.label(el.top_angle_leg)} x {s.label(el.top_angle_leg)} x "
               f"{s.label(el.top_angle_thickness)} x {s.label(el.top_angle_length)}",
            _steel(s, el.stiffener_Fy), top_mass)

    if conn.cope is not None:
        base_length = conn.cope.c + conn.cope.dc
        if conn.cope.doubler is not None:
            dp = conn.cope.doubler
            add(1, f"{t('doubler_plate')} {s.label(dp.thickness)} x "
                   f"{s.label(dp.depth)} x {s.label(base_length)}",
                _steel(s, conn.beam.material.Fy),
                dp.depth * base_length * dp.thickness * STEEL_DENSITY)
        if conn.cope.stiffener is not None:
            st = conn.cope.stiffener
            length = st.length if st.length is not None else base_length
            add(1, f"{t('long_stiffener')} {s.label(st.width)} x "
                   f"{s.label(st.thickness)} x {s.label(length)}",
                _steel(s, conn.beam.material.Fy),
                st.width * length * st.thickness * STEEL_DENSITY)

    bolt = getattr(el, "bolt", None)
    count = 0
    if isinstance(el, (SinglePlate, ExtendedSinglePlate)):
        count = el.rows * (el.lines if isinstance(el, ExtendedSinglePlate) else 1)
    elif isinstance(el, EndPlate):
        count = 2 * el.rows
    elif isinstance(el, DoubleAngle):
        count = (0 if el.beam_weld else el.rows) + (0 if el.support_weld else el.rows)
    elif isinstance(el, SeatedAngle):
        count = 0 if el.support_weld else el.bolts
    if count and bolt is not None:
        add(count, f"{t('bolts')} Ø {s.label(bolt.diameter)}", bolt.grade)
    return rows


def _weld_sizes(conn: ShearConnection) -> list[float]:
    el = conn.element
    sizes = (getattr(el, "weld", 0.0), getattr(el, "support_weld", 0.0),
             getattr(el, "beam_weld", 0.0))
    if conn.cope is not None:
        sizes += (getattr(conn.cope.doubler, "weld", 0.0),
                  getattr(conn.cope.stiffener, "weld", 0.0))
    return [value for value in dict.fromkeys(sizes) if value > 0]


def _weld_length(lay: ShearLayout) -> float:
    return sum(math.hypot(x1 - x0, y1 - y0) for x0, y0, x1, y1 in lay.welds)


def _weld_symbol(s: _Sheet, x: float, y: float, h: float) -> None:
    attrs = {"layer": "SC-SOLDADURA", "lineweight": 70}
    s.msp.add_line((x, y), (x + 4 * h, y), dxfattribs=attrs)
    s.msp.add_line((x + h, y), (x + 1.8 * h, y + h), dxfattribs=attrs)
    s.msp.add_line((x + 1.8 * h, y + h), (x + 2.6 * h, y), dxfattribs=attrs)
    s.msp.add_line((x + 1.8 * h, y), (x + 1.8 * h, y + h), dxfattribs=attrs)
    s.text("w", x + 0.45 * h, y + 0.25 * h, 0.55 * h, layer="SC-TEXTO")


def _draw_bom(s: _Sheet, conn: ShearConnection, lay: ShearLayout, x: float, y: float,
              lang: str) -> None:
    def t(key: str, **kw) -> str:
        return tr(f"drawing.{key}", lang, **kw)

    h = s.text_h
    rows = [
        (t("item"), t("qty"), t("description"), t("material"), t("weight")),
        *_bom_rows(conn, s, lang),
    ]
    widths = (3, 3, 36, 16, 8)
    s.text(t("bom"), x, y + 2 * h, 1.2 * h, layer="SC-TEXTO")
    for r, row in enumerate(rows):
        top = y - r * 2 * h
        cursor = x
        for col, (width, cell) in enumerate(zip(widths, row, strict=True)):
            s.rect(cursor, top - 2 * h, cursor + width * h, top, "SC-TEXTO")
            if col in (0, 1, 4):
                s.text(cell, cursor + width * h - 0.25 * h, top - 1.55 * h,
                       0.65 * h, layer="SC-TEXTO", align=TextEntityAlignment.RIGHT)
            else:
                s.text(cell, cursor + 0.25 * h, top - 1.55 * h, 0.65 * h,
                       layer="SC-TEXTO")
            cursor += width * h

    note_y = y - len(rows) * 2 * h - 1.4 * h
    s.text(t("note_units", unit=s.unit), x, note_y, 0.75 * h, layer="SC-TEXTO")

    sizes = _weld_sizes(conn)
    if not sizes:
        return
    wy = note_y - 2.4 * h
    s.text(t("weld_schedule"), x, wy, 1.1 * h, layer="SC-TEXTO")
    weld_widths = (6, 9, 8, 9)
    header = (t("symbol"), t("type"), t("size"), t("length"))
    for row_index, row in enumerate([header] + [
            ("", t("fillet_weld"), s.label(size),
             s.label(_weld_length(lay)) if len(sizes) == 1 else "—") for size in sizes]):
        top = wy - (row_index + 1) * 2 * h
        cursor = x
        for width, cell in zip(weld_widths, row, strict=True):
            s.rect(cursor, top - 2 * h, cursor + width * h, top, "SC-TEXTO")
            if row_index and width == 6:
                _weld_symbol(s, cursor + 0.5 * h, top - 1.45 * h, 0.55 * h)
            else:
                s.text(cell, cursor + 0.25 * h, top - 1.55 * h, 0.65 * h,
                       layer="SC-TEXTO")
            cursor += width * h
    s.text(t("weld_note"), x, wy - (len(sizes) + 2) * 2 * h, 0.7 * h,
           layer="SC-TEXTO")


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
    for rectangle in (lay.cope_doubler, lay.cope_stiffener):
        if rectangle is not None:
            x_0, y_0, x_1, y_1 = rectangle
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

    if opt.bom:
        _draw_bom(s, conn, lay, x0 + xl + 6 * s.text_h, hi, lang)


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
    if conn.cope is not None:
        if conn.cope.doubler is not None:
            dp = conn.cope.doubler
            out.append(f"{tr('drawing.doubler_plate', lang)}: {q(dp.thickness)} x "
                       f"{q(dp.depth)}")
        if conn.cope.stiffener is not None:
            st = conn.cope.stiffener
            out.append(f"{tr('drawing.long_stiffener', lang)}: {q(st.width)} x "
                       f"{q(st.thickness)}")
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
