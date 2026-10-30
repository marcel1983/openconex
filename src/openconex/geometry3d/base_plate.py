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
from openconex.drawing.base_plate import _rod_positions, anchor_hole, plate_washer

__all__ = ["Part", "base_plate_parts", "occ_available", "write_step", "write_stl"]


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
    flanges = [_box(sx * col.d / 2 - (col.tf if sx > 0 else 0), -col.bf / 2, z_top, col.tf,
                    col.bf, h) for sx in (-1, 1)]
    web = _box(-col.d / 2 + col.tf, -col.tw / 2, z_top, col.d - 2 * col.tf, col.tw, h)
    parts.append(Part("column", _fuse_all([*flanges, web])))
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
