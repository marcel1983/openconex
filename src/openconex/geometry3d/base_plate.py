# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Solid model of a column base plate and STEP / STL export (optional extra ``3d``).

Coordinates in mm: x along N (strong-axis moment), y along B, z up; the top of
the concrete is z = 0. Each part is a separate solid in a compound.
"""

from __future__ import annotations

import contextlib
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from openconex.connections.base_plate.check import BasePlate
from openconex.core.model import HSSKind, HSSShape
from openconex.drawing.base_plate import _rod_positions, anchor_hole, plate_washer

__all__ = ["Part", "base_plate_parts", "embedded_base_parts", "isometric_svg",
           "occ_available", "write_step", "write_stl"]


def occ_available() -> bool:
    try:
        import OCP  # noqa: F401
    except ImportError:
        return False
    return True


@dataclass(frozen=True)
class Part:
    name: str
    shape: object
    """OCP TopoDS_Shape."""


def _require():
    if not occ_available():
        raise RuntimeError("3D output needs OpenCASCADE: pip install 'openconex[3d]'")


def _box(x0, y0, z0, dx, dy, dz):
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt
    return BRepPrimAPI_MakeBox(gp_Pnt(x0, y0, z0), dx, dy, dz).Shape()


def _cylinder(x, y, z0, r, h):
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
    return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x, y, z0), gp_Dir(0, 0, 1)), r, h).Shape()


def _hex_nut(x, y, z0, across_flats, h, hole):
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCP.gp import gp_Pnt, gp_Vec
    r = across_flats / math.sqrt(3)
    poly = BRepBuilderAPI_MakePolygon()
    for k in range(6):
        a = math.radians(60 * k)
        poly.Add(gp_Pnt(x + r * math.cos(a), y + r * math.sin(a), z0))
    poly.Close()
    prism = BRepPrimAPI_MakePrism(BRepBuilderAPI_MakeFace(poly.Wire()).Face(),
                                  gp_Vec(0, 0, h)).Shape()
    return BRepAlgoAPI_Cut(prism, _cylinder(x, y, z0 - 1, hole / 2, h + 2)).Shape()


def _cut_all(shape, tools):
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
    for tool in tools:
        shape = BRepAlgoAPI_Cut(shape, tool).Shape()
    return shape


def _fuse_all(shapes):
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse
    out = shapes[0]
    for s in shapes[1:]:
        out = BRepAlgoAPI_Fuse(out, s).Shape()
    return out


def base_plate_parts(bp: BasePlate, grout: float = 38.1, pedestal_N: float | None = None,
                     pedestal_B: float | None = None, column_height: float | None = None
                     ) -> list[Part]:
    _require()
    col = bp.column
    rods = _rod_positions(bp)
    d = bp.rod.diameter
    hole = anchor_hole(d)
    hef = bp.hef or 12 * d
    z_plate = grout
    z_top = grout + bp.tp
    pn, pb = pedestal_N or bp.N + 300, pedestal_B or bp.B + 300
    parts = [
        Part("pedestal", _box(-pn / 2, -pb / 2, -(hef + 150), pn, pb, hef + 150)),
        Part("grout", _box(-bp.N / 2, -bp.B / 2, 0, bp.N, bp.B, grout)),
        Part("base_plate", _cut_all(_box(-bp.N / 2, -bp.B / 2, z_plate, bp.N, bp.B, bp.tp),
                                    [_cylinder(x, y, z_plate - 1, hole / 2, bp.tp + 2)
                                     for x, y in rods])),
    ]
    h = column_height or 1.5 * col.d
    if isinstance(col, HSSShape):
        if col.kind is HSSKind.ROUND:
            outer = _cylinder(0, 0, z_top, col.d / 2, h)
            inner = _cylinder(0, 0, z_top - 1, col.d / 2 - col.t, h + 2)
        else:
            outer = _box(-col.d / 2, -col.bf / 2, z_top, col.d, col.bf, h)
            inner = _box(-col.d / 2 + col.t, -col.bf / 2 + col.t, z_top - 1,
                         col.d - 2 * col.t, col.bf - 2 * col.t, h + 2)
        column = _cut_all(outer, [inner])
    else:
        flanges = [_box(sx * col.d / 2 - (col.tf if sx > 0 else 0), -col.bf / 2, z_top,
                        col.tf, col.bf, h) for sx in (-1, 1)]
        web = _box(-col.d / 2 + col.tf, -col.tw / 2, z_top, col.d - 2 * col.tf, col.tw, h)
        column = _fuse_all([*flanges, web])
    parts.append(Part("column", column))
    if bp.shear_lug:
        lug = bp.shear_lug
        h_lug = grout + lug.embedment
        boxes = []
        if lug.direction in ("strong", "both"):
            boxes.append(_box(-lug.thickness / 2, -lug.width / 2, z_plate - h_lug,
                              lug.thickness, lug.width, h_lug))
        if lug.direction in ("weak", "both"):
            boxes.append(_box(-lug.width / 2, -lug.thickness / 2, z_plate - h_lug,
                              lug.width, lug.thickness, h_lug))
        parts.append(Part("shear_lug", _fuse_all(boxes)))
    af = 1.5 * d + 3.175  # heavy hex nut, across flats = 1.5d + 1/8 in.
    w_size, w_t = plate_washer(d, bp.washer_thickness)
    for i, (x, y) in enumerate(rods, 1):
        parts.append(Part(f"anchor_rod_{i}", _cylinder(x, y, -hef, d / 2, hef + z_top + 3 * d)))
        washer = _cut_all(_box(x - w_size / 2, y - w_size / 2, z_top, w_size, w_size, w_t),
                          [_cylinder(x, y, z_top - 1, (d + 1.5875) / 2, w_t + 2)])
        parts.append(Part(f"washer_{i}", washer))
        parts.append(Part(f"nut_top_{i}", _hex_nut(x, y, z_top + w_t, af, d, d)))
        parts.append(Part(f"nut_embedded_{i}", _hex_nut(x, y, -hef, af, d, d)))
    return parts


def embedded_base_parts(bp: BasePlate, foundation_length: float | None = None,
                        foundation_depth: float | None = None,
                        column_height: float | None = None) -> list[Part]:
    """Solids of a Type I embedded base: foundation, column and face plates."""
    _require()
    embedded = bp.embedded_base
    col = bp.column
    fw = embedded.foundation_width
    fl = foundation_length or fw
    depth = foundation_depth or embedded.embedment + 304.8
    h = column_height or 1.5 * col.d
    z0 = -embedded.embedment
    parts = [Part("foundation", _box(-fw / 2, -fl / 2, -depth, fw, fl, depth))]
    if isinstance(col, HSSShape):
        if col.kind is HSSKind.ROUND:
            outer = _cylinder(0, 0, z0, col.d / 2, embedded.embedment + h)
            inner = _cylinder(0, 0, z0 - 1, col.d / 2 - col.t, embedded.embedment + h + 2)
        else:
            outer = _box(-col.d / 2, -col.bf / 2, z0, col.d, col.bf, embedded.embedment + h)
            inner = _box(-col.d / 2 + col.t, -col.bf / 2 + col.t, z0 - 1,
                         col.d - 2 * col.t, col.bf - 2 * col.t,
                         embedded.embedment + h + 2)
        column = _cut_all(outer, [inner])
    else:
        flanges = [_box(sx * col.d / 2 - (col.tf if sx > 0 else 0), -col.bf / 2, z0,
                        col.tf, col.bf, embedded.embedment + h) for sx in (-1, 1)]
        web = _box(-col.d / 2 + col.tf, -col.tw / 2, z0,
                   col.d - 2 * col.tf, col.tw, embedded.embedment + h)
        column = _fuse_all([*flanges, web])
    parts.append(Part("column", column))
    if embedded.base_plate_width is not None:
        width = embedded.base_plate_width
        parts.append(Part("embedded_base_plate", _box(
            -width / 2, -width / 2, z0 - embedded.base_plate_thickness, width, width,
            embedded.base_plate_thickness)))
    tp = embedded.face_plate_thickness
    x0, x1 = -col.d / 2 + col.tf, col.d / 2 - col.tf
    # Face bearing plates bear on the top of the foundation (DG1 §5.3).
    parts.append(Part("face_plate_front", _box(
        x0, col.tw / 2, 0.0, x1 - x0, (col.bf - col.tw) / 2, tp)))
    parts.append(Part("face_plate_back", _box(
        x0, -col.bf / 2, 0.0, x1 - x0, (col.bf - col.tw) / 2, tp)))
    return parts


def _projected_edges(shape) -> list[list[tuple[float, float]]]:
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.GCPnts import GCPnts_QuasiUniformDeflection
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    lines = []
    explorer = TopExp_Explorer(shape, TopAbs_EDGE)
    while explorer.More():
        curve = BRepAdaptor_Curve(TopoDS.Edge(explorer.Current()))
        discretizer = GCPnts_QuasiUniformDeflection(curve, 0.8)
        if discretizer.IsDone() and discretizer.NbPoints() >= 2:
            lines.append([(discretizer.Value(i).X(), discretizer.Value(i).Y())
                          for i in range(1, discretizer.NbPoints() + 1)])
        explorer.Next()
    return lines


def isometric_svg(parts: list[Part], width: float = 210, height: float = 150) -> str:
    """Vector isometric view of the 3D parts with hidden-line removal."""
    _require()
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
    from OCP.HLRAlgo import HLRAlgo_Projector
    from OCP.HLRBRep import HLRBRep_Algo, HLRBRep_HLRToShape

    algo = HLRBRep_Algo()
    for part in parts:
        algo.Add(part.shape)
    # Keep the world Z axis (the column) vertical on the sheet: the projection
    # plane X axis must be horizontal.
    projector = HLRAlgo_Projector(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(1, 1, 1),
                                         gp_Dir(-1, 1, 0)))
    algo.Projector(projector)
    algo.Update()
    algo.Hide()
    hlr = HLRBRep_HLRToShape(algo)
    groups = (
        (False, (hlr.VCompound(), hlr.OutLineVCompound(), hlr.Rg1LineVCompound())),
        (True, (hlr.HCompound(), hlr.OutLineHCompound(), hlr.Rg1LineHCompound())),
    )
    lines: list[tuple[bool, list[tuple[float, float]]]] = []
    for hidden, shapes in groups:
        for shape in shapes:
            if shape is not None:
                lines += [(hidden, line) for line in _projected_edges(shape)]
    if not lines:
        return ""
    points = [point for _, line in lines for point in line]
    min_x = min(point[0] for point in points)
    max_x = max(point[0] for point in points)
    min_y = min(point[1] for point in points)
    max_y = max(point[1] for point in points)
    pad = 6.0
    scale = min((width - 2 * pad) / max(max_x - min_x, 1e-9),
                (height - 2 * pad) / max(max_y - min_y, 1e-9))
    x0 = pad + ((width - 2 * pad) - (max_x - min_x) * scale) / 2
    y0 = pad + ((height - 2 * pad) - (max_y - min_y) * scale) / 2

    def point(xy: tuple[float, float]) -> str:
        x, y = xy
        return f"{x0 + (x - min_x) * scale:.2f},{height - y0 - (y - min_y) * scale:.2f}"

    body = []
    for hidden, line in lines:
        style = ' class="hidden"' if hidden else ' class="visible"'
        body.append(f'<polyline{style} points="{" ".join(point(p) for p in line)}"/>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}mm" '
            f'height="{height}mm" viewBox="0 0 {width} {height}">'
            '<style>.visible{fill:none;stroke:#1b1f24;stroke-width:0.35}'
            '.hidden{fill:none;stroke:#9aa3ad;stroke-width:0.18;'
            'stroke-dasharray:1.2 1.2}</style>' + "".join(body) + "</svg>")


@contextlib.contextmanager
def _quiet():
    """Silence the OpenCASCADE writers, which print statistics to stdout."""
    sys.stdout.flush()
    saved = os.dup(1)
    with open(os.devnull, "w") as devnull:
        os.dup2(devnull.fileno(), 1)
        try:
            yield
        finally:
            os.dup2(saved, 1)
            os.close(saved)


def _compound(parts: list[Part]):
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Compound
    builder, comp = BRep_Builder(), TopoDS_Compound()
    builder.MakeCompound(comp)
    for p in parts:
        builder.Add(comp, p.shape)
    return comp


def write_step(parts: list[Part], path: str | Path) -> Path:
    _require()
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.Interface import Interface_Static
    from OCP.STEPControl import STEPControl_AsIs, STEPControl_Writer
    Interface_Static.SetCVal_s("write.step.unit", "MM")
    writer = STEPControl_Writer()
    path = Path(path)
    with _quiet():
        writer.Transfer(_compound(parts), STEPControl_AsIs)
        status = writer.Write(str(path))
    if status != IFSelect_RetDone:
        raise RuntimeError(f"could not write {path}")
    return path


def write_stl(parts: list[Part], path: str | Path, deflection: float = 0.5) -> Path:
    _require()
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.StlAPI import StlAPI_Writer
    shape = _compound(parts)
    BRepMesh_IncrementalMesh(shape, deflection)
    path = Path(path)
    if not StlAPI_Writer().Write(shape, str(path)):
        raise RuntimeError(f"could not write {path}")
    return path
