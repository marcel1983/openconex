# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Solid model of a beam-end shear connection (optional extra ``3d``).

Same axes as the elevation drawing: x along the beam from the face of the
support, y up from the bottom of the beam, z across the web (web centered on
z = 0). Parts are simple prisms and cylinders; welds are not modeled.
"""

from __future__ import annotations

from openconex.connections.shear.bent_plate import SkewedBentPlate, parse_skew
from openconex.connections.shear.check import ShearConnection
from openconex.connections.shear.double_angle import DoubleAngle
from openconex.connections.shear.end_plate import EndPlate
from openconex.connections.shear.seated import SeatedAngle
from openconex.connections.shear.stiffened_seat import StiffenedSeat, seat_plate_width
from openconex.drawing.shear import INCH, shear_layout

from .base_plate import Part, _box, _cut_all, _fuse_all, _require

__all__ = ["shear_parts"]


def _cylinder_x(x0, y, z, r, h):
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
    return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x0, y, z), gp_Dir(1, 0, 0)), r, h).Shape()


def _cylinder_z(x, y, z0, r, h):
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
    return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x, y, z0), gp_Dir(0, 0, 1)), r, h).Shape()


def _rotate_y(shape, angle: float):
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf
    transform = gp_Trsf()
    transform.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 1, 0)), angle)
    return BRepBuilderAPI_Transform(shape, transform, True).Shape()


def _bent_plate_parts(conn: ShearConnection, el: SkewedBentPlate, *,
                      context: str | None = None) -> list[Part]:
    """Schematic solid model of the skewed double bent plate (phase 2)."""
    beam, support = conn.beam, conn.support
    assert beam is not None
    d, tf, bf, tw = beam.d, beam.tf, beam.bf, beam.tw
    a, b = el.plate_a, el.plate_b
    t = a.thickness
    height = a.length
    y0 = d / 2 - height / 2
    alpha = parse_skew(el.skew)
    leg_a = a.leg_beam or a.width * 0.6
    leg_b = b.leg_beam or b.width * 0.6
    length = max(leg_a, leg_b) + 2 * INCH
    support_t = support.tw if support is not None and conn.support_element == "web" else (
        support.tf if support is not None else 0.25 * INCH)
    support_width = max(2 * max(a.width, b.width), 12 * INCH)
    parts: list[Part] = []

    section = _fuse_all([
        _box(0.0, 0.0, -bf / 2, length, tf, bf),
        _box(0.0, d - tf, -bf / 2, length, tf, bf),
        _box(0.0, tf, -tw / 2, length, d - 2 * tf, tw),
    ])
    parts.append(Part("beam", _rotate_y(section, alpha)))
    parts.append(Part("support", _box(-support_t, 0.0, -support_width / 2, support_t, d,
                                      support_width)))
    if context:
        member = _support_context(conn, -4 * INCH, d + 4 * INCH, support_t,
                                  support_width, context)
        if member is not None:
            parts.append(member)

    for name, plate, sign, leg in (("a", a, 1, leg_a), ("b", b, -1, leg_b)):
        z = sign * tw / 2
        bolted = _box(0.0, y0, z if sign > 0 else z - plate.width, t, height, plate.width)
        welded = _rotate_y(_box(0.0, y0, z if sign > 0 else z - t, leg, height, t), alpha)
        parts.append(Part(f"bent_plate_{name}", _fuse_all([bolted, welded])))

    r = a.bolt.diameter / 2
    row = el.row_distance or 6 * INCH
    if el.load_offset > 0:
        row_a, row_b = row - el.load_offset, el.load_offset
    else:
        row_a, row_b = (1 - el.share_a) * row, el.share_a * row
    rows = a.rows
    for name, plate, sign in (("a", a, 1), ("b", b, -1)):
        z = row_a if sign > 0 else -row_b
        for i in range(rows):
            y = y0 + (height - 2 * plate.lev - (rows - 1) * plate.spacing) / 2 \
                + plate.lev + i * plate.spacing
            parts.append(Part(f"bolt_{name}{i + 1}",
                              _cylinder_x(-support_t - r, y, z, r,
                                          support_t + t + 2 * r)))
    return parts


def _support_context(conn: ShearConnection, lo: float, hi: float, t_sup: float,
                     sup_w: float, kind: str) -> Part | None:
    """Supporting member behind the connection face, for gallery art only.

    The shear model draws the support as a thin plate because the calculation
    only needs the local thickness.  A prism gives the thumbnails the context
    of a column (``kind="column"``) or of a supporting girder
    (``kind="beam"``) without changing the exported connection geometry:
    ``context`` is off by default.
    """
    support = conn.support
    if support is None:
        return None
    depth = max(support.bf, 12 * INCH)
    if kind == "column":
        return Part("support_context", _box(-depth, lo, -sup_w / 2, depth,
                                            hi - lo, sup_w))
    flange = max(support.tf, 0.25 * INCH)
    length = max(3 * sup_w, 36 * INCH)
    body = _box(-depth, lo, -length / 2, depth - t_sup, hi - lo, length)
    top = _box(-depth, hi - flange / 2, -length / 2, depth, flange, length)
    bottom = _box(-depth, lo - flange / 2, -length / 2, depth, flange, length)
    return Part("support_context", _fuse_all([body, top, bottom]))


def shear_parts(conn: ShearConnection, *, context: str | None = None) -> list[Part]:
    """Beam, support, connecting elements and bolts as OCP solids."""
    _require()
    if isinstance(conn.element, SkewedBentPlate):
        return _bent_plate_parts(conn, conn.element, context=context)
    lay = shear_layout(conn)
    beam, el = conn.beam, conn.element
    assert beam is not None
    d, tf, tw, bf = beam.d, beam.tf, beam.tw, beam.bf
    x0, length = lay.beam_start, lay.beam_length
    parts: list[Part] = []
    # beam with copes
    shape = _fuse_all([_box(x0, 0, -bf / 2, length, tf, bf),
                       _box(x0, d - tf, -bf / 2, length, tf, bf),
                       _box(x0, tf, -tw / 2, length, d - 2 * tf, tw)])
    cuts = []
    if lay.cope_top:
        c, dc = lay.cope_top
        cuts.append(_box(x0 - 1, d - dc, -bf, c + 1, dc + 1, 2 * bf))
    if lay.cope_bottom:
        c, dc = lay.cope_bottom
        cuts.append(_box(x0 - 1, -1, -bf, c + 1, dc + 1, 2 * bf))
    parts.append(Part("beam", _cut_all(shape, cuts)))
    # support (flange or web seen as a plate)
    ys = [y for p in lay.plates for y in (p[1], p[3])] + [0.0, d]
    lo, hi = min(ys) - 4 * INCH, max(ys) + 4 * INCH
    sup_w = conn.support.bf if conn.support is not None and conn.support_element == "flange" \
        else max(bf, 12 * INCH)
    t_sup = max(lay.support_t, INCH / 4)
    parts.append(Part("support", _box(-t_sup, lo, -sup_w / 2, t_sup, hi - lo, sup_w)))
    if context:
        member = _support_context(conn, lo, hi, t_sup, sup_w, context)
        if member is not None:
            parts.append(member)
    # connecting elements
    t = lay.plate_thickness
    side = tw / 2
    for x_0, y_0, x_1, y_1, name in lay.plates:
        w, h = x_1 - x_0, y_1 - y_0
        if isinstance(el, DoubleAngle):
            out = (el.weld_e or 3.5 * INCH)
            for sign in (1, -1):
                z = side if sign > 0 else -side - t
                leg = _box(x_0, y_0, z, w, h, t)
                outstanding = _box(x_0, y_0, side if sign > 0 else -side - out, t, h, out)
                parts.append(Part(f"angle{'+' if sign > 0 else '-'}",
                                  _fuse_all([leg, outstanding])))
        elif isinstance(el, EndPlate):
            width = 2 * el.leh + 5.5 * INCH
            parts.append(Part(name, _box(x_0, y_0, -width / 2, w, h, width)))
        elif isinstance(el, SeatedAngle):
            width = el.top_angle_length if name == "top_angle" else el.length
            parts.append(Part(name, _box(x_0, y_0, -width / 2, w, h, width)))
        elif isinstance(el, StiffenedSeat):
            if name == "seat":
                width = seat_plate_width(el)
                parts.append(Part(name, _box(x_0, y_0, -width / 2, w, h, width)))
            elif name == "top_angle":
                width = el.top_angle_length
                parts.append(Part(name, _box(x_0, y_0, -width / 2, w, h, width)))
            else:
                parts.append(Part(name, _box(x_0, y_0, -t / 2, w, h, t)))
        else:
            parts.append(Part(name, _box(x_0, y_0, side, w, h, t)))
    if conn.cope is not None:
        doubler = conn.cope.doubler
        if lay.cope_doubler is not None and doubler is not None:
            x_0, y_0, x_1, y_1 = lay.cope_doubler
            parts.append(Part("doubler", _box(x_0, y_0, side, x_1 - x_0,
                                              y_1 - y_0, doubler.thickness)))
        stiffener = conn.cope.stiffener
        if lay.cope_stiffener is not None and stiffener is not None:
            x_0, y_0, x_1, y_1 = lay.cope_stiffener
            width = stiffener.width
            parts.append(Part("stiffener", _box(x_0, y_0, -width / 2, x_1 - x_0,
                                                y_1 - y_0, width)))
    # bolts
    r = lay.bolt_diameter / 2 if lay.bolt_diameter else 0.375 * INCH
    grip = tw + 2 * t + 2 * r
    for i, (x, y) in enumerate(lay.bolts):
        parts.append(Part(f"bolt{i + 1}", _cylinder_z(x, y, -grip / 2 - r, r, grip + 2 * r)))
    gage = 5.5 * INCH if isinstance(el, (EndPlate, DoubleAngle)) else 0.0
    for i, y in enumerate(lay.support_bolts):
        for j, z in enumerate((-gage / 2, gage / 2) if gage else (0.0,)):
            parts.append(Part(f"support_bolt{i + 1}{'ab'[j]}",
                              _cylinder_x(-t_sup - r, y, z, r, t_sup + t + 3 * r)))
    return parts
