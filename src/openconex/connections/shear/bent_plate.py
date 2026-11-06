# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Skewed double bent-plate shear connection (AISC Manual Part 10; II.A-10).

Two bent plates, one on each face of the supported beam web, are welded to
that web and bolted to the support web. The skew between the beam and the
support is absorbed by the bends, so the two vertical bolt rows are separated
along the beam. The beam end reaction is split between the plates by a simple
beam analogy between the two bolt rows:

* plate A carries ``R * e_B / g`` and plate B carries the remainder, where
  ``g`` is the distance between the rows and ``e_B`` is the distance from the
  load line to row B (AISC Design Example II.A-10);
* each plate is checked for bolt shear, bearing and tearout in the plate and
  the support, shear yielding and rupture, block shear, and its C-shaped weld
  group to the beam web (instantaneous centre, Manual Table 8-8);
* the beam web is checked as the base metal of the weld (Manual Eq. 9-3) and
  the plate thickness is checked against the maximum fillet weld size
  (AISC 360-22 §J2.2b).

The bent geometry is represented by two equivalent rectangles (one per plate)
in this phase; the plan view, the 3D bent solid and the GUI editor are later
work. The load split is an explicit statics hypothesis, not a stiffness
analysis.
"""

from __future__ import annotations

from dataclasses import dataclass

from openconex.core.checks import CheckResult
from openconex.core.loads import Method
from openconex.core.model import BoltSpec
from openconex.kernel import bolts, elements
from openconex.kernel.bolts import clear_distance
from openconex.kernel.design import WELD, Calc
from openconex.kernel.weld_group import WeldLine, electrode_coefficient, icr_strength
from openconex.units import Kind, from_internal, to_internal

from .double_angle import MANUAL, SPEC, _bearing_tearout, _hole_net

__all__ = ["BentPlate", "SkewedBentPlate", "check_bent_plate", "check_skewed_bent_plate"]

PART8 = "AISC Manual 16th ed., Part 8"


@dataclass(frozen=True)
class BentPlate:
    """One bent plate: geometry, bolts and C-shaped weld to the beam web."""

    thickness: float
    plate_Fy: float
    plate_Fu: float
    length: float
    """Vertical plate length and weld length l."""
    width: float
    """Plate width across the beam (informational in this phase)."""
    rows: int
    spacing: float
    lev: float
    leh: float
    bolt: BoltSpec
    weld: float
    """Fillet weld size."""
    weld_return: float
    """Length kl of the top and bottom weld returns."""
    weld_offset: float
    """Distance from the vertical weld line to the line of action of the load."""
    FEXX: float
    beam_tw: float
    beam_Fu: float
    support_t: float
    support_Fu: float
    deformation_considered: bool = True


@dataclass(frozen=True)
class SkewedBentPlate:
    """The two bent plates and the statics split of the beam end reaction."""

    plate_a: BentPlate
    plate_b: BentPlate
    share_a: float = 0.375
    skew: str = ""
    """Skew as written in the project (e.g. ``6:12``); informational."""

    def __post_init__(self) -> None:
        if not 0.0 < self.share_a < 1.0:
            raise ValueError("share_a must be between 0 and 1")

    @property
    def share_b(self) -> float:
        return 1.0 - self.share_a


def _rename(check: CheckResult, key: str) -> CheckResult:
    return check.model_copy(update={"id": key, "text_id": f"check.{key}"})


def _bolts(bp: BentPlate, R: float, method: Method, combo: str,
           label: str) -> CheckResult:
    """Bolt group of one plate: shear, plate bearing/tearout and support bearing."""
    c = Calc(method, combo)
    clause = f"{SPEC} §J3.7, §J3.11; {MANUAL}, Tables 7-1, 7-4 and 7-5"
    b = bp.bolt
    shear = c.step(r"r_{n,bolt}", "", bolts.bolt_shear(b, 0.0, method).capacity,
                   Kind.FORCE, f"{SPEC} §J3.7")
    edge = clear_distance(b, bp.lev, to_edge=True)
    inner = clear_distance(b, bp.spacing, to_edge=False)
    plate_edge = c.step(r"r_{n,plate,edge}", r"\min(2.4dtF_u, 1.2l_ctF_u)",
                        _bearing_tearout(bp, bp.thickness, bp.plate_Fu, edge, method),
                        Kind.FORCE, f"{SPEC} §J3.11", l_c=(edge, Kind.LENGTH),
                        t=(bp.thickness, Kind.THICKNESS))
    plate_inner = c.step(r"r_{n,plate}", r"\min(2.4dtF_u, 1.2l_ctF_u)",
                         _bearing_tearout(bp, bp.thickness, bp.plate_Fu, inner, method),
                         Kind.FORCE, f"{SPEC} §J3.11", l_c=(inner, Kind.LENGTH),
                         t=(bp.thickness, Kind.THICKNESS))
    # The support web is continuous in the direction of the load: no edge
    # tearout, only bearing (Manual Table 7-4).
    support = c.step(r"r_{n,support}", r"2.4dtF_u",
                     bolts.bolt_bearing(bp.bolt, bp.support_t, bp.support_Fu, 0.0, method,
                                        deformation_considered=bp.deformation_considered)
                     .capacity, Kind.FORCE, f"{SPEC} §J3.11",
                     t=(bp.support_t, Kind.THICKNESS))
    edge_bolt = c.step(r"r_{n,edge}", r"\min", min(shear, plate_edge, support),
                       Kind.FORCE, clause)
    inner_bolt = c.step(r"r_{n,inner}", r"\min", min(shear, plate_inner, support),
                        Kind.FORCE, clause)
    total = c.step(r"\sum r_{n,i}", "", edge_bolt + (bp.rows - 1) * inner_bolt,
                   Kind.FORCE, clause, n=(bp.rows, Kind.DIMENSIONLESS))
    return c.result(f"skewed_bent_plate.{label}.bolts", clause, R, total, Kind.FORCE)


def _weld(bp: BentPlate, R: float, method: Method, combo: str,
          label: str) -> tuple[CheckResult, float]:
    """C-shaped weld group by the instantaneous centre (Manual Table 8-8)."""
    c = Calc(method, combo)
    clause = f"{SPEC} §J2.4(c); {PART8}, Table 8-8"
    lines = [
        WeldLine(0.0, 0.0, 0.0, bp.length),
        WeldLine(0.0, bp.length, bp.weld_return, bp.length),
        WeldLine(0.0, 0.0, bp.weld_return, 0.0),
    ]
    load = (bp.weld_offset, bp.length / 2)
    unit = to_internal(1 / 16, "in", Kind.LENGTH)
    E70 = to_internal(70.0, "ksi", Kind.STRESS)
    r70 = icr_strength(lines, unit, E70, load, angle=0).Rn
    C = c.step("C", r"R_{n,70}/l", r70 / bp.length, Kind.FORCE_PER_LENGTH, clause,
               l=(bp.length, Kind.LENGTH))
    c1 = c.step("C_1", "", electrode_coefficient(bp.FEXX), Kind.DIMENSIONLESS,
                "AISC Manual 16th ed., Table 8-3", F_EXX=(bp.FEXX, Kind.STRESS))
    if method is Method.LRFD:
        d_req = c.step("D_{req}", r"\frac{R}{\phi C C_1 l}", R / (WELD.phi * C * c1 * bp.length),
                       Kind.DIMENSIONLESS, clause)
    else:
        d_req = c.step("D_{req}", r"\frac{\Omega R}{C C_1 l}",
                       WELD.omega * R / (C * c1 * bp.length), Kind.DIMENSIONLESS, clause)
    D = c.step("D", "", from_internal(bp.weld, Kind.LENGTH, "in") * 16,
               Kind.DIMENSIONLESS, clause, w=(bp.weld, Kind.THICKNESS))
    rn = c.step("R_n", r"C C_1 D l", C * c1 * D * bp.length, Kind.FORCE, clause)
    capacity = c.available(rn, WELD, Kind.FORCE, clause)
    return c.result(f"skewed_bent_plate.{label}.weld", clause, R, capacity, Kind.FORCE), d_req


def _plate_checks(bp: BentPlate, R: float, method: Method, combo: str,
                  label: str) -> tuple[list[CheckResult], float]:
    t = bp.thickness
    hole = _hole_net(bp.bolt)
    agv = (bp.lev + (bp.rows - 1) * bp.spacing) * t
    anv = (bp.lev + (bp.rows - 1) * bp.spacing
           - (bp.rows - 0.5) * hole) * t
    ant = (bp.leh - 0.5 * hole) * t
    block = elements.block_shear(agv, anv, ant, bp.plate_Fy, bp.plate_Fu, R, method,
                                 Ubs=1.0, combo=combo)
    weld, d_req = _weld(bp, R, method, combo, label)
    return [
        _bolts(bp, R, method, combo, label),
        _rename(elements.shear_yielding(bp.length * t, bp.plate_Fy, R, method, combo),
                f"skewed_bent_plate.{label}.shear_yielding"),
        _rename(elements.shear_rupture((bp.length - bp.rows * hole) * t, bp.plate_Fu, R,
                                       method, combo),
                f"skewed_bent_plate.{label}.shear_rupture"),
        _rename(block, f"skewed_bent_plate.{label}.block_shear"),
        weld,
    ], d_req


def check_bent_plate(bp: BentPlate, R: float, method: Method, combo: str = "",
                     label: str = "plate_b") -> list[CheckResult]:
    """Limit states of one bent plate under its share ``R`` of the reaction."""
    return _plate_checks(bp, R, method, combo, label)[0]


def _beam_web_thickness(bp: BentPlate, D: float, method: Method,
                        combo: str) -> CheckResult:
    """Minimum beam web thickness for the required weld size (Manual Eq. 9-3)."""
    c = Calc(method, combo)
    clause = "AISC Manual 16th ed., Eq. 9-3"
    fu = from_internal(bp.beam_Fu, Kind.STRESS, "ksi")
    t_min = to_internal(6.19 * D / fu, "in", Kind.LENGTH)
    c.step("t_{min}", r"\frac{6.19 D}{F_u}", t_min, Kind.THICKNESS, clause,
           D=(D, Kind.DIMENSIONLESS), F_u=(bp.beam_Fu, Kind.STRESS))
    return c.result("skewed_bent_plate.beam_web_thickness", clause, t_min, bp.beam_tw,
                    Kind.THICKNESS)


def _plate_thickness(bp: BentPlate, method: Method, combo: str) -> CheckResult:
    """Plate thickness needed for the maximum fillet weld size (§J2.2b)."""
    c = Calc(method, combo)
    clause = f"{SPEC} §J2.2b"
    demand = bp.weld + to_internal(1 / 16, "in", Kind.LENGTH)
    c.step("t_{min}", r"w + 1/16\ \mathrm{in}", demand, Kind.THICKNESS, clause,
           w=(bp.weld, Kind.THICKNESS))
    return c.result("skewed_bent_plate.plate_thickness", clause, demand, bp.thickness,
                    Kind.THICKNESS)


def check_skewed_bent_plate(sbp: SkewedBentPlate, R: float, method: Method,
                            combo: str = "") -> list[CheckResult]:
    """All limit states of the skewed double bent-plate connection."""
    results_a, d_req_a = _plate_checks(sbp.plate_a, R * sbp.share_a, method, combo,
                                       "plate_a")
    results_b, d_req_b = _plate_checks(sbp.plate_b, R * sbp.share_b, method, combo,
                                       "plate_b")
    # Both plates have the same weld and beam web; use the larger required size.
    d_req = max(d_req_a, d_req_b)
    critical = sbp.plate_b if sbp.share_b >= sbp.share_a else sbp.plate_a
    return [
        *results_a,
        *results_b,
        _beam_web_thickness(critical, d_req, method, combo),
        _plate_thickness(critical, method, combo),
    ]
