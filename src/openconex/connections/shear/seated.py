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

The top (stability) angle is not designed.
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
from openconex.units import Kind, to_internal

from .double_angle import SPEC

__all__ = ["SeatedAngle", "check_seated"]

PART10 = "AISC Manual 16th ed., Part 10"
WEB_YIELDING = Resistance(1.00, 1.50)
WEB_CRIPPLING = Resistance(0.75, 2.00)


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
    bearing_length: float | None = None
    """Bearing length used for the leg flexure; defaults to the required l_b,min."""


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
    return [bearing, shear, flexure, bolt_check]
