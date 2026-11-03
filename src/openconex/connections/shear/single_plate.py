# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Conventional single-plate (shear tab) connection (AISC Manual Part 10, Table 10-9).

A plate shop-welded to the support with fillet welds on both faces and bolted
to the beam web with one vertical line of bolts (Design Example II.A-17A).
Limit states for the beam end reaction R:

* shear transfer at the bolt holes: C/n times the sum over the bolts of the
  least of bolt shear (single), plate bearing/tearout and beam web
  bearing/tearout (AISC 360-22 §J3.7 User Note, §J3.11). C is the instantaneous
  center coefficient for the eccentricity e = a/2 (Manual Table 10-9);
* shear yielding, shear rupture and block shear rupture of the plate (§J4);
* dimensional limits of the conventional configuration: t_p or t_w ≤ d/2 +
  1/16 in., l_eh ≥ 2d, l_ev per Table J3.4;
* weld size w ≥ 5/8 t_p (Manual Part 10) and the support thickness that
  develops the weld, t_min = 3.09 D / F_u (Manual Eq. 9-6).

The beam is taken uncoped; the bottom bolt is the edge bolt for plate tearout.
"""

from __future__ import annotations

from dataclasses import dataclass

from openconex.core.bolting import min_edge_distance
from openconex.core.checks import CheckResult
from openconex.core.loads import Method
from openconex.core.model import BoltSpec
from openconex.kernel import bolts, elements
from openconex.kernel.bolt_group import icr_coefficient
from openconex.kernel.bolts import clear_distance
from openconex.kernel.design import Calc
from openconex.units import Kind, from_internal, to_internal

from .double_angle import MANUAL, SPEC, _bearing_tearout, _hole_net

__all__ = ["SinglePlate", "check_single_plate"]


@dataclass(frozen=True)
class SinglePlate:
    bolt: BoltSpec
    rows: int
    spacing: float
    length: float
    thickness: float
    lev: float
    """Vertical edge distance of the plate (top and bottom)."""
    leh: float
    """Horizontal edge distance of the plate (bolt line to plate edge)."""
    a: float
    """Distance from the weld line (support face) to the bolt line."""
    plate_Fy: float
    plate_Fu: float
    beam_tw: float
    beam_Fu: float
    weld: float
    """Fillet weld size on each face of the plate."""
    support_t: float
    support_Fu: float
    deformation_considered: bool = True


def _result(sp, key: str, check: CheckResult) -> CheckResult:
    return check.model_copy(update={"id": f"single_plate.{key}",
                                    "text_id": f"check.single_plate.{key}"})


def _transfer(sp: SinglePlate, R: float, method: Method, combo: str) -> CheckResult:
    c = Calc(method, combo)
    clause = f"{SPEC} §J3.7, §J3.11; {MANUAL}, Table 10-9"
    b = sp.bolt
    shear = c.step(r"r_{n,bolt}", "", bolts.bolt_shear(b, 0.0, method).capacity, Kind.FORCE,
                   f"{SPEC} §J3.7")
    edge = clear_distance(b, sp.lev, to_edge=True)
    inner = clear_distance(b, sp.spacing, to_edge=False)
    plate_edge = c.step(r"r_{n,plate,edge}", r"\min(2.4dtF_u, 1.2l_ctF_u)",
                        _bearing_tearout(sp, sp.thickness, sp.plate_Fu, edge, method),
                        Kind.FORCE, f"{SPEC} §J3.11", l_c=(edge, Kind.LENGTH))
    plate_inner = c.step(r"r_{n,plate}", r"\min(2.4dtF_u, 1.2l_ctF_u)",
                         _bearing_tearout(sp, sp.thickness, sp.plate_Fu, inner, method),
                         Kind.FORCE, f"{SPEC} §J3.11", l_c=(inner, Kind.LENGTH))
    web = c.step(r"r_{n,web}", r"\min(2.4dtF_u, 1.2l_ctF_u)",
                 _bearing_tearout(sp, sp.beam_tw, sp.beam_Fu, inner, method), Kind.FORCE,
                 f"{SPEC} §J3.11", t=(sp.beam_tw, Kind.THICKNESS))
    rows = [min(shear, plate_edge if i == sp.rows - 1 else plate_inner, web)
            for i in range(sp.rows)]
    total = c.step(r"\sum r_{n,i}", "", sum(rows), Kind.FORCE, clause)
    e = c.step("e", "a/2", sp.a / 2, Kind.LENGTH, f"{MANUAL}, Table 10-9")
    group = [(0.0, sp.spacing * i) for i in range(sp.rows)]
    C = c.step("C", "IC", icr_coefficient(group, (e, sp.spacing * (sp.rows - 1) / 2)).C,
               clause=f"{MANUAL[:-8]}Part 7 (instantaneous center)")
    rn = c.step(r"\frac{C}{n}\sum r_{n,i}", "", C / sp.rows * total, Kind.FORCE, clause,
                n=(sp.rows, Kind.DIMENSIONLESS))
    return c.result("single_plate.bolts", clause, R, rn, Kind.FORCE)


def _limit(method: Method, combo: str, key: str, clause: str, symbol: str, expression: str,
           demand: float, capacity: float, kind: Kind) -> CheckResult:
    c = Calc(method, combo)
    c.step(symbol, expression, capacity, kind, clause)
    return c.result(f"single_plate.{key}", clause, demand, capacity, kind)


def check_single_plate(sp: SinglePlate, R: float, method: Method,
                       combo: str = "") -> list[CheckResult]:
    """All limit states of the connection for the beam end reaction ``R``."""
    t, hole, d = sp.thickness, _hole_net(sp.bolt), sp.bolt.diameter
    agv = (sp.length - sp.lev) * t
    block = elements.block_shear(agv, agv - (sp.rows - 0.5) * hole * t,
                                 (sp.leh - 0.5 * hole) * t, sp.plate_Fy, sp.plate_Fu, R,
                                 method, Ubs=1.0, combo=combo)
    sixteenths = from_internal(sp.weld, Kind.LENGTH, "in") * 16
    t_min = to_internal(3.09 * sixteenths / from_internal(sp.support_Fu, Kind.STRESS, "ksi"),
                        "in", Kind.LENGTH)
    d_in = from_internal(d, Kind.LENGTH, "in")
    return [
        _transfer(sp, R, method, combo),
        _result(sp, "shear_yielding", elements.shear_yielding(sp.length * t, sp.plate_Fy, R,
                                                             method, combo)),
        _result(sp, "shear_rupture", elements.shear_rupture(
            (sp.length - sp.rows * hole) * t, sp.plate_Fu, R, method, combo)),
        _result(sp, "block_shear", block),
        _limit(method, combo, "max_thickness", f"{MANUAL}, Table 10-9", r"d/2 + 1/16",
               r"t_p\ \mathrm{or}\ t_w \le d/2 + 1/16\ \mathrm{in.}",
               min(t, sp.beam_tw), d / 2 + to_internal(1 / 16, "in", Kind.LENGTH),
               Kind.THICKNESS),
        _limit(method, combo, "leh", f"{MANUAL}, Table 10-9", "2d", "l_{eh} \\ge 2d",
               2 * d, sp.leh, Kind.LENGTH),
        _limit(method, combo, "lev", f"{SPEC} Table J3.4", r"l_{ev,min}", "",
               min_edge_distance(d_in), sp.lev, Kind.LENGTH),
        _limit(method, combo, "weld_size", MANUAL, r"\frac{5}{8}t_p", "w \\ge 5t_p/8",
               5 * t / 8, sp.weld, Kind.THICKNESS),
        _limit(method, combo, "support_thickness", "AISC Manual 16th ed., Eq. 9-6",
               "t_{min}", r"\frac{3.09 D}{F_u}", t_min, sp.support_t, Kind.THICKNESS),
    ]
