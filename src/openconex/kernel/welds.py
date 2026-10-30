# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Weld checks, AISC 360-22 Section J2.

Fillet welds are equal-leg; ``theta`` is the angle between the line of action
of the force and the weld longitudinal axis, in degrees.
"""

from __future__ import annotations

import math

from openconex.core.checks import CheckResult
from openconex.core.model import FilletWeld
from openconex.kernel.design import SPEC, WELD, Calc, Method, Resistance
from openconex.units import Kind, to_internal

__all__ = [
    "directional_factor",
    "fillet_effective_length",
    "fillet_size_checks",
    "fillet_weld",
    "fillet_weld_group_concentric",
    "fillet_weld_per_length",
    "pjp_weld",
]

PJP_TENSION = Resistance(0.80, 1.88)


def directional_factor(theta: float) -> float:
    """k_ds = 1.0 + 0.50 sin^1.5(θ), AISC 360-22 Eq. J2-5."""
    return 1.0 + 0.50 * math.sin(math.radians(theta)) ** 1.5


def fillet_effective_length(size: float, length: float, end_loaded: bool) -> float:
    """Effective length of an end-loaded fillet weld (§J2.2b(d)).

    For l > 100w the length is multiplied by β = 1.2 - 0.002 l/w ≤ 1.0; beyond
    300w the effective length is 180w.
    """
    ratio = length / size
    if not end_loaded or ratio <= 100:
        return length
    if ratio > 300:
        return 180 * size
    return length * min(1.0, 1.2 - 0.002 * ratio)


def fillet_weld(weld: FilletWeld, demand: float, method: Method, theta: float = 0.0,
                end_loaded: bool = False, combo: str = "") -> CheckResult:
    """Fillet weld strength Rn = Fnw Awe with Fnw = 0.60 FEXX k_ds (§J2.4, Eq. J2-4)."""
    clause = f"{SPEC} §J2.4, Eq. J2-4"
    c = Calc(method, combo)
    kds = c.step("k_{ds}", r"1.0 + 0.50\sin^{1.5}\theta", directional_factor(theta),
                 clause=f"{SPEC} Eq. J2-5", theta=(theta, Kind.DIMENSIONLESS))
    fnw = c.step("F_{nw}", "0.60 F_{EXX} k_{ds}", 0.60 * weld.material.FEXX * kds, Kind.STRESS,
                 clause, F_EXX=(weld.material.FEXX, Kind.STRESS))
    le = c.step("l_e", r"\beta l", fillet_effective_length(weld.size, weld.length, end_loaded),
                Kind.LENGTH, f"{SPEC} §J2.2b")
    awe = c.step("A_{we}", r"\frac{w}{\sqrt{2}} l_e", weld.throat * le, Kind.AREA,
                 w=(weld.size, Kind.THICKNESS))
    rn = c.step("R_n", "F_{nw} A_{we}", fnw * awe, Kind.FORCE, clause)
    cap = c.available(rn, WELD, Kind.FORCE, clause)
    return c.result("weld.strength", clause, demand, cap, Kind.FORCE)


def fillet_weld_per_length(size: float, FEXX: float, demand: float, method: Method,
                           theta: float = 0.0, combo: str = "") -> CheckResult:
    """Strength per unit length of one fillet weld line; ``demand`` in N/mm."""
    clause = f"{SPEC} §J2.4, Eq. J2-4"
    c = Calc(method, combo)
    kds = c.step("k_{ds}", r"1.0 + 0.50\sin^{1.5}\theta", directional_factor(theta),
                 clause=f"{SPEC} Eq. J2-5")
    rn = c.step("R_n", r"0.60 F_{EXX} k_{ds} \frac{w}{\sqrt{2}}",
                0.60 * FEXX * kds * size / math.sqrt(2), Kind.FORCE_PER_LENGTH, clause,
                F_EXX=(FEXX, Kind.STRESS), w=(size, Kind.THICKNESS))
    cap = c.available(rn, WELD, Kind.FORCE_PER_LENGTH, clause)
    return c.result("weld.strength", clause, demand, cap, Kind.FORCE_PER_LENGTH)


def fillet_weld_group_concentric(size: float, FEXX: float, longitudinal: float,
                                 transverse: float, demand: float, method: Method,
                                 combo: str = "") -> CheckResult:
    """Concentrically loaded group of longitudinal and transverse fillet welds (§J2.4(b)).

    Rn = max(Rnwl + Rnwt, 0.85 Rnwl + 1.5 Rnwt), Eq. J2-6a/J2-6b, with both
    components computed without the directional increase.
    """
    clause = f"{SPEC} §J2.4(b)"
    c = Calc(method, combo)
    unit = 0.60 * FEXX * size / math.sqrt(2)
    rl = c.step("R_{nwl}", r"0.60 F_{EXX} \frac{w}{\sqrt{2}} l_l", unit * longitudinal,
                Kind.FORCE, clause)
    rt = c.step("R_{nwt}", r"0.60 F_{EXX} \frac{w}{\sqrt{2}} l_t", unit * transverse,
                Kind.FORCE, clause)
    rn = c.step("R_n", r"\max(R_{nwl} + R_{nwt},\ 0.85R_{nwl} + 1.5R_{nwt})",
                max(rl + rt, 0.85 * rl + 1.5 * rt), Kind.FORCE, clause + ", Eq. J2-6")
    cap = c.available(rn, WELD, Kind.FORCE, clause)
    return c.result("weld.strength", clause, demand, cap, Kind.FORCE)


def _min_fillet_size(t: float) -> float:
    """Table J2.4, by the thickness of the thinner part joined [mm]."""
    t_in = t / 25.4
    for limit, size in ((0.25, 1 / 8), (0.5, 3 / 16), (0.75, 1 / 4)):
        if t_in <= limit:
            return size * 25.4
    return 5 / 16 * 25.4


def fillet_size_checks(size: float, length: float, thinner_part: float,
                       edge_thickness: float | None = None) -> list[CheckResult]:
    """Detailing limits of fillet welds (§J2.2b).

    Minimum size (Table J2.4), maximum size along a material edge of thickness
    ``edge_thickness`` (t for t < 1/4 in., t - 1/16 in. otherwise) and minimum
    length 4w. Minimum checks use demand = required minimum, capacity = provided.
    """
    results = []
    c = Calc(Method.LRFD)
    wmin = c.step("w_{min}", "Table J2.4", _min_fillet_size(thinner_part), Kind.THICKNESS,
                  f"{SPEC} Table J2.4", t=(thinner_part, Kind.THICKNESS))
    results.append(c.result("weld.min_size", f"{SPEC} §J2.2b, Table J2.4", wmin, size,
                            Kind.THICKNESS))
    if edge_thickness is not None:
        c = Calc(Method.LRFD)
        sixteenth = to_internal(1 / 16, "in", Kind.LENGTH)
        quarter = to_internal(0.25, "in", Kind.LENGTH)
        wmax = c.step("w_{max}", r"t\ (t < 1/4\ in.),\ t - 1/16\ in.",
                      edge_thickness if edge_thickness < quarter else edge_thickness - sixteenth,
                      Kind.THICKNESS, f"{SPEC} §J2.2b(b)")
        results.append(c.result("weld.max_size", f"{SPEC} §J2.2b(b)", size, wmax,
                                Kind.THICKNESS))
    c = Calc(Method.LRFD)
    lmin = c.step("l_{min}", "4w", 4 * size, Kind.LENGTH, f"{SPEC} §J2.2b(c)")
    results.append(c.result("weld.min_length", f"{SPEC} §J2.2b(c)", lmin, length, Kind.LENGTH))
    return results


def pjp_weld(throat: float, length: float, FEXX: float, demand: float, method: Method,
             tension_normal: bool, combo: str = "") -> CheckResult:
    """Weld metal strength of a PJP groove weld (Table J2.5).

    Tension normal to the weld axis: φ = 0.80, Ω = 1.88; shear: φ = 0.75,
    Ω = 2.00; Fnw = 0.60 FEXX. ``throat`` is the effective throat E (Table J2.1).
    The base metal must be checked separately with Section J4.
    """
    clause = f"{SPEC} §J2.4, Table J2.5"
    c = Calc(method, combo)
    rn = c.step("R_n", "0.60 F_{EXX} E l", 0.60 * FEXX * throat * length, Kind.FORCE, clause,
                E=(throat, Kind.THICKNESS), l=(length, Kind.LENGTH))
    cap = c.available(rn, PJP_TENSION if tension_normal else WELD, Kind.FORCE, clause)
    return c.result("weld.pjp", clause, demand, cap, Kind.FORCE)
