# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Unstiffened bolted seated connection (AISC Manual Part 10; Design Example II.A-12A).

The beam bears on the outstanding leg of a seat angle bolted to the support.
Limit states for the beam end reaction R:

* required bearing length for web local yielding and web local crippling of
  the beam (Manual Eq. 10-1, 10-2, from AISC 360-22 §J10.2 and §J10.3), not
  less than k_des, against the bearing length available on the outstanding
  leg (leg minus the setback, which includes the length underrun);
* shear yielding of the outstanding leg, 0.60 F_y L t (§J4.2);
* flexural yielding of the outstanding leg at the critical section a distance
  t + 3/8 in. from the back of the angle: R_n = (F_y L t^2/4) / e_c with
  e_c = setback + l_b/2 − t − 3/8 in. (Manual Part 10);
* shear transfer at the bolts in the vertical leg: n times the least of bolt
  shear and bearing on the angle and the support (§J3.7, §J3.11; edge distances
  are taken large enough that tearout does not govern, as in Manual Table 10-5).

With ``support_weld`` > 0 the vertical leg is welded to the support with a
fillet weld along each end (Design Examples II.A-13, II.A-16) instead of
bolted: R_n = 2 r_w l_v^2 / sqrt(l_v^2 + 20.25 e^2) (elastic method of Manual
Part 10, Table 10-6), l_v the vertical leg and e = setback + (leg − setback)/2.

The top (stability) angle is a standard detail of Manual Part 10: an L4×4×1/4
with two 3/4-in. bolts through each leg (or a 3/16-in. fillet weld along the
supported leg). It carries no part of the beam end reaction; the checks only
verify that the specified angle meets the standard minimums.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from openconex.core.checks import CheckResult
from openconex.core.loads import Method
from openconex.core.materials import E_STEEL
from openconex.core.model import BoltSpec
from openconex.kernel import bolts, elements
from openconex.kernel.design import FLEXURE, Calc, Resistance
from openconex.kernel.welds import fillet_weld_per_length
from openconex.units import Kind, to_internal

from .double_angle import SPEC

__all__ = ["SeatedAngle", "check_seated", "top_angle_checks"]

PART10 = "AISC Manual 16th ed., Part 10"
WEB_YIELDING = Resistance(1.00, 1.50)
WEB_CRIPPLING = Resistance(0.75, 2.00)

# Standard stability angle of Manual Part 10 (Design Examples II.A-12A, II.A-14).
TOP_ANGLE_LEG = to_internal(4.0, "in", Kind.LENGTH)
TOP_ANGLE_THICKNESS = to_internal(0.25, "in", Kind.THICKNESS)
TOP_ANGLE_LENGTH = to_internal(4.0, "in", Kind.LENGTH)
TOP_ANGLE_BOLTS = 2
TOP_ANGLE_WELD = to_internal(0.1875, "in", Kind.THICKNESS)


@dataclass(frozen=True)
class SeatedAngle:
    length: float
    """Angle length L."""
    thickness: float
    leg: float
    """Outstanding (horizontal) leg."""
    Fy: float
    bolt: BoltSpec
    bolts: int
    """Bolts through the vertical leg."""
    support_t: float
    support_Fu: float
    angle_Fu: float
    beam_d: float
    beam_tw: float
    beam_tf: float
    beam_kdes: float
    beam_Fy: float
    setback: float = to_internal(0.75, "in", Kind.LENGTH)
    """Setback including the length underrun (Manual Part 10: 1/2 in. + 1/4 in.)."""
    support_weld: float = 0.0
    """Fillet weld size along each end of the vertical leg; 0 when bolted."""
    vertical_leg: float = 0.0
    FEXX: float = to_internal(70.0, "ksi", Kind.STRESS)
    bearing_length: float | None = None
    """Bearing length used for the leg flexure; defaults to the required l_b,min."""
    top_angle_leg: float = TOP_ANGLE_LEG
    """Outstanding leg of the stability angle."""
    top_angle_thickness: float = TOP_ANGLE_THICKNESS
    top_angle_length: float = TOP_ANGLE_LENGTH
    """Length of the stability angle along the beam."""
    top_angle_bolts: int = TOP_ANGLE_BOLTS
    """Bolts through each leg of the stability angle (welded seats use the weld)."""
    top_angle_weld: float = TOP_ANGLE_WELD
    """Fillet weld of the stability angle to the support (welded seats)."""


def _factor(method: Method, r: Resistance) -> float:
    """Multiplier turning a required strength into a nominal one: 1/φ or Ω."""
    return 1 / r.phi if method is Method.LRFD else r.omega


def _bearing_length(sa: SeatedAngle, R: float, method: Method, combo: str) -> CheckResult:
    c = Calc(method, combo)
    clause = f"{PART10}, Eq. 10-1, 10-2"
    d, tw, tf = sa.beam_d, sa.beam_tw, sa.beam_tf
    available = c.step(r"l_{b,max}", r"\mathrm{leg} - \mathrm{setback}", sa.leg - sa.setback,
                       Kind.LENGTH, PART10)
    yielding = c.step(r"l_{b,yielding}", r"\frac{R}{\phi F_y t_w} - 2.5 k_{des}",
                      R * _factor(method, WEB_YIELDING) / (sa.beam_Fy * tw) - 2.5 * sa.beam_kdes,
                      Kind.LENGTH, f"{PART10}, Eq. 10-1")
    base = 0.40 * tw**2 * math.sqrt(E_STEEL * sa.beam_Fy * tf / tw)
    ratio = R * _factor(method, WEB_CRIPPLING) / base - 1
    if available / d <= 0.2:
        crippling = c.step(r"l_{b,crippling}",
                           r"\frac{d}{3}\left[\frac{R}{\phi 0.40 t_w^2}\sqrt{\frac{t_w}{E F_y t_f}}"
                           r" - 1\right]\left(\frac{t_f}{t_w}\right)^{1.5}",
                           d / 3 * ratio * (tf / tw) ** 1.5, Kind.LENGTH, f"{PART10}, Eq. 10-2")
    else:
        crippling = c.step(r"l_{b,crippling}",
                           r"\frac{d}{4}\left[\left(\frac{R}{\phi 0.40 t_w^2}\sqrt{\frac{t_w}"
                           r"{E F_y t_f}} - 1\right)\left(\frac{t_f}{t_w}\right)^{1.5}"
                           r" + 0.2\right]",
                           d / 4 * (ratio * (tf / tw) ** 1.5 + 0.2), Kind.LENGTH,
                           f"{PART10}, Eq. 10-3")
    required = c.step(r"l_{b,min}", r"\max(l_{b,yielding}, l_{b,crippling}, k_{des})",
                      max(yielding, crippling, sa.beam_kdes), Kind.LENGTH, clause)
    return c.result("seated.bearing_length", clause, required, available, Kind.LENGTH)


def top_angle_checks(method: Method, combo: str, *, leg: float, thickness: float,
                     length: float, bolts: int, weld: float,
                     welded: bool) -> list[CheckResult]:
    """Standard stability angle: minimum leg, thickness, length, bolts or weld."""
    clause = f"{PART10}, stability angle detail"
    checks = []
    for check_id, required, actual, kind in (
            ("seated.top_angle_leg", TOP_ANGLE_LEG, leg, Kind.LENGTH),
            ("seated.top_angle_thickness", TOP_ANGLE_THICKNESS, thickness, Kind.THICKNESS),
            ("seated.top_angle_length", TOP_ANGLE_LENGTH, length, Kind.LENGTH)):
        c = Calc(method, combo)
        c.step("required", "", required, kind, clause)
        checks.append(c.result(check_id, clause, required, actual, kind))
    c = Calc(method, combo)
    if welded:
        c.step("w_{min}", "", TOP_ANGLE_WELD, Kind.THICKNESS, clause)
        checks.append(c.result("seated.top_angle_weld", clause, TOP_ANGLE_WELD, weld,
                               Kind.THICKNESS))
    else:
        c.step("n_{min}", "", TOP_ANGLE_BOLTS, Kind.DIMENSIONLESS, clause)
        checks.append(c.result("seated.top_angle_bolts", clause, TOP_ANGLE_BOLTS, bolts,
                               Kind.DIMENSIONLESS))
    return checks


def check_seated(sa: SeatedAngle, R: float, method: Method,
                 combo: str = "") -> list[CheckResult]:
    """All limit states of the seat for the beam end reaction ``R``."""
    bearing = _bearing_length(sa, R, method, combo)
    lb = sa.bearing_length or bearing.demand

    c = Calc(method, combo)
    clause = PART10
    t = sa.thickness
    ec = c.step("e_c", r"\mathrm{setback} + l_b/2 - t - 3/8\ \mathrm{in.}",
                max(sa.setback + lb / 2 - t - to_internal(0.375, "in", Kind.LENGTH), 0.0),
                Kind.LENGTH, clause, l_b=(lb, Kind.LENGTH))
    mn = c.step("M_n", r"F_y L t^2/4", sa.Fy * sa.length * t**2 / 4, Kind.MOMENT, clause)
    rn = c.step("R_n", "M_n/e_c", mn / ec if ec > 0 else math.inf, Kind.FORCE, clause)
    flexure = c.result("seated.flexural_yielding", clause, R,
                       c.available(rn, FLEXURE, Kind.FORCE, clause), Kind.FORCE)

    if sa.support_weld > 0:
        bolt_check = _welds(sa, R, method, combo)
        shear = elements.shear_yielding(sa.length * t, sa.Fy, R, method, combo)
        shear = shear.model_copy(update={"id": "seated.shear_yielding",
                                         "text_id": "check.seated.shear_yielding"})
        return [bearing, shear, flexure, bolt_check, *top_angle_checks(
            method, combo, leg=sa.top_angle_leg, thickness=sa.top_angle_thickness,
            length=sa.top_angle_length, bolts=sa.top_angle_bolts,
            weld=sa.top_angle_weld, welded=True)]
    c = Calc(method, combo)
    clause = f"{SPEC} §J3.7, §J3.11"
    b = sa.bolt
    per_bolt = c.step("r_n", r"\min(r_{n,bolt}, 2.4 d t F_u)", min(
        bolts.bolt_shear(b, 0.0, method).capacity,
        bolts.bolt_bearing(b, t, sa.angle_Fu, 0.0, method).capacity,
        bolts.bolt_bearing(b, sa.support_t, sa.support_Fu, 0.0, method).capacity),
        Kind.FORCE, clause)
    bolt_check = c.result("seated.bolts", clause, R,
                          c.step("n r_n", "", sa.bolts * per_bolt, Kind.FORCE, clause,
                                 n=(sa.bolts, Kind.DIMENSIONLESS)), Kind.FORCE)
    shear = elements.shear_yielding(sa.length * t, sa.Fy, R, method, combo)
    shear = shear.model_copy(update={"id": "seated.shear_yielding",
                                     "text_id": "check.seated.shear_yielding"})
    return [bearing, shear, flexure, bolt_check, *top_angle_checks(
        method, combo, leg=sa.top_angle_leg, thickness=sa.top_angle_thickness,
        length=sa.top_angle_length, bolts=sa.top_angle_bolts, weld=sa.top_angle_weld,
        welded=False)]


def _welds(sa: SeatedAngle, R: float, method: Method, combo: str) -> CheckResult:
    c = Calc(method, combo)
    clause = f"{PART10}, Table 10-6"
    e = c.step("e", r"\mathrm{setback} + (\mathrm{leg} - \mathrm{setback})/2",
               sa.setback + (sa.leg - sa.setback) / 2, Kind.LENGTH, clause)
    rw = fillet_weld_per_length(sa.support_weld, sa.FEXX, 0.0, method).capacity
    lv = sa.vertical_leg
    rn = c.step("R_n", r"\frac{2 r_w l_v^2}{\sqrt{l_v^2 + 20.25 e^2}}",
                2 * rw * lv**2 / math.sqrt(lv**2 + 20.25 * e**2), Kind.FORCE, clause,
                l_v=(lv, Kind.LENGTH), w=(sa.support_weld, Kind.THICKNESS))
    return c.result("seated.weld", clause, R, rn, Kind.FORCE)
