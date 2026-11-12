# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Solid model of a beam-to-column-flange moment connection (optional extra ``3d``).

Built in the axes of the elevation drawing (x along the beam from the column
flange face, y up from the bottom of the beam, z across the web) and rotated so
that the vertical is z, as in the base plate model. Welds are not modeled.
"""

from __future__ import annotations

from openconex.connections.moment.fr_moment import MomentConnection
from openconex.drawing.moment import moment_layout

from .base_plate import Part, _box, _fuse_all, _require
from .shear import _cylinder_z

__all__ = ["moment_parts"]


def _cylinder_y(x, y0, z, r, h):
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
    return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x, y0, z), gp_Dir(0, 1, 0)), r, h).Shape()


def _cylinder_x(x0, y, z, r, h):
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
    return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x0, y, z), gp_Dir(1, 0, 0)), r, h).Shape()


def _prism_z(points, z0, h):
    """Polygon in the x-y plane at z0 extruded by h along z."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCP.gp import gp_Pnt, gp_Vec
    poly = BRepBuilderAPI_MakePolygon()
    for x, y in points:
        poly.Add(gp_Pnt(x, y, z0))
    poly.Close()
    return BRepPrimAPI_MakePrism(BRepBuilderAPI_MakeFace(poly.Wire()).Face(),
                                 gp_Vec(0, 0, h)).Shape()


def _z_up(shape):
    """Rotate +90° about x so that the elevation y axis becomes the vertical z axis."""
    import math

    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf
    transform = gp_Trsf()
    transform.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(1, 0, 0)), math.pi / 2)
    return BRepBuilderAPI_Transform(shape, transform, True).Shape()


def moment_parts(mc: MomentConnection) -> list[Part]:
    """Beam, column, plates and bolts; z is vertical (as in the base plate model)."""
    return [Part(p.name, _z_up(p.shape)) for p in _parts(mc)]


def _parts(mc: MomentConnection) -> list[Part]:
    _require()
    lay = moment_layout(mc)
    beam, col = mc.beam, mc.column
    d, tf, tw, bf = beam.d, beam.tf, beam.tw, beam.bf
    length = lay.beam_length
    x0 = lay.beam_x0
    parts = [Part("beam", _fuse_all([_box(x0, 0, -bf / 2, length, tf, bf),
                                     _box(x0, d - tf, -bf / 2, length, tf, bf),
                                     _box(x0, tf, -tw / 2, length, d - 2 * tf, tw)]))]
    ys = [y for p in lay.plates for y in (p[1], p[3])] + [0.0, d]
    lo, hi = min(ys) - 150.0, max(ys) + 150.0
    cbf, ctf, ctw, cd = col.bf, col.tf, col.tw, col.d
    parts.append(Part("column", _fuse_all([
        _box(-ctf, lo, -cbf / 2, ctf, hi - lo, cbf),
        _box(-cd, lo, -cbf / 2, ctf, hi - lo, cbf),
        _box(-cd + ctf, lo, -ctw / 2, cd - 2 * ctf, hi - lo, ctw)])))
    ep = mc.end_plate
    if ep is not None and lay.end_plate_rows:
        x_0, y_0, x_1, y_1, _ = lay.plates[0]
        parts.append(Part("end_plate", _box(x_0, y_0, -ep.width / 2, x_1 - x_0, y_1 - y_0,
                                            ep.width)))
        ts = max(tw, ep.stiffener_thickness)
        for i, poly in enumerate(lay.stiffeners):
            if len(poly) == 3:  # triangular stiffener on the extension, in the web plane
                parts.append(Part(f"stiffener{i + 1}", _prism_z(poly, -ts / 2, ts)))
            else:  # horizontal stiffeners on both sides of the web
                (xa, ya), (xb, _), _, (_, yd) = poly
                for side, z in (("a", tw / 2), ("b", -bf / 2)):
                    parts.append(Part(f"stiffener{i + 1}{side}",
                                      _box(xa, yd, z, xb - xa, ya - yd, (bf - tw) / 2)))
        tcp = mc.continuity_plate
        if tcp > 0:
            width = (cbf - ctw) / 2
            for j, yc in enumerate((d - tf / 2, tf / 2)):
                for side, z in (("a", ctw / 2), ("b", -cbf / 2)):
                    parts.append(Part(f"continuity_plate{j + 1}{side}", _box(
                        -cd + ctf, yc - tcp / 2, z, cd - 2 * ctf, tcp, width)))
        r = ep.bolt.diameter / 2
        for i, y in enumerate(lay.end_plate_rows):
            for j, z in enumerate((-ep.gage / 2, ep.gage / 2)):
                parts.append(Part(f"bolt{i + 1}{'ab'[j]}", _cylinder_x(
                    -ctf - 2 * r, y, z, r, ctf + ep.thickness + 4 * r)))
        return parts
    w = mc.web
    x_0, y_0, x_1, y_1, _ = lay.plates[0]
    parts.append(Part("web_plate", _box(x_0, y_0, tw / 2, x_1 - x_0, y_1 - y_0, w.thickness)))
    for name, plate in (("top_plate", mc.top), ("bottom_plate", mc.bottom or mc.top)):
        rect = next((p for p in lay.plates if p[4] == name), None)
        if rect is None or plate is None:
            continue
        x_0, y_0, x_1, y_1, _ = rect
        parts.append(Part(name, _box(x_0, y_0, -plate.width / 2, x_1 - x_0, y_1 - y_0,
                                     plate.width)))
    r = lay.bolt_diameter / 2
    for i, (x, y) in enumerate(lay.web_bolts):
        parts.append(Part(f"web_bolt{i + 1}", _cylinder_z(x, y, -tw / 2 - 2 * r, r,
                                                          tw + w.thickness + 4 * r)))
    if mc.bolt is not None and lay.flange_bolts:
        rb = mc.bolt.diameter / 2
        top = next(p for p in lay.plates if p[4] == "top_plate")
        bottom = next(p for p in lay.plates if p[4] == "bottom_plate")
        for i, x in enumerate(lay.flange_bolts):
            for j, z in enumerate((-mc.gage / 2, mc.gage / 2)):
                parts.append(Part(f"flange_bolt_top{i + 1}{'ab'[j]}", _cylinder_y(
                    x, d - tf - 2 * rb, z, rb, top[3] - d + tf + 4 * rb)))
                parts.append(Part(f"flange_bolt_bottom{i + 1}{'ab'[j]}", _cylinder_y(
                    x, bottom[1] - 2 * rb, z, rb, tf - bottom[1] + 4 * rb)))
    return parts
