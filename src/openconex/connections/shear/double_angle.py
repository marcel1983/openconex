# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""All-bolted double-angle shear connection (AISC Manual Part 10; Design Example II.A-1A).

Two angles bolted to the beam web (bolts in double shear) and to the support
(two bolts per row in single shear). The required strength is the beam end
reaction R. Limit states:

* shear transfer at the bolt holes on each side: the sum over the bolts of the
  least of bolt shear, angle bearing/tearout and beam web or support
  bearing/tearout (AISC 360-22 §J3.7 User Note, §J3.11);
* shear yielding and rupture of the angles (§J4.2);
* block shear rupture of the angles on each leg (§J4.3).

With ``support_weld`` > 0 the support legs are welded instead ("welds B",
Design Example II.A-2A): the bolt and block shear checks of the support side
are replaced by the strength of the two eccentric weld lines (instantaneous
center, e = width of the welded leg, as in Manual Table 10-2), the maximum
weld size for the angle thickness (§J2.2b) and the support thickness that
develops the welds (Manual Eq. 9-6).

With ``beam_weld`` > 0 the legs are welded to the beam web ("welds A",
Design Example II.A-3): each angle has a C-shaped weld (a vertical line at the
toe and two horizontal returns) loaded at the heel, solved by the
instantaneous center as in Manual Table 10-3. It replaces the bolt and block
shear checks of the beam side and adds the beam web thickness that develops
both welds, t_min = 6.19 D / F_u (Manual Eq. 9-3). With both sides welded the
angles have no holes.

The beam pushes the angles down at the beam web, so the bottom bolt is the
edge bolt for angle tearout there; at the support the angles bear up, so the
top bolt is the edge bolt. The beam web and the support are taken without a
cope or edge near the bolts (non-edge tearout only).
"""

from __future__ import annotations

from dataclasses import dataclass

from openconex.core.checks import CheckResult
from openconex.core.loads import Method
from openconex.core.model import BoltSpec
from openconex.kernel import bolts, elements
from openconex.kernel.bolts import clear_distance
from openconex.kernel.design import Calc
from openconex.kernel.weld_group import WeldLine, weld_group_eccentric
from openconex.units import Kind, from_internal, to_internal

__all__ = ["DoubleAngle", "check_double_angle"]

MANUAL = "AISC Manual 16th ed., Part 10"
SPEC = "AISC 360-22"


@dataclass(frozen=True)
class DoubleAngle:
    bolt: BoltSpec
    rows: int
    """Bolts in each vertical line."""
    spacing: float
    length: float
    """Angle length l."""
    thickness: float
    lev: float
    """Vertical edge distance of the angles (top and bottom)."""
    leh_beam: float
    """Horizontal edge distance on the leg bolted to the beam web."""
    leh_support: float
    angle_Fy: float
    angle_Fu: float
    beam_tw: float
    beam_Fu: float
    support_t: float
    """Thickness of the support (column flange or girder web)."""
    support_Fu: float
    deformation_considered: bool = True
    support_weld: float = 0.0
    """Fillet weld size of the legs welded to the support ("welds B"); 0 when bolted."""
    weld_e: float = 0.0
    """Eccentricity of the support welds: width of the leg welded to the support."""
    FEXX: float = to_internal(70.0, "ksi", Kind.STRESS)
    beam_weld: float = 0.0
    """Fillet weld size of the legs welded to the beam web ("welds A"); 0 when bolted."""
    beam_leg: float = 0.0
    """Width of the leg welded to the beam web (eccentricity of welds A)."""
    beam_weld_return: float | None = None
    """Length of the horizontal returns of welds A; defaults to ``beam_leg`` − 1/2 in."""


def _hole_net(bolt: BoltSpec) -> float:
    """Hole width plus 1/16 in. for net areas (AISC 360-22 §B4.3b)."""
    return bolt.hole_dimensions[0] + to_internal(1 / 16, "in", Kind.LENGTH)


def _bearing_tearout(da: DoubleAngle, t: float, Fu: float, lc: float, method: Method) -> float:
    kw = {"deformation_considered": da.deformation_considered}
    bearing = bolts.bolt_bearing(da.bolt, t, Fu, 0.0, method, **kw).capacity
    tearout = bolts.bolt_tearout(da.bolt, t, Fu, lc, 0.0, method, **kw).capacity
    return min(bearing, tearout)


def _transfer(da: DoubleAngle, R: float, method: Method, combo: str, side: str) -> CheckResult:
    """Shear transfer at the bolt holes of one leg (§J3.7 User Note)."""
    c = Calc(method, combo)
    clause = f"{SPEC} §J3.7, §J3.11; {MANUAL}"
    b = da.bolt
    shear = bolts.bolt_shear(b, 0.0, method).capacity
    edge = clear_distance(b, da.lev, to_edge=True)
    inner = clear_distance(b, da.spacing, to_edge=False)
    angle_edge = c.step(r"r_{n,angle,edge}", r"\min(2.4dtF_u, 1.2l_ctF_u)",
                        _bearing_tearout(da, da.thickness, da.angle_Fu, edge, method),
                        Kind.FORCE, f"{SPEC} §J3.11", l_c=(edge, Kind.LENGTH))
    angle_inner = c.step(r"r_{n,angle}", r"\min(2.4dtF_u, 1.2l_ctF_u)",
                         _bearing_tearout(da, da.thickness, da.angle_Fu, inner, method),
                         Kind.FORCE, f"{SPEC} §J3.11", l_c=(inner, Kind.LENGTH))
    if side == "beam":
        part = c.step(r"r_{n,web}", r"\min(2.4dtF_u, 1.2l_ctF_u)",
                      _bearing_tearout(da, da.beam_tw, da.beam_Fu, inner, method),
                      Kind.FORCE, f"{SPEC} §J3.11", t=(da.beam_tw, Kind.THICKNESS))
        bolt = c.step(r"2 r_{n,bolt}", "", 2 * shear, Kind.FORCE, f"{SPEC} §J3.7")
        edge_row, part_row = da.rows - 1, part  # bottom bolt is the edge bolt
    else:
        part = c.step(r"r_{n,support}", r"\min(2.4dtF_u, 1.2l_ctF_u)",
                      _bearing_tearout(da, da.support_t, da.support_Fu, inner, method),
                      Kind.FORCE, f"{SPEC} §J3.11", t=(da.support_t, Kind.THICKNESS))
        bolt = c.step(r"2 r_{n,bolt}", "", 2 * shear, Kind.FORCE, f"{SPEC} §J3.7")
        edge_row, part_row = 0, 2 * part  # top bolt; two bolts per row
    rows = [min(bolt, 2 * (angle_edge if i == edge_row else angle_inner), part_row)
            for i in range(da.rows)]
    rn = c.step(r"\sum r_{n,i}", "", sum(rows), Kind.FORCE, clause,
                n=(da.rows, Kind.DIMENSIONLESS))
    return c.result(f"double_angle.bolts_{side}", clause, R, rn, Kind.FORCE)


def _renamed(check: CheckResult, key: str) -> CheckResult:
    return check.model_copy(update={"id": f"double_angle.{key}",
                                    "text_id": f"check.double_angle.{key}"})


def _block_shear(da: DoubleAngle, leh: float, R: float, method: Method,
                 combo: str, key: str) -> CheckResult:
    hole, t = _hole_net(da.bolt), da.thickness
    agv = 2 * (da.length - da.lev) * t
    anv = agv - 2 * (da.rows - 0.5) * hole * t
    ant = 2 * (leh - 0.5 * hole) * t
    return _renamed(elements.block_shear(agv, anv, ant, da.angle_Fy, da.angle_Fu, R, method,
                                         Ubs=1.0, combo=combo), key)


def check_double_angle(da: DoubleAngle, R: float, method: Method,
                       combo: str = "") -> list[CheckResult]:
    """All limit states of the connection for the beam end reaction ``R``."""
    t, hole = da.thickness, _hole_net(da.bolt)
    agv = 2 * da.length * t
    holes = 0 if da.support_weld > 0 and da.beam_weld > 0 else da.rows
    anv = 2 * (da.length - holes * hole) * t
    if da.beam_weld > 0:
        beam = _beam_welds(da, R, method, combo)
    else:
        beam = [_transfer(da, R, method, combo, "beam"),
                _block_shear(da, da.leh_beam, R, method, combo, "block_shear_beam")]
    if da.support_weld > 0:
        support = _support_welds(da, R, method, combo)
    else:
        support = [_transfer(da, R, method, combo, "support"),
                   _block_shear(da, da.leh_support, R, method, combo, "block_shear_support")]
    return [
        beam[0],
        _renamed(elements.shear_yielding(agv, da.angle_Fy, R, method, combo),
                 "angle_shear_yielding"),
        _renamed(elements.shear_rupture(anv, da.angle_Fu, R, method, combo),
                 "angle_shear_rupture"),
        *beam[1:],
        *support,
    ]


def _beam_welds(da: DoubleAngle, R: float, method: Method, combo: str) -> list[CheckResult]:
    w, length = da.beam_weld, da.length
    kl = (da.beam_weld_return if da.beam_weld_return is not None
          else da.beam_leg - to_internal(0.5, "in", Kind.LENGTH))
    lines = [WeldLine(0.0, 0.0, 0.0, length), WeldLine(0.0, length, kl, length),
             WeldLine(0.0, 0.0, kl, 0.0)]
    # one angle; the reaction is shared by the two angles
    one = weld_group_eccentric(lines, w, da.FEXX, (da.beam_leg, length / 2), R / 2, method,
                               combo=combo)
    weld = one.model_copy(update={
        "id": "double_angle.weld_beam", "text_id": "check.double_angle.weld_beam",
        "demand": R, "capacity": 2 * one.capacity})
    sixteenth = to_internal(1 / 16, "in", Kind.LENGTH)
    c = Calc(method, combo)
    clause = "AISC Manual 16th ed., Eq. 9-3"
    t_min = c.step("t_{min}", r"\frac{6.19 D}{F_u}",
                   to_internal(6.19 * (w / sixteenth) / from_internal(da.beam_Fu, Kind.STRESS,
                                                                      "ksi"), "in", Kind.LENGTH),
                   Kind.THICKNESS, clause)
    web = c.result("double_angle.beam_web_thickness", clause, t_min, da.beam_tw,
                   Kind.THICKNESS)
    return [weld, web]


def _support_welds(da: DoubleAngle, R: float, method: Method, combo: str) -> list[CheckResult]:
    w, length = da.support_weld, da.length
    lines = [WeldLine(0.0, 0.0, 0.0, length), WeldLine(0.0, 0.0, 0.0, length)]
    weld = _renamed(weld_group_eccentric(lines, w, da.FEXX, (da.weld_e, length / 2), R, method,
                                         combo=combo), "weld_support")
    sixteenth = to_internal(1 / 16, "in", Kind.LENGTH)
    max_size = da.thickness if da.thickness < 4 * sixteenth else da.thickness - sixteenth
    c = Calc(method, combo)
    clause = f"{SPEC} §J2.2b"
    c.step("w_{max}", r"t - 1/16\ \mathrm{in.}", max_size, Kind.THICKNESS, clause)
    # w = t - 1/16 in. exactly is allowed; avoid a float round-off NG
    size = c.result("double_angle.weld_max_size", clause, w, max_size * (1 + 1e-9),
                    Kind.THICKNESS)
    c = Calc(method, combo)
    clause = "AISC Manual 16th ed., Eq. 9-6"
    D = w / sixteenth
    t_min = c.step("t_{min}", r"\frac{3.09 D}{F_u}",
                   to_internal(3.09 * D / from_internal(da.support_Fu, Kind.STRESS, "ksi"), "in",
                               Kind.LENGTH), Kind.THICKNESS, clause)
    support = c.result("double_angle.support_thickness", clause, t_min, da.support_t,
                       Kind.THICKNESS)
    return [weld, size, support]
