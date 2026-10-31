# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Shear transfer, tension transfer and column welds of base plates (AISC DG1, 3rd ed.).

Internal units (N, mm, MPa). Each function returns CheckResults with the trace.
"""

from __future__ import annotations

import math

from openconex.core.checks import CheckResult
from openconex.core.loads import Method
from openconex.core.model import BoltSpec, FilletWeld
from openconex.kernel import bolts, elements, welds
from openconex.kernel.design import Calc, Resistance
from openconex.units import Kind

__all__ = [
    "flange_weld_for_moment",
    "friction",
    "lug_plate_bending",
    "lug_steel_checks",
    "lug_weld",
    "plate_bending_at_rods",
    "rod_tension_shear_bending",
]

DG1 = "AISC DG1 3rd ed."
FRICTION = Resistance(0.65, math.nan)
CONCRETE_SHEAR = Resistance(0.75, math.nan)
PLATE = Resistance(0.90, 1.67)


def friction(P: float, area: float, fc: float, demand: float, mu: float = 0.4,
             combo: str = "") -> CheckResult:
    """φVn = min[0.65 μ Pu, 0.75 (0.2 f'c Ac), 0.75 (0.8 ksi) Ac] (DG1 Eq. 4-30), LRFD only.

    ``P`` is the minimum concurrent compression; ``area`` is the bearing area Ac.
    """
    clause = f"{DG1} §4.3.5, Eq. 4-30"
    c = Calc(Method.LRFD, combo)
    limit = 0.8 * 6.894757  # 0.8 ksi in MPa
    v = c.step(r"\phi V_n", r"\min[0.65\mu P_u,\ 0.75(0.2f'_c A_c),\ 0.75(0.8\ ksi)A_c]",
               min(FRICTION.phi * mu * max(P, 0.0), CONCRETE_SHEAR.phi * 0.2 * fc * area,
                   CONCRETE_SHEAR.phi * limit * area), Kind.FORCE, clause,
               mu=(mu, Kind.DIMENSIONLESS), P_u=(P, Kind.FORCE), A_c=(area, Kind.AREA))
    return c.result("base_plate.friction", clause, demand, v, Kind.FORCE)


def rod_tension_shear_bending(rod: BoltSpec, rods: int, N: float, V: float, tp: float,
                              washer_t: float, method: Method, combo: str = "") -> CheckResult:
    """Anchor rods in shear with bending through a welded plate washer (DG1 Example 4.7-6).

    Lever arm = (tp + washer_t/2)/2; f_t = N/(n Ab) + M/Z with Z = d³/6, checked
    against F'nt of AISC 360-22 §J3.8 using the shear stress V/(n Ab).
    """
    c = Calc(method, combo)
    arm = c.step("l_{arm}", r"\frac{t_p + t_w/2}{2}", (tp + washer_t / 2) / 2, Kind.LENGTH, DG1)
    m = c.step("M_r", r"\frac{V}{n} l_{arm}", V / rods * arm, Kind.MOMENT, DG1)
    z = c.step("Z", "d^3/6", rod.diameter**3 / 6, Kind.SECTION_MODULUS, DG1)
    ft = c.step("f_t", r"\frac{N}{n A_b} + \frac{M_r}{Z}", N / (rods * rod.area) + m / z,
                Kind.STRESS, DG1)
    combined = bolts.bolt_tension_shear(rod, ft * rod.area, V / rods, method, combo=combo)
    return combined.model_copy(update={
        "id": "base_plate.rod_combined", "text_id": "check.base_plate.rod_combined",
        "steps": (*c.steps, *combined.steps)})


def lug_steel_checks(width: float, thickness: float, Fy: float, Fu: float, V: float, M: float,
                     method: Method, combo: str = "") -> list[CheckResult]:
    """Shear yielding and rupture and flexural yielding and rupture of a shear lug (§J4)."""
    a = width * thickness
    z = width * thickness**2 / 4
    return [
        elements.shear_yielding(a, Fy, V, method, combo),
        elements.shear_rupture(a, Fu, V, method, combo),
        elements.flexural_yielding(z, Fy, M, method, combo),
        elements.flexural_rupture(z, Fu, M, method, combo),
    ]


def lug_weld(width: float, lug_thickness: float, weld_size: float, FEXX: float, V: float,
             M: float, method: Method, combo: str = "") -> CheckResult:
    """Fillet welds on both faces of a shear lug: resultant per unit length (DG1 Ex. 4.7-5).

    Lever between welds a = t_lug + 2w/3; r_v = V/(2b), r_m = M/(a b); θ = 90°.
    """
    c = Calc(method, combo)
    a = c.step("a", "t_{sl} + 2w/3", lug_thickness + 2 * weld_size / 3, Kind.LENGTH, DG1)
    rv = c.step("r_v", r"\frac{V}{2b}", V / (2 * width), Kind.FORCE_PER_LENGTH, DG1)
    rm = c.step("r_m", r"\frac{M}{a b}", M / (a * width), Kind.FORCE_PER_LENGTH, DG1)
    r = c.step("r", r"\sqrt{r_v^2 + r_m^2}", math.hypot(rv, rm), Kind.FORCE_PER_LENGTH, DG1)
    check = welds.fillet_weld_per_length(weld_size, FEXX, r, method, theta=90, combo=combo)
    return check.model_copy(update={"steps": (*c.steps, *check.steps)})


def lug_plate_bending(width: float, tp: float, Fy: float, moment: float, method: Method,
                      combo: str = "") -> CheckResult:
    """Local bending of the base plate at the shear lug (DG1 Example 4.7-5).

    Effective width b_sl and plastic modulus Z = b_sl t_bp^2/4 (AISC 360-22 §J4.5).
    """
    c = Calc(method, combo)
    z = c.step("Z_y", r"\frac{b_{sl} t_{bp}^2}{4}", width * tp**2 / 4,
               Kind.SECTION_MODULUS, DG1)
    check = elements.flexural_yielding(z, Fy, moment, method, combo)
    return check.model_copy(update={
        "id": "base_plate.lug_plate_bending",
        "text_id": "check.base_plate.lug_plate_bending",
        "steps": (*c.steps, *check.steps)})


def plate_bending_at_rods(rod_force: float, a: float, tp: float, Fy: float, method: Method,
                          combo: str = "") -> CheckResult:
    """Plate bending from one rod in tension, 45° spread: b_eff = 2a, Z = b_eff t²/4.

    ``a`` is the distance from the rod to the face of the supporting web or
    flange (DG1 Examples 4.7-3 and 4.7-7).
    """
    c = Calc(method, combo)
    m = c.step("M_r", "r a", rod_force * a, Kind.MOMENT, DG1)
    beff = c.step("b_{eff}", "2a", 2 * a, Kind.LENGTH, DG1)
    check = elements.flexural_yielding(beff * tp * tp / 4, Fy, m, method, combo)
    return check.model_copy(update={"id": "base_plate.plate_bending_rods",
                                    "text_id": "check.base_plate.plate_bending_rods",
                                    "steps": (*c.steps, *check.steps)})


def flange_weld_for_moment(M: float, d: float, weld: FilletWeld, method: Method,
                           combo: str = "") -> CheckResult:
    """Column flange weld for the flange force M/d, transverse (θ = 90°) (DG1 Ex. 4.7-9)."""
    c = Calc(method, combo)
    force = c.step("R", "M/d", M / d, Kind.FORCE, DG1)
    check = welds.fillet_weld(weld, force, method, theta=90, combo=combo)
    return check.model_copy(update={"steps": (*c.steps, *check.steps)})
