# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Solid model of a bolted beam or column splice (optional extra ``3d``).

Built from :func:`openconex.drawing.splice.splice_layout` (x along the member,
y across the depth, z across the flanges) and rotated so that the vertical is
z: the beam lies along x with its web vertical and the column stands along z.
"""

from __future__ import annotations

from openconex.connections.splice.splice import BeamSplice, ColumnSplice
from openconex.drawing.splice import splice_layout

from .base_plate import Part, _box, _fuse_all, _require
from .moment import _cylinder_y
from .shear import _cylinder_z

__all__ = ["splice_parts"]


def _transform(shape, column: bool):
    """Beam: y (depth) up. Column: x (member axis) up."""
    import math

    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf
    transform = gp_Trsf()
    if column:
        transform.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 1, 0)), -math.pi / 2)
    else:
        transform.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(1, 0, 0)), math.pi / 2)
    return BRepBuilderAPI_Transform(shape, transform, True).Shape()


def _solid(b):
    return _box(b.x0, b.y0, b.z0, b.x1 - b.x0, b.y1 - b.y0, b.z1 - b.z0)


def splice_parts(sp: BeamSplice | ColumnSplice) -> list[Part]:
    """Members, splice plates, fillers and bolts."""
    _require()
    lay = splice_layout(sp)
    parts: list[Part] = []
    for name in ("member_1", "member_2"):
        boxes = [b for b in lay.members if b.name.startswith(name)]
        parts.append(Part(name, _fuse_all([_solid(b) for b in boxes])))
    parts += [Part(b.name, _solid(b)) for b in lay.plates + lay.fillers]
    r = lay.flange_bolt_diameter / 2
    for i, (x, z, y0, y1) in enumerate(lay.flange_bolts):
        parts.append(Part(f"flange_bolt{i + 1}", _cylinder_y(x, y0 - r, z, r, y1 - y0 + 2 * r)))
    r = lay.web_bolt_diameter / 2
    for i, (x, y, z0, z1) in enumerate(lay.web_bolts):
        parts.append(Part(f"web_bolt{i + 1}", _cylinder_z(x, y, z0 - r, r, z1 - z0 + 2 * r)))
    return [Part(p.name, _transform(p.shape, lay.column)) for p in parts]
