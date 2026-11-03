# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Shear end-plate connection (AISC Manual Part 10; Design Example II.A-11A).

A plate shop-welded to the end of the beam web with two fillet welds and
bolted to the support with two bolts per row. Limit states for the beam end
reaction R:

* shear transfer at the bolt holes: sum over the rows of the least of two
  bolt shears, two plate bearing/tearout strengths (the top bolt is the edge
  bolt, the plate bears up) and two support bearing/tearout strengths
  (AISC 360-22 §J3.7 User Note, §J3.11);
* shear yielding and rupture of the plate on two planes, block shear (§J4);
* the two welds to the beam web, effective length l − 2w (§J2.4, longitudinal
  welds without directional increase), and the beam web thickness that
  develops them, t_min = 6.19 D / F_u (Manual Eq. 9-3).
"""

from __future__ import annotations

from dataclasses import dataclass

from openconex.core.checks import CheckResult
from openconex.core.loads import Method
from openconex.core.model import BoltSpec
from openconex.kernel import bolts, elements
from openconex.kernel.bolts import clear_distance
from openconex.kernel.design import Calc
from openconex.kernel.welds import fillet_weld_per_length
from openconex.units import Kind, from_internal, to_internal

from .double_angle import MANUAL, SPEC, _bearing_tearout, _hole_net

__all__ = ["EndPlate", "check_end_plate"]


@dataclass(frozen=True)
class EndPlate:
    bolt: BoltSpec
    rows: int
    """Rows of two bolts."""
    spacing: float
    length: float
    thickness: float
    lev: float
    leh: float
    """Horizontal edge distance from each bolt line to the plate edge."""
    plate_Fy: float
    plate_Fu: float
    weld: float
    """Fillet weld size on each side of the beam web."""
    beam_tw: float
    beam_Fu: float
    support_t: float
    support_Fu: float
    FEXX: float = to_internal(70.0, "ksi", Kind.STRESS)
    deformation_considered: bool = True


def _rename(key: str, check: CheckResult) -> CheckResult:
    return check.model_copy(update={"id": f"end_plate.{key}",
                                    "text_id": f"check.end_plate.{key}"})


def _transfer(ep: EndPlate, R: float, method: Method, combo: str) -> CheckResult:
    c = Calc(method, combo)
    clause = f"{SPEC} §J3.7, §J3.11; {MANUAL}"
    b = ep.bolt
    shear = c.step(r"2 r_{n,bolt}", "", 2 * bolts.bolt_shear(b, 0.0, method).capacity,
                   Kind.FORCE, f"{SPEC} §J3.7")
    edge = clear_distance(b, ep.lev, to_edge=True)
    inner = clear_distance(b, ep.spacing, to_edge=False)
    plate_edge = c.step(r"2 r_{n,plate,edge}", r"2\min(2.4dtF_u, 1.2l_ctF_u)",
                        2 * _bearing_tearout(ep, ep.thickness, ep.plate_Fu, edge, method),
                        Kind.FORCE, f"{SPEC} §J3.11", l_c=(edge, Kind.LENGTH))
    plate_inner = c.step(r"2 r_{n,plate}", r"2\min(2.4dtF_u, 1.2l_ctF_u)",
                         2 * _bearing_tearout(ep, ep.thickness, ep.plate_Fu, inner, method),
                         Kind.FORCE, f"{SPEC} §J3.11", l_c=(inner, Kind.LENGTH))
    support = c.step(r"2 r_{n,support}", r"2\min(2.4dtF_u, 1.2l_ctF_u)",
                     2 * _bearing_tearout(ep, ep.support_t, ep.support_Fu, inner, method),
                     Kind.FORCE, f"{SPEC} §J3.11", t=(ep.support_t, Kind.THICKNESS))
    rows = [min(shear, plate_edge if i == 0 else plate_inner, support)
            for i in range(ep.rows)]
    rn = c.step(r"\sum r_{n,i}", "", sum(rows), Kind.FORCE, clause,
                n=(ep.rows, Kind.DIMENSIONLESS))
    return c.result("end_plate.bolts", clause, R, rn, Kind.FORCE)


def check_end_plate(ep: EndPlate, R: float, method: Method,
                    combo: str = "") -> list[CheckResult]:
    """All limit states of the connection for the beam end reaction ``R``."""
    t, hole, n = ep.thickness, _hole_net(ep.bolt), ep.rows
    agv = 2 * (ep.length - ep.lev) * t
    block = elements.block_shear(agv, agv - 2 * (n - 0.5) * hole * t,
                                 2 * (ep.leh - 0.5 * hole) * t, ep.plate_Fy, ep.plate_Fu, R,
                                 method, Ubs=1.0, combo=combo)

    c = Calc(method, combo)
    clause = f"{SPEC} §J2.4"
    lw = c.step("l_w", "l - 2w", ep.length - 2 * ep.weld, Kind.LENGTH, clause)
    per_length = fillet_weld_per_length(ep.weld, ep.FEXX, 0.0, method).capacity
    rn = c.step(r"2 r_w l_w", "", 2 * per_length * lw, Kind.FORCE, clause,
                w=(ep.weld, Kind.THICKNESS))
    weld = c.result("end_plate.weld", clause, R, rn, Kind.FORCE)

    c = Calc(method, combo)
    clause = "AISC Manual 16th ed., Eq. 9-3"
    D = from_internal(ep.weld, Kind.LENGTH, "in") * 16
    t_min = c.step("t_{min}", r"\frac{6.19 D}{F_u}",
                   to_internal(6.19 * D / from_internal(ep.beam_Fu, Kind.STRESS, "ksi"), "in",
                               Kind.LENGTH), Kind.THICKNESS, clause)
    web = c.result("end_plate.beam_web_thickness", clause, t_min, ep.beam_tw, Kind.THICKNESS)
    return [
        _transfer(ep, R, method, combo),
        _rename("shear_yielding", elements.shear_yielding(2 * ep.length * t, ep.plate_Fy, R,
                                                          method, combo)),
        _rename("shear_rupture", elements.shear_rupture(2 * (ep.length - n * hole) * t,
                                                        ep.plate_Fu, R, method, combo)),
        _rename("block_shear", block),
        weld,
        web,
    ]
