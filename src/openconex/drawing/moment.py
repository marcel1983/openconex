# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Elevation drawing of a beam-to-column-flange moment connection (ezdxf, DXF R2013).

View looking at the beam web: x along the beam from the face of the column
flange (x = 0), y up from the bottom of the beam. Same geometry for the 3D
model (:func:`moment_layout`). Layers MC-*.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from openconex.connections.moment.fr_moment import FlangeDetail, MomentConnection
from openconex.i18n import tr
from openconex.units import Kind, UnitSystem, to_internal

from .base_plate import _Sheet

__all__ = ["LAYERS", "MomentDrawing", "MomentLayout", "moment_dxf", "moment_layout",
           "write_moment_dxf"]

LAYERS = {
    "MC-VIGA": (5, "Continuous"),
    "MC-COLUMNA": (4, "Continuous"),
    "MC-PLACA": (1, "Continuous"),
    "MC-PERNO": (3, "Continuous"),
    "MC-SOLDADURA": (30, "Continuous"),
    "MC-COTAS": (8, "Continuous"),
    "MC-TEXTO": (7, "Continuous"),
}

INCH = to_internal(1.0, "in", Kind.LENGTH)
SETBACK = INCH / 2


@dataclass(frozen=True)
class MomentDrawing:
    title: str = ""
    number: str = ""
    revision: str = "0"
    date: str = ""


@dataclass
class MomentLayout:
    beam_d: float
    beam_tf: float
    beam_length: float
    column_d: float
    column_tf: float
    plates: list[tuple[float, float, float, float, str]] = field(default_factory=list)
    """(x0, y0, x1, y1, name) of the flange and web plates in elevation."""
    flange_bolts: list[float] = field(default_factory=list)
    """x of the flange bolts (each through the top and bottom flange plates)."""
    web_bolts: list[tuple[float, float]] = field(default_factory=list)
    bolt_diameter: float = 0.0
    welds: list[tuple[float, float, float, float]] = field(default_factory=list)
    end_plate_rows: list[float] = field(default_factory=list)
    """y of the end-plate bolt rows (two bolts each, at the gage)."""
    stiffeners: list[list[tuple[float, float]]] = field(default_factory=list)
    """End-plate stiffeners in elevation (closed polygons)."""
    beam_x0: float = 0.0
    """x of the beam end (setback, or the end-plate thickness)."""


def _end_plate_layout(mc: MomentConnection, lay: MomentLayout) -> None:
    from openconex.connections.moment.end_plate import EndPlateLayout as Layout
    ep, beam = mc.end_plate, mc.beam
    d, tf, t = beam.d, beam.tf, ep.thickness
    inner = [d - tf - ep.pf - i * ep.pb for i in range(ep.inside_rows)]
    rows = list(inner)
    top = d
    if not ep.flush:
        rows.insert(0, d + ep.pf_o)
        top = d + ep.pext
    if ep.symmetric:
        bottom_rows = [d - y for y in rows]
        bottom = d - top
    else:
        bottom_rows = [tf + ep.pf]
        bottom = 0.0
    lay.end_plate_rows = rows + bottom_rows
    lay.plates.append((0.0, bottom, t, top, "end_plate"))
    lay.bolt_diameter = ep.bolt.diameter
    lay.beam_x0 = t
    half = (beam.bf - beam.tw) / 2
    if ep.layout in (Layout.EXTENDED_4_STIFFENED, Layout.EXTENDED_1_3_STIFFENED):
        h = ep.pext
        length = h * 3**0.5  # 30° stiffener, AISC 358 §6.10
        lay.stiffeners.append([(t, d), (t, d + h), (t + length, d)])
        if ep.symmetric:
            lay.stiffeners.append([(t, 0.0), (t, -h), (t + length, 0.0)])
    elif ep.layout is Layout.FLUSH_4_STIFFENED_BETWEEN:
        y1 = d - tf - ep.pf - ep.ps_o
        lay.stiffeners.append([(t, y1), (t + half, y1), (t + half, y1 - ep.stiffener_thickness),
                               (t, y1 - ep.stiffener_thickness)])
    elif ep.layout is Layout.FLUSH_4_STIFFENED_INSIDE:
        y1 = d - tf - ep.pf - ep.pb - ep.ps
        ts = ep.stiffener_thickness or tf
        lay.stiffeners.append([(t, y1), (t + half, y1), (t + half, y1 - ts), (t, y1 - ts)])
    lay.welds += [(t, d - tf, t, d), (t, 0.0, t, tf)]
    lay.welds.append((t, tf, t, d - tf))


def moment_layout(mc: MomentConnection) -> MomentLayout:
    beam, col = mc.beam, mc.column
    d = beam.d
    lay = MomentLayout(beam_d=d, beam_tf=beam.tf, beam_length=max(1.5 * d, 30 * INCH),
                       column_d=col.d, column_tf=col.tf)
    if mc.detail is FlangeDetail.END_PLATE:
        _end_plate_layout(mc, lay)
        return lay
    lay.beam_x0 = SETBACK if mc.detail is not FlangeDetail.WELDED_FLANGE else 0.0
    w = mc.web
    mid = d / 2
    top_y = mid + w.length / 2
    web_width = w.leh + 2 * INCH
    lay.plates.append((0.0, top_y - w.length, web_width, top_y, "web_plate"))
    bottom_bolt = top_y - w.length + w.lev
    lay.web_bolts = [(web_width - w.leh, bottom_bolt + i * w.spacing) for i in range(w.rows)]
    lay.bolt_diameter = w.bolt.diameter
    lay.welds.append((0.0, top_y - w.length, 0.0, top_y))
    if mc.detail is FlangeDetail.BOLTED_FLANGE_PLATE:
        length = SETBACK + (mc.beam_lev) + (mc.rows - 1) * mc.spacing + mc.plate_lev
        t_top = mc.top.thickness
        t_bot = (mc.bottom or mc.top).thickness
        lay.plates += [(0.0, d, length, d + t_top, "top_plate"),
                       (0.0, -t_bot, length, 0.0, "bottom_plate")]
        lay.flange_bolts = [SETBACK + mc.beam_lev + i * mc.spacing for i in range(mc.rows)]
        lay.welds += [(0.0, d, 0.0, d + t_top), (0.0, -t_bot, 0.0, 0.0)]
    elif mc.detail is FlangeDetail.WELDED_FLANGE_PLATE:
        top, bottom = mc.top, mc.bottom
        top_len = top.weld_length + SETBACK + INCH / 2
        bot_len = bottom.weld_length + SETBACK + INCH / 2
        lay.plates += [(0.0, d, top_len, d + top.thickness, "top_plate"),
                       (0.0, -bottom.thickness, bot_len, 0.0, "bottom_plate")]
        lay.welds += [(0.0, d, 0.0, d + top.thickness), (0.0, -bottom.thickness, 0.0, 0.0),
                      (top_len - top.weld_length, d + top.thickness, top_len,
                       d + top.thickness),
                      (bot_len - bottom.weld_length, -bottom.thickness, bot_len,
                       -bottom.thickness)]
    else:
        lay.welds += [(0.0, d - beam.tf, 0.0, d), (0.0, 0.0, 0.0, beam.tf)]
    return lay


def _draw(s: _Sheet, mc: MomentConnection, lay: MomentLayout, opt: MomentDrawing,
          lang: str) -> None:
    u = s.u
    d, tf = u(lay.beam_d), u(lay.beam_tf)
    ys = [y for p in lay.plates for y in (p[1], p[3])] + [0.0, lay.beam_d]
    lo, hi = u(min(ys)) - u(6 * INCH), u(max(ys)) + u(6 * INCH)
    cd, ctf = u(lay.column_d), u(lay.column_tf)
    # column: two flanges and web line (side view of the column)
    s.rect(-ctf, lo, 0.0, hi, "MC-COLUMNA")
    s.rect(-cd, lo, -cd + ctf, hi, "MC-COLUMNA")
    # beam
    x0, xe = u(lay.beam_x0), u(lay.beam_length)
    s.rect(x0, 0.0, xe, d, "MC-VIGA")
    for y in (tf, d - tf):
        s.msp.add_line((x0, y), (xe, y), dxfattribs={"layer": "MC-VIGA"})
    for x_0, y_0, x_1, y_1, _ in lay.plates:
        s.rect(u(x_0), u(y_0), u(x_1), u(y_1), "MC-PLACA")
    r = u(lay.bolt_diameter) / 2 or u(0.4 * INCH)
    for x, y in lay.web_bolts:
        s.msp.add_circle((u(x), u(y)), r, dxfattribs={"layer": "MC-PERNO"})
    for y in lay.end_plate_rows:
        t = u(lay.plates[0][2])
        s.rect(-ctf - 1.5 * r, u(y) - r, t + 1.5 * r, u(y) + r, "MC-PERNO")
    for poly in lay.stiffeners:
        s.msp.add_lwpolyline([(u(x), u(y)) for x, y in poly], close=True,
                             dxfattribs={"layer": "MC-PLACA"})
    for x in lay.flange_bolts:
        for y0, y1 in ((u(lay.plates[1][3]) + 2 * r, d - tf - 2 * r),
                       (u(lay.plates[2][1]) - 2 * r, tf + 2 * r)):
            s.msp.add_line((u(x), y0), (u(x), y1), dxfattribs={"layer": "MC-PERNO"})
    for x_0, y_0, x_1, y_1 in lay.welds:
        s.msp.add_line((u(x_0), u(y_0)), (u(x_1), u(y_1)),
                       dxfattribs={"layer": "MC-SOLDADURA", "lineweight": 70})
    if len(lay.plates) > 1:
        x_0, y_0, x_1, y_1, _ = lay.plates[1]
        s.hdim(u(x_0), u(x_1), u(y_1), u(y_1) + 3 * s.text_h)
    x_0, y_0, x_1, y_1, _ = lay.plates[0]
    s.vdim(u(y_0), u(y_1), u(x_1), u(x_1) + 3 * s.text_h)
    s.text(tr("drawing.elevation", lang), -cd, hi + 2 * s.text_h, height=1.4 * s.text_h,
           layer="MC-TEXTO")
    lines = [tr(f"moment.type.{mc.detail.value}", lang),
             f"{tr('input.beam', lang)}: {mc.beam.name}",
             f"{tr('input.column', lang)}: {mc.column.name}"]
    q = s.label
    if mc.top is not None:
        lines.append(f"PL {q(mc.top.thickness)} × {q(mc.top.width)}")
    if mc.bolt is not None:
        lines.append(f"{tr('input.bolts', lang)}: {4 * mc.rows} × Ø {q(mc.bolt.diameter)} "
                     f"{mc.bolt.grade}")
    if mc.web is not None:
        lines.append(f"PL {q(mc.web.thickness)} × {q(mc.web.length)}, {mc.web.rows} × Ø "
                     f"{q(mc.web.bolt.diameter)}")
    ep = mc.end_plate
    if mc.detail is FlangeDetail.END_PLATE and ep is not None:
        x_0, y_0, x_1, y_1, _ = lay.plates[0]
        lines.append(tr(f"moment.layout.{ep.layout.value}", lang))
        lines.append(f"PL {q(ep.thickness)} × {q(ep.width)} × {q(y_1 - y_0)}")
        lines.append(f"{tr('input.bolts', lang)}: {2 * len(lay.end_plate_rows)} × Ø "
                     f"{q(ep.bolt.diameter)} {ep.bolt.grade}, g = {q(ep.gage)}")
    y = lo - 3 * s.text_h
    for line in lines:
        s.text(line, -cd, y, layer="MC-TEXTO")
        y -= 1.6 * s.text_h
    title = " · ".join(v for v in (opt.title, opt.number, f"Rev. {opt.revision}", opt.date) if v)
    if title:
        s.text(title, -cd, y - s.text_h, height=1.2 * s.text_h, layer="MC-TEXTO")


def moment_dxf(mc: MomentConnection, units: UnitSystem, lang: str = "es",
               options: MomentDrawing | None = None):
    s = _Sheet(units, lang)
    for name, (color, ltype) in LAYERS.items():
        if name not in s.doc.layers:
            s.doc.layers.add(name, color=color, linetype=ltype)
    lay = moment_layout(mc)
    s.setup_dims(s.u(max(lay.beam_d, 300.0)) / 60)
    _draw(s, mc, lay, options or MomentDrawing(), lang)
    return s.doc


def write_moment_dxf(mc: MomentConnection, path: str | Path, units: UnitSystem,
                     lang: str = "es", options: MomentDrawing | None = None) -> Path:
    path = Path(path)
    moment_dxf(mc, units, lang, options).saveas(path)
    return path
