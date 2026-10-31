# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""DXF fabrication drawing of an exposed column base plate (ezdxf, DXF R2013).

Model space at 1:1 in the project length unit (mm or in.). Views: plan,
elevation and bill of materials, plus notes and a title block. Layers follow
the names of the development plan (BP-*).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import ezdxf
from ezdxf.enums import TextEntityAlignment

from openconex.connections.base_plate.check import BasePlate
from openconex.core.bolting import base_plate_hole
from openconex.core.model import HSSKind, HSSShape
from openconex.i18n import tr
from openconex.units import Kind, UnitSystem, format_value, from_internal

__all__ = ["LAYERS", "BasePlateDrawing", "anchor_hole", "write_base_plate_dxf"]

LAYERS = {  # name: (ACI color, linetype)
    "BP-PLACA": (1, "Continuous"),
    "BP-COLUMNA": (5, "Continuous"),
    "BP-ANCLAJE": (3, "Continuous"),
    "BP-COTAS": (8, "Continuous"),
    "BP-TEXTO": (7, "Continuous"),
    "BP-EJES": (6, "CENTER"),
    "BP-CONCRETO": (9, "DASHED"),
}

STEEL_DENSITY = 7.85e-6  # kg/mm³


def anchor_hole(d: float) -> float:
    """Hole diameter [mm] for an anchor rod of diameter ``d`` [mm] (Manual Table 14-2)."""
    return base_plate_hole(from_internal(d, Kind.LENGTH, "in"))[0]


def plate_washer(d: float, thickness: float | None = None) -> tuple[float, float]:
    """Plate washer (size, thickness) [mm]: Table 14-2, or the designed thickness if larger."""
    _, size, t_min = base_plate_hole(from_internal(d, Kind.LENGTH, "in"))
    return size, max(t_min, thickness or 0.0)


@dataclass(frozen=True)
class BasePlateDrawing:
    """Geometry and annotation options that are not part of the design model."""

    pedestal_N: float | None = None
    pedestal_B: float | None = None
    grout: float = 38.1
    column_stub: float | None = None
    title: str = ""
    number: str = ""
    revision: str = "0"
    date: str = ""


class _Sheet:
    def __init__(self, units: UnitSystem, lang: str):
        self.lang = lang
        self.units = units
        self.unit = units.length if units.length in ("mm", "in") else (
            "in" if units.length == "ft" else "mm")
        self.doc = ezdxf.new("R2013", setup=True)
        self.doc.header["$INSUNITS"] = 1 if self.unit == "in" else 4
        self.doc.header["$MEASUREMENT"] = 0 if self.unit == "in" else 1
        for name, (color, ltype) in LAYERS.items():
            self.doc.layers.add(name, color=color, linetype=ltype)
        self.msp = self.doc.modelspace()

    def u(self, mm: float) -> float:
        """Internal mm to drawing units."""
        return from_internal(mm, Kind.LENGTH, self.unit)

    def label(self, mm: float) -> str:
        return format_value(mm, Kind.LENGTH, self.units.with_unit(Kind.LENGTH, self.unit), 4)

    def setup_dims(self, size: float) -> None:
        style = self.doc.dimstyles.get("EZDXF")
        style.dxf.dimtxt = size
        style.dxf.dimasz = size * 0.8
        style.dxf.dimexe = size * 0.4
        style.dxf.dimexo = size * 0.4
        style.dxf.dimgap = size * 0.3
        if self.unit == "mm":
            style.dxf.dimlunit, style.dxf.dimdec = 2, 0  # decimal, whole millimetres
        else:
            style.dxf.dimlunit, style.dxf.dimdec = 5, 4  # fractional inches to 1/16
        self.text_h = size

    def rect(self, x0, y0, x1, y1, layer):
        self.msp.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], close=True,
                                dxfattribs={"layer": layer})

    def text(self, s, x, y, height=None, layer="BP-TEXTO",
             align=TextEntityAlignment.LEFT):
        t = self.msp.add_text(s, height=height or self.text_h, dxfattribs={"layer": layer})
        t.set_placement((x, y), align=align)
        return t

    def hdim(self, x0, x1, y, base_y):
        self.msp.add_linear_dim(base=(x0, base_y), p1=(x0, y), p2=(x1, y),
                                dxfattribs={"layer": "BP-COTAS"}).render()

    def vdim(self, y0, y1, x, base_x):
        self.msp.add_linear_dim(base=(base_x, y0), p1=(x, y0), p2=(x, y1), angle=90,
                                dxfattribs={"layer": "BP-COTAS"}).render()


def _rod_positions(bp: BasePlate) -> list[tuple[float, float]]:
    n = bp.rods_per_side
    ys = [0.0] if n == 1 else [-bp.rod_spacing / 2 + i * bp.rod_spacing / (n - 1)
                               for i in range(n)]
    return [(sx * bp.f, y) for sx in (-1, 1) for y in ys]


def _i_shape(sheet: _Sheet, d, bf, tf, tw, cx, cy, layer):
    """Closed outline of an I-shape seen in plan (depth along x)."""
    hx, hy = d / 2, bf / 2
    pts = [(-hx, -hy), (-hx + tf, -hy), (-hx + tf, -tw / 2), (hx - tf, -tw / 2), (hx - tf, -hy),
           (hx, -hy), (hx, hy), (hx - tf, hy), (hx - tf, tw / 2), (-hx + tf, tw / 2),
           (-hx + tf, hy), (-hx, hy)]
    sheet.msp.add_lwpolyline([(cx + x, cy + y) for x, y in pts], close=True,
                             dxfattribs={"layer": layer})


def _lug_rectangles(bp: BasePlate) -> list[tuple[float, float]]:
    """Plan dimensions (x, y) of each shear lug, before drawing-unit scaling."""
    lug = bp.shear_lug
    if lug is None:
        return []
    if lug.direction == "strong":
        return [(lug.thickness, lug.width)]
    if lug.direction == "weak":
        return [(lug.width, lug.thickness)]
    return [(lug.thickness, lug.width), (lug.width, lug.thickness)]


def _hss_shape(sheet: _Sheet, kind: HSSKind, d, bf, t, cx, cy, layer):
    """Outline of a rectangular/square or round HSS seen in plan."""
    if kind is HSSKind.ROUND:
        sheet.msp.add_circle((cx, cy), d / 2, dxfattribs={"layer": layer})
        sheet.msp.add_circle((cx, cy), d / 2 - t, dxfattribs={"layer": layer})
    else:
        sheet.rect(cx - d / 2, cy - bf / 2, cx + d / 2, cy + bf / 2, layer)
        sheet.rect(cx - d / 2 + t, cy - bf / 2 + t, cx + d / 2 - t, cy + bf / 2 - t, layer)


def write_base_plate_dxf(bp: BasePlate, path: str | Path, units: UnitSystem, lang: str = "es",
                         options: BasePlateDrawing | None = None) -> Path:
    opt = options or BasePlateDrawing()
    s = _Sheet(units, lang)

    def t(key, **kw):
        return tr(f"drawing.{key}", lang, **kw)

    if bp.shear_lug:
        s.doc.layers.add("BP-LLAVE", color=2, linetype="DASHED")
    col = bp.column
    N, B, tp = s.u(bp.N), s.u(bp.B), s.u(bp.tp)
    s.setup_dims(max(N, B) / 40)
    h = s.text_h
    pN = s.u(opt.pedestal_N) if opt.pedestal_N else N + 8 * h
    pB = s.u(opt.pedestal_B) if opt.pedestal_B else B + 8 * h
    grout = s.u(opt.grout)
    rods = [(s.u(x), s.u(y)) for x, y in _rod_positions(bp)]
    d_rod = s.u(bp.rod.diameter)
    hole = s.u(anchor_hole(bp.rod.diameter))

    # ---------------------------------------------------------------- plan view
    s.rect(-pN / 2, -pB / 2, pN / 2, pB / 2, "BP-CONCRETO")
    s.rect(-N / 2, -B / 2, N / 2, B / 2, "BP-PLACA")
    if isinstance(col, HSSShape):
        _hss_shape(s, col.kind, s.u(col.d), s.u(col.bf), s.u(col.t), 0, 0, "BP-COLUMNA")
    else:
        _i_shape(s, s.u(col.d), s.u(col.bf), s.u(col.tf), s.u(col.tw), 0, 0, "BP-COLUMNA")
    for dx, dy in _lug_rectangles(bp):
        s.rect(-s.u(dx) / 2, -s.u(dy) / 2, s.u(dx) / 2, s.u(dy) / 2, "BP-LLAVE")
    w_size, w_t = (s.u(v) for v in plate_washer(bp.rod.diameter, bp.washer_thickness))
    for x, y in rods:
        s.rect(x - w_size / 2, y - w_size / 2, x + w_size / 2, y + w_size / 2, "BP-ANCLAJE")
        s.msp.add_circle((x, y), hole / 2, dxfattribs={"layer": "BP-PLACA"})
        s.msp.add_circle((x, y), d_rod / 2, dxfattribs={"layer": "BP-ANCLAJE"})
    ext = max(pN, N) / 2 + 2 * h
    s.msp.add_line((-ext, 0), (ext, 0), dxfattribs={"layer": "BP-EJES"})
    s.msp.add_line((0, -max(pB, B) / 2 - 2 * h), (0, max(pB, B) / 2 + 2 * h),
                   dxfattribs={"layer": "BP-EJES"})
    top = max(pB, B) / 2
    s.hdim(-N / 2, N / 2, B / 2, top + 6 * h)
    s.hdim(rods[0][0], rods[-1][0], rods[-1][1], top + 3 * h)
    s.vdim(-B / 2, B / 2, N / 2, max(pN, N) / 2 + 6 * h)
    if bp.rods_per_side > 1:
        s.vdim(rods[-1][1] - s.u(bp.rod_spacing), rods[-1][1], rods[-1][0],
               max(pN, N) / 2 + 3 * h)
    s.text(f"{t('plan')}", -N / 2, -top - 4 * h, 1.4 * h)
    s.text(f"{col.name} — {t('column')}", -N / 2, -top - 6 * h)

    # ------------------------------------------------------------ elevation view
    y0 = -top - 14 * h - max(s.u(bp.hef), pB / 2)
    hef = s.u(bp.hef) if bp.hef else 12 * d_rod
    stub = s.u(opt.column_stub) if opt.column_stub else 1.2 * s.u(col.d)
    conc_depth = hef + 4 * h
    s.rect(-pN / 2, y0 - conc_depth, pN / 2, y0, "BP-CONCRETO")
    s.rect(-N / 2, y0, N / 2, y0 + grout, "BP-CONCRETO")
    s.rect(-N / 2, y0 + grout, N / 2, y0 + grout + tp, "BP-PLACA")
    d, tf = s.u(col.d), s.u(col.tf)
    cy0 = y0 + grout + tp
    s.rect(-d / 2, cy0, -d / 2 + tf, cy0 + stub, "BP-COLUMNA")
    s.rect(d / 2 - tf, cy0, d / 2, cy0 + stub, "BP-COLUMNA")
    s.msp.add_line((-d / 2 + tf, cy0 + stub), (d / 2 - tf, cy0 + stub),
                   dxfattribs={"layer": "BP-COLUMNA"})
    if bp.shear_lug:
        lug = bp.shear_lug
        lug_w = s.u(lug.width if lug.direction in ("weak", "both") else lug.thickness)
        lug_bottom = y0 - s.u(lug.embedment)
        s.rect(-lug_w / 2, lug_bottom, lug_w / 2, y0 + grout, "BP-LLAVE")
        s.vdim(lug_bottom, y0, -lug_w / 2, -max(pN, N) / 2 - 9 * h)
        s.text(t("shear_lug"), -lug_w / 2, lug_bottom - 2 * h)
    proj = 3 * d_rod
    for x in sorted({x for x, _ in rods}):
        s.rect(x - d_rod / 2, y0 - hef, x + d_rod / 2, cy0 + proj, "BP-ANCLAJE")
        nut_h, nut_w = d_rod, 1.6 * d_rod
        s.rect(x - w_size / 2, cy0, x + w_size / 2, cy0 + w_t, "BP-ANCLAJE")
        s.rect(x - nut_w / 2, cy0 + w_t, x + nut_w / 2, cy0 + w_t + nut_h, "BP-ANCLAJE")
        s.rect(x - nut_w / 2, y0 - hef, x + nut_w / 2, y0 - hef + nut_h, "BP-ANCLAJE")
    s.msp.add_line((0, y0 - conc_depth - h), (0, cy0 + stub + h), dxfattribs={"layer": "BP-EJES"})
    s.hdim(-N / 2, N / 2, cy0 + stub, cy0 + stub + 3 * h)
    s.vdim(y0 + grout, cy0, -N / 2, -max(pN, N) / 2 - 3 * h)
    s.vdim(y0, y0 + grout, -N / 2, -max(pN, N) / 2 - 6 * h)
    xr = rods[-1][0]
    s.vdim(y0 - hef, y0, xr + d_rod, max(pN, N) / 2 + 4 * h)
    s.text(t("elevation"), -N / 2, y0 - conc_depth - 3 * h, 1.4 * h)

    # ----------------------------------------------------- bill of materials + notes
    plate_mass = bp.N * bp.B * bp.tp * STEEL_DENSITY
    rod_len = (bp.hef or 12 * bp.rod.diameter) + opt.grout + bp.tp + 3 * bp.rod.diameter
    rows = [
        (t("item"), t("qty"), t("description"), t("material"), t("weight")),
        ("1", "1", f"{t('base_plate')} {s.label(bp.tp)} × {s.label(bp.B)} × {s.label(bp.N)}",
         bp.plate_grade, f"{plate_mass:.1f} kg"),
        ("2", str(bp.rods), f"{t('anchor_rod')} Ø {s.label(bp.rod.diameter)} × "
         f"{s.label(rod_len)}", bp.rod.grade, ""),
        ("3", str(2 * bp.rods), f"{t('nut')} Ø {s.label(bp.rod.diameter)}", "ASTM A563", ""),
        ("4", "—", f"{t('holes')} Ø {s.label(anchor_hole(bp.rod.diameter))}", "", ""),
    ]
    washer = plate_washer(bp.rod.diameter, bp.washer_thickness)
    rows.append(("5", str(bp.rods), f"{t('washer')} {s.label(washer[1])} × {s.label(washer[0])}"
                 f" × {s.label(washer[0])}", bp.plate_grade, ""))
    if bp.shear_lug:
        lug = bp.shear_lug
        count = 2 if lug.direction == "both" else 1
        length = lug.grout + lug.embedment
        mass = lug.width * lug.thickness * length * STEEL_DENSITY * count
        rows.append((str(len(rows) + 1), str(count),
                     f"{t('shear_lug')} {s.label(lug.width)} × {s.label(lug.thickness)} × "
                     f"{s.label(length)}", lug.grade, f"{mass:.1f} kg"))
    widths = [3, 3, 26, 14, 8]
    bx = max(pN, N) / 2 + 14 * h
    by = top
    s.text(t("bom"), bx, by + 2 * h, 1.2 * h)
    for r, row in enumerate(rows):
        x = bx
        for w, cell in zip(widths, row, strict=True):
            s.rect(x, by - (r + 1) * 2 * h, x + w * h, by - r * 2 * h, "BP-TEXTO")
            s.text(cell, x + 0.3 * h, by - (r + 1) * 2 * h + 0.6 * h, 0.8 * h)
            x += w * h
    notes = [t("note_units", unit=s.unit), t("note_holes"), t("note_length")]
    if bp.flange_weld:
        notes.append(t("note_weld", size=s.label(bp.flange_weld)))
    if bp.shear_lug:
        notes.append(t("note_lug", size=s.label(bp.shear_lug.weld)))
    ny = by - (len(rows) + 2) * 2 * h
    s.text(t("notes"), bx, ny, 1.1 * h)
    for i, note in enumerate(notes, 1):
        s.text(f"{i}. {note}", bx, ny - i * 1.6 * h, 0.8 * h)

    # ------------------------------------------------------------- title block
    tb_y = ny - (len(notes) + 3) * 1.6 * h
    tb_w = sum(widths) * h
    s.rect(bx, tb_y - 8 * h, bx + tb_w, tb_y, "BP-TEXTO")
    s.text(opt.title or t("drawing_title"), bx + h, tb_y - 2 * h, 1.2 * h)
    s.text(f"{t('drawing_title')} — {col.name}", bx + h, tb_y - 4 * h, 0.9 * h)
    s.text(f"N° {opt.number}  Rev. {opt.revision}  {opt.date}", bx + h, tb_y - 6 * h, 0.9 * h)
    s.text("OpenConex", bx + tb_w - h, tb_y - 6 * h, 0.8 * h,
           align=TextEntityAlignment.RIGHT)

    path = Path(path)
    s.doc.saveas(path)
    return path

