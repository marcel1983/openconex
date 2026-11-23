# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Drawing of a bolted beam or column splice (ezdxf, DXF R2013).

Layout axes (:func:`splice_layout`, also used by the 3D model): x along the
member from the splice centerline, y across the depth from the member axis, z
across the flanges. The beam splice is drawn horizontal and the column splice
vertical (lower column below). Views: elevation looking at the web and plan of
the top (or right) flange. Layers SP-*.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from openconex.connections.splice.splice import BeamSplice, ColumnSplice, web_bolts
from openconex.i18n import tr
from openconex.units import Kind, UnitSystem, to_internal

from .base_plate import _Sheet

__all__ = ["LAYERS", "Box", "SpliceDrawing", "SpliceLayout", "splice_dxf", "splice_layout",
           "write_splice_dxf"]

LAYERS = {
    "SP-PERFIL": (5, "Continuous"),
    "SP-PLACA": (1, "Continuous"),
    "SP-RELLENO": (2, "Continuous"),
    "SP-PERNO": (3, "Continuous"),
    "SP-COTAS": (8, "Continuous"),
    "SP-TEXTO": (7, "Continuous"),
    "SP-EJES": (6, "CENTER"),
}

INCH = to_internal(1.0, "in", Kind.LENGTH)


@dataclass(frozen=True)
class SpliceDrawing:
    title: str = ""
    number: str = ""
    revision: str = "0"
    date: str = ""


@dataclass(frozen=True)
class Box:
    """Axis-aligned solid: x, y, z ranges in the layout axes."""

    name: str
    x0: float
    x1: float
    y0: float
    y1: float
    z0: float
    z1: float
    layer: str = "SP-PLACA"


@dataclass
class SpliceLayout:
    column: bool
    members: list[Box] = field(default_factory=list)
    """Flanges and web of each member, as boxes."""
    plates: list[Box] = field(default_factory=list)
    fillers: list[Box] = field(default_factory=list)
    flange_bolts: list[tuple[float, float, float, float]] = field(default_factory=list)
    """(x, z, y0, y1): bolts through the flange plates, along y."""
    web_bolts: list[tuple[float, float, float, float]] = field(default_factory=list)
    """(x, y, z0, z1): bolts through the web plates, along z."""
    flange_bolt_diameter: float = 0.0
    web_bolt_diameter: float = 0.0
    length: float = 0.0
    """Drawn member length on each side of the splice."""


def _i_boxes(name: str, x0: float, x1: float, d: float, bf: float, tf: float,
             tw: float) -> list[Box]:
    return [Box(f"{name}_flange_top", x0, x1, d / 2 - tf, d / 2, -bf / 2, bf / 2, "SP-PERFIL"),
            Box(f"{name}_flange_bottom", x0, x1, -d / 2, -d / 2 + tf, -bf / 2, bf / 2,
                "SP-PERFIL"),
            Box(f"{name}_web", x0, x1, -d / 2 + tf, d / 2 - tf, -tw / 2, tw / 2, "SP-PERFIL")]


def splice_layout(sp: BeamSplice | ColumnSplice) -> SpliceLayout:
    column = isinstance(sp, ColumnSplice)
    fl, w, gap = sp.flange, sp.web, sp.gap
    if column:
        left, right = sp.lower, sp.upper
    else:
        left = right = sp.beam
    span = max(fl.length, w.length if w else 0.0) + gap / 2
    length = max(1.6 * span, 1.2 * max(left.d, right.d))
    lay = SpliceLayout(column=column, length=length,
                       flange_bolt_diameter=fl.bolt.diameter,
                       web_bolt_diameter=w.bolt.diameter if w else 0.0)
    lay.members += _i_boxes("member_1", -length, -gap / 2, left.d, left.bf, left.tf, left.tw)
    lay.members += _i_boxes("member_2", gap / 2, length, right.d, right.bf, right.tf,
                            right.tw)
    D = max(left.d, right.d)
    xp = gap / 2 + fl.length
    t = fl.thickness
    lay.plates += [Box("flange_plate_top", -xp, xp, D / 2, D / 2 + t, -fl.width / 2,
                       fl.width / 2),
                   Box("flange_plate_bottom", -xp, xp, -D / 2 - t, -D / 2, -fl.width / 2,
                       fl.width / 2)]
    if column and sp.filler > 0:
        shallow = sp.shallow
        x0, x1 = (gap / 2, xp) if shallow is right else (-xp, -gap / 2)
        bf = min(fl.width, shallow.bf)
        for side, y0, y1 in (("top", shallow.d / 2, D / 2), ("bottom", -D / 2,
                                                              -shallow.d / 2)):
            lay.fillers.append(Box(f"filler_{side}", x0, x1, y0, y1, -bf / 2, bf / 2,
                                   "SP-RELLENO"))
    ti = fl.inner_thickness if fl.inner else 0.0
    if fl.inner:
        bi, g = fl.inner_width, fl.gage
        tf = left.tf
        for side, sign in (("top", 1), ("bottom", -1)):
            y_out = sign * (D / 2 - tf)
            y0, y1 = sorted((y_out, y_out - sign * ti))
            for k, zc in (("a", g / 2), ("b", -g / 2)):
                lay.plates.append(Box(f"inner_plate_{side}_{k}", -xp, xp, y0, y1,
                                      zc - bi / 2, zc + bi / 2))
    r_top = D / 2 + t
    for sx in (-1, 1):
        for i in range(fl.rows):
            x = sx * (gap / 2 + fl.lev_member + i * fl.spacing)
            member = right if sx > 0 else left
            for z in (-fl.gage / 2, fl.gage / 2):
                lay.flange_bolts.append((x, z, member.d / 2 - member.tf - ti, r_top))
                lay.flange_bolts.append((x, z, -r_top, -member.d / 2 + member.tf + ti))
    if w is not None:
        xw = gap / 2 + w.length
        z0 = max(left.tw, right.tw) / 2
        for k, sign in (("a", 1), ("b", -1)):
            za, zb = sorted((sign * z0, sign * (z0 + w.thickness)))
            lay.plates.append(Box(f"web_plate_{k}", -xw, xw, -w.height / 2, w.height / 2,
                                  za, zb))
        for x, y in web_bolts(w, gap):
            for sx in (-1, 1):
                lay.web_bolts.append((sx * x, y, -z0 - w.thickness, z0 + w.thickness))
    return lay


def _draw(s: _Sheet, sp: BeamSplice | ColumnSplice, lay: SpliceLayout, opt: SpliceDrawing,
          lang: str) -> None:
    u = s.u
    # elevation: (x, y) -> drawing; the column is drawn vertical (x up)
    if lay.column:
        def elev(x, y):
            return (u(-y), u(x))
    else:
        def elev(x, y):
            return (u(x), u(y))

    def rect(x0, y0, x1, y1, layer):
        (a, b), (c, d) = elev(x0, y0), elev(x1, y1)
        s.rect(min(a, c), min(b, d), max(a, c), max(b, d), layer)

    def line(x0, y0, x1, y1, layer, **kw):
        s.msp.add_line(elev(x0, y0), elev(x1, y1), dxfattribs={"layer": layer, **kw})

    for b in lay.members:
        if b.name.endswith("_web"):
            continue
        rect(b.x0, b.y0, b.x1, b.y1, "SP-PERFIL")
    for name in ("member_1", "member_2"):
        top = next(b for b in lay.members if b.name == f"{name}_flange_top")
        bot = next(b for b in lay.members if b.name == f"{name}_flange_bottom")
        for x in (top.x0, top.x1):
            line(x, bot.y0, x, top.y1, "SP-PERFIL")
    for b in lay.plates:
        if b.name.startswith("inner_plate") and b.name.endswith("_b"):
            continue
        if b.name.startswith("web_plate_b"):
            continue
        rect(b.x0, b.y0, b.x1, b.y1, "SP-PLACA")
    for b in lay.fillers:
        rect(b.x0, b.y0, b.x1, b.y1, "SP-RELLENO")
    r = u(lay.web_bolt_diameter) / 2 or u(0.4 * INCH)
    for x, y, _, _ in lay.web_bolts:
        s.msp.add_circle(elev(x, y), r, dxfattribs={"layer": "SP-PERNO"})
    seen = set()
    for x, _, y0, y1 in lay.flange_bolts:
        if (x, y0) in seen:
            continue
        seen.add((x, y0))
        line(x, y0, x, y1, "SP-PERNO")
    extent = max(b.y1 for b in lay.plates)
    line(0.0, -extent - 2 * INCH, 0.0, extent + 2 * INCH, "SP-EJES")
    top = next(b for b in lay.plates if b.name == "flange_plate_top")
    (a, b_), (c, d) = elev(top.x0, top.y1), elev(top.x1, top.y1)
    if lay.column:
        s.vdim(b_, d, a, a - 3 * s.text_h)
    else:
        s.hdim(a, c, b_, b_ + 3 * s.text_h)
    # plan of the top flange (beam) or of the right flange (column), offset from the elevation
    off = 2.2 * extent + 6 * INCH
    if lay.column:
        def plan(x, z):
            return (u(z + off), u(x))
    else:
        def plan(x, z):
            return (u(x), u(z - off))

    def prect(x0, z0, x1, z1, layer):
        (a, b), (c, d) = plan(x0, z0), plan(x1, z1)
        s.rect(min(a, c), min(b, d), max(a, c), max(b, d), layer)

    for b in lay.members:
        if b.name.endswith("_flange_top"):
            prect(b.x0, b.z0, b.x1, b.z1, "SP-PERFIL")
    prect(top.x0, top.z0, top.x1, top.z1, "SP-PLACA")
    rf = u(lay.flange_bolt_diameter) / 2
    for x, z, y0, _ in lay.flange_bolts:
        if y0 > 0:
            s.msp.add_circle(plan(x, z), rf, dxfattribs={"layer": "SP-PERNO"})
    q = s.label
    fl = sp.flange
    if lay.column:
        lo, hi = sp.lower, sp.upper
        lines = [tr("splice.type.column", lang),
                 f"{tr('input.upper_column', lang)}: {hi.name}",
                 f"{tr('input.lower_column', lang)}: {lo.name}"]
        if sp.filler > 0:
            lines.append(f"{tr('input.filler', lang)}: {q(sp.filler)}")
    else:
        lines = [tr("splice.type.beam", lang), f"{tr('input.beam', lang)}: {sp.beam.name}"]
    lines.append(f"PL {q(fl.thickness)} × {q(fl.width)} × {q(top.x1 - top.x0)}")
    if fl.inner:
        lines.append(f"2 PL {q(fl.inner_thickness)} × {q(fl.inner_width)}")
    lines.append(f"{tr('input.flange_bolts', lang)}: {len(lay.flange_bolts)} × Ø "
                 f"{q(fl.bolt.diameter)} {fl.bolt.grade}")
    w = sp.web
    if w is not None:
        lines.append(f"2 PL {q(w.thickness)} × {q(w.height)} × {q(2 * w.length + sp.gap)}; "
                     f"{len(lay.web_bolts)} × Ø {q(w.bolt.diameter)}")
    corners = [elev(b.x0, b.y0) for b in lay.members] + [elev(b.x1, b.y1) for b in lay.members]
    corners += [plan(b.x0, b.z0) for b in lay.members] + [plan(b.x1, b.z1) for b in lay.members]
    x_text = min(x for x, _ in corners)
    y_text = min(y for _, y in corners) - 3 * s.text_h
    label_h = 1.4 * s.text_h
    if lay.column:
        x_el, y_el = elev(lay.length, extent)
        x_pl, y_pl = plan(lay.length, -max(b.z1 for b in lay.members))
    else:
        x_el, y_el = elev(-lay.length, extent + 2 * INCH)
        x_pl, y_pl = plan(-lay.length, max(b.z1 for b in lay.members) + 2 * INCH)
    s.text(tr("drawing.elevation", lang), x_el, y_el + 2 * s.text_h, height=label_h,
           layer="SP-TEXTO")
    s.text(tr("drawing.plan", lang), x_pl, y_pl + 2 * s.text_h, height=label_h,
           layer="SP-TEXTO")
    y = y_text
    for text in lines:
        s.text(text, x_text, y, layer="SP-TEXTO")
        y -= 1.6 * s.text_h
    title = " · ".join(v for v in (opt.title, opt.number, f"Rev. {opt.revision}", opt.date) if v)
    if title:
        s.text(title, x_text, y - s.text_h, height=1.2 * s.text_h, layer="SP-TEXTO")


def splice_dxf(sp: BeamSplice | ColumnSplice, units: UnitSystem, lang: str = "es",
               options: SpliceDrawing | None = None):
    s = _Sheet(units, lang)
    for name, (color, ltype) in LAYERS.items():
        if name not in s.doc.layers:
            s.doc.layers.add(name, color=color, linetype=ltype)
    lay = splice_layout(sp)
    depth = max(b.y1 for b in lay.members) * 2
    s.setup_dims(s.u(max(depth, 300.0)) / 60)
    _draw(s, sp, lay, options or SpliceDrawing(), lang)
    return s.doc


def write_splice_dxf(sp: BeamSplice | ColumnSplice, path: str | Path, units: UnitSystem,
                     lang: str = "es", options: SpliceDrawing | None = None) -> Path:
    path = Path(path)
    splice_dxf(sp, units, lang, options).saveas(path)
    return path
