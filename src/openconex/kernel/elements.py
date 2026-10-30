# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Affected and connecting elements, AISC 360-22 Section J4.

Areas in mm², stresses in MPa, forces in N, moments in N·mm.
"""

from __future__ import annotations

import math

from openconex.core.checks import CheckResult
from openconex.core.materials import E_STEEL
from openconex.kernel.design import (
    FLEXURE,
    SHEAR_RUPTURE,
    SHEAR_YIELD,
    SPEC,
    TENSION_RUPTURE,
    TENSION_YIELD,
    Calc,
    Method,
    Resistance,
)
from openconex.units import Kind, to_internal

__all__ = [
    "block_shear",
    "compression",
    "effective_net_area",
    "flexural_rupture",
    "flexural_yielding",
    "net_area",
    "shear_rupture",
    "shear_yielding",
    "tension_rupture",
    "tension_yielding",
]

COMPRESSION = Resistance(0.90, 1.67)
FLEXURAL_RUPTURE = Resistance(0.75, 2.00)
BLOCK_SHEAR = Resistance(0.75, 2.00)
HOLE_ALLOWANCE = to_internal(1 / 16, "in", Kind.LENGTH)
"""Extra width for net area: nominal hole + 1/16 in. (§B4.3b)."""


def net_area(gross: float, thickness: float, holes: int, hole_width: float,
             stagger: list[tuple[float, float]] | None = None) -> float:
    """An = Ag - n (dh + 1/16 in.) t + Σ s²/(4g) t (§B4.3b); stagger is [(s, g), ...]."""
    an = gross - holes * (hole_width + HOLE_ALLOWANCE) * thickness
    for s, g in stagger or []:
        an += s * s / (4 * g) * thickness
    return an


def effective_net_area(An: float, U: float = 1.0, Ag: float | None = None,
                       bolted_splice_plate: bool = False) -> float:
    """Ae = An U (§D3); for bolted splice plates Ae = An ≤ 0.85 Ag (§J4.1(b))."""
    if bolted_splice_plate:
        if Ag is None:
            raise ValueError("Ag is required for splice plates")
        return min(An, 0.85 * Ag)
    return An * U


def tension_yielding(Ag: float, Fy: float, demand: float, method: Method,
                     combo: str = "") -> CheckResult:
    clause = f"{SPEC} §J4.1(a), Eq. J4-1"
    c = Calc(method, combo)
    rn = c.step("R_n", "F_y A_g", Fy * Ag, Kind.FORCE, clause, F_y=(Fy, Kind.STRESS),
                A_g=(Ag, Kind.AREA))
    return c.result("element.tension_yielding", clause, demand,
                    c.available(rn, TENSION_YIELD, Kind.FORCE, clause), Kind.FORCE)


def tension_rupture(Ae: float, Fu: float, demand: float, method: Method,
                    combo: str = "") -> CheckResult:
    clause = f"{SPEC} §J4.1(b), Eq. J4-2"
    c = Calc(method, combo)
    rn = c.step("R_n", "F_u A_e", Fu * Ae, Kind.FORCE, clause, F_u=(Fu, Kind.STRESS),
                A_e=(Ae, Kind.AREA))
    return c.result("element.tension_rupture", clause, demand,
                    c.available(rn, TENSION_RUPTURE, Kind.FORCE, clause), Kind.FORCE)


def shear_yielding(Agv: float, Fy: float, demand: float, method: Method,
                   combo: str = "") -> CheckResult:
    clause = f"{SPEC} §J4.2(a), Eq. J4-3"
    c = Calc(method, combo)
    rn = c.step("R_n", "0.60 F_y A_{gv}", 0.60 * Fy * Agv, Kind.FORCE, clause,
                F_y=(Fy, Kind.STRESS), A_gv=(Agv, Kind.AREA))
    return c.result("element.shear_yielding", clause, demand,
                    c.available(rn, SHEAR_YIELD, Kind.FORCE, clause), Kind.FORCE)


def shear_rupture(Anv: float, Fu: float, demand: float, method: Method,
                  combo: str = "") -> CheckResult:
    clause = f"{SPEC} §J4.2(b), Eq. J4-4"
    c = Calc(method, combo)
    rn = c.step("R_n", "0.60 F_u A_{nv}", 0.60 * Fu * Anv, Kind.FORCE, clause,
                F_u=(Fu, Kind.STRESS), A_nv=(Anv, Kind.AREA))
    return c.result("element.shear_rupture", clause, demand,
                    c.available(rn, SHEAR_RUPTURE, Kind.FORCE, clause), Kind.FORCE)


def block_shear(Agv: float, Anv: float, Ant: float, Fy: float, Fu: float, demand: float,
                method: Method, Ubs: float = 1.0, combo: str = "") -> CheckResult:
    """Rn = 0.60 Fu Anv + Ubs Fu Ant ≤ 0.60 Fy Agv + Ubs Fu Ant (§J4.3, Eq. J4-5).

    Ubs = 1.0 for uniform tension stress, 0.5 for nonuniform.
    """
    clause = f"{SPEC} §J4.3, Eq. J4-5"
    c = Calc(method, combo)
    rupture = c.step("R_{n,1}", "0.60 F_u A_{nv} + U_{bs} F_u A_{nt}",
                     0.60 * Fu * Anv + Ubs * Fu * Ant, Kind.FORCE, clause,
                     A_nv=(Anv, Kind.AREA), A_nt=(Ant, Kind.AREA), U_bs=(Ubs, Kind.DIMENSIONLESS))
    yielding = c.step("R_{n,2}", "0.60 F_y A_{gv} + U_{bs} F_u A_{nt}",
                      0.60 * Fy * Agv + Ubs * Fu * Ant, Kind.FORCE, clause,
                      A_gv=(Agv, Kind.AREA))
    rn = c.step("R_n", r"\min(R_{n,1}, R_{n,2})", min(rupture, yielding), Kind.FORCE, clause)
    return c.result("element.block_shear", clause, demand,
                    c.available(rn, BLOCK_SHEAR, Kind.FORCE, clause), Kind.FORCE)


def compression(Ag: float, Fy: float, slenderness: float, demand: float, method: Method,
                combo: str = "") -> CheckResult:
    """Connecting elements in compression (§J4.4).

    ``slenderness`` is Lc/r. For Lc/r ≤ 25, Pn = Fy Ag (Eq. J4-6); otherwise
    flexural buckling per Chapter E (Eq. E3-2/E3-3).
    """
    clause = f"{SPEC} §J4.4"
    c = Calc(method, combo)
    if slenderness <= 25:
        rn = c.step("P_n", "F_y A_g", Fy * Ag, Kind.FORCE, clause + ", Eq. J4-6")
    else:
        fe = c.step("F_e", r"\frac{\pi^2 E}{(L_c/r)^2}", math.pi**2 * E_STEEL / slenderness**2,
                    Kind.STRESS, f"{SPEC} Eq. E3-4", Lc_r=(slenderness, Kind.DIMENSIONLESS))
        if slenderness <= 4.71 * math.sqrt(E_STEEL / Fy):
            fcr = c.step("F_{cr}", r"0.658^{F_y/F_e} F_y", 0.658 ** (Fy / fe) * Fy,
                         Kind.STRESS, f"{SPEC} Eq. E3-2")
        else:
            fcr = c.step("F_{cr}", "0.877 F_e", 0.877 * fe, Kind.STRESS, f"{SPEC} Eq. E3-3")
        rn = c.step("P_n", "F_{cr} A_g", fcr * Ag, Kind.FORCE, f"{SPEC} Eq. E3-1")
    return c.result("element.compression", clause, demand,
                    c.available(rn, COMPRESSION, Kind.FORCE, clause, "P_n"), Kind.FORCE)


def flexural_yielding(Z: float, Fy: float, demand: float, method: Method,
                      combo: str = "") -> CheckResult:
    """Flexural yielding of a connecting element, Mn = Fy Z (§J4.5)."""
    clause = f"{SPEC} §J4.5"
    c = Calc(method, combo)
    rn = c.step("M_n", "F_y Z", Fy * Z, Kind.MOMENT, clause, F_y=(Fy, Kind.STRESS),
                Z=(Z, Kind.SECTION_MODULUS))
    return c.result("element.flexural_yielding", clause, demand,
                    c.available(rn, FLEXURE, Kind.MOMENT, clause, "M_n"), Kind.MOMENT)


def flexural_rupture(Znet: float, Fu: float, demand: float, method: Method,
                     combo: str = "") -> CheckResult:
    """Flexural rupture of a connecting element, Mn = Fu Znet (§J4.5)."""
    clause = f"{SPEC} §J4.5"
    c = Calc(method, combo)
    rn = c.step("M_n", "F_u Z_{net}", Fu * Znet, Kind.MOMENT, clause, F_u=(Fu, Kind.STRESS),
                Z_net=(Znet, Kind.SECTION_MODULUS))
    return c.result("element.flexural_rupture", clause, demand,
                    c.available(rn, FLEXURAL_RUPTURE, Kind.MOMENT, clause, "M_n"), Kind.MOMENT)
