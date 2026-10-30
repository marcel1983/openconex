# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Bolt checks, AISC 360-22 Section J3 (strength per bolt).

Demands are the required strength of one bolt (N); thicknesses and distances
in mm; stresses in MPa.
"""

from __future__ import annotations

from enum import StrEnum

from openconex.core.bolting import HoleType, min_edge_distance, min_spacing
from openconex.core.checks import CheckResult
from openconex.core.model import BoltSpec
from openconex.kernel.design import BOLT, SPEC, Calc, Method, Resistance
from openconex.units import Kind, from_internal, to_internal

__all__ = [
    "SlipClass",
    "bolt_bearing",
    "bolt_shear",
    "bolt_slip",
    "bolt_spacing_checks",
    "bolt_tearout",
    "bolt_tension",
    "bolt_tension_shear",
    "clear_distance",
]

D_U = 1.13
"""Ratio of mean installed pretension to specified minimum pretension, §J3.9."""


class SlipClass(StrEnum):
    A = "A"
    B = "B"

    @property
    def mu(self) -> float:
        return {"A": 0.30, "B": 0.50}[self.value]


def bolt_tension(bolt: BoltSpec, demand: float, method: Method, combo: str = "") -> CheckResult:
    """Tensile strength Rn = Fnt Ab (§J3.7, Eq. J3-1)."""
    clause = f"{SPEC} §J3.7, Eq. J3-1"
    c = Calc(method, combo)
    rn = c.step("R_n", "F_{nt} A_b", bolt.material.Fnt * bolt.area, Kind.FORCE, clause,
                F_nt=(bolt.material.Fnt, Kind.STRESS), A_b=(bolt.area, Kind.AREA))
    cap = c.available(rn, BOLT, Kind.FORCE, clause)
    return c.result("bolt.tension", clause, demand, cap, Kind.FORCE)


def bolt_shear(bolt: BoltSpec, demand: float, method: Method, planes: int = 1,
               combo: str = "") -> CheckResult:
    """Shear strength Rn = Fnv Ab per shear plane (§J3.7, Eq. J3-1)."""
    clause = f"{SPEC} §J3.7, Eq. J3-1"
    c = Calc(method, combo)
    rn = c.step("R_n", "n_s F_{nv} A_b", planes * bolt.Fnv * bolt.area, Kind.FORCE, clause,
                n_s=(planes, Kind.DIMENSIONLESS), F_nv=(bolt.Fnv, Kind.STRESS),
                A_b=(bolt.area, Kind.AREA))
    cap = c.available(rn, BOLT, Kind.FORCE, clause)
    return c.result("bolt.shear", clause, demand, cap, Kind.FORCE)


def bolt_tension_shear(bolt: BoltSpec, tension: float, shear: float, method: Method,
                       planes: int = 1, combo: str = "") -> CheckResult:
    """Tension with shear in bearing-type connections (§J3.8, Eq. J3-2/J3-3).

    The nominal tensile stress is reduced to F'nt according to the required
    shear stress f_rv; the check compares the bolt tension with F'nt Ab.
    """
    clause = f"{SPEC} §J3.8"
    c = Calc(method, combo)
    fnt, fnv, ab = bolt.material.Fnt, bolt.Fnv, bolt.area
    frv = c.step("f_{rv}", "V_r/(n_s A_b)", shear / (planes * ab), Kind.STRESS, clause)
    if method is Method.LRFD:
        expr, red = r"1.3F_{nt} - \frac{F_{nt}}{\phi F_{nv}} f_{rv}", fnt / (BOLT.phi * fnv)
    else:
        expr, red = r"1.3F_{nt} - \frac{\Omega F_{nt}}{F_{nv}} f_{rv}", BOLT.omega * fnt / fnv
    fnt_p = c.step("F'_{nt}", expr + r" \le F_{nt}", max(0.0, min(fnt, 1.3 * fnt - red * frv)),
                   Kind.STRESS, clause + ", Eq. J3-3", F_nt=(fnt, Kind.STRESS),
                   F_nv=(fnv, Kind.STRESS))
    rn = c.step("R_n", "F'_{nt} A_b", fnt_p * ab, Kind.FORCE, clause + ", Eq. J3-2")
    cap = c.available(rn, BOLT, Kind.FORCE, clause)
    return c.result("bolt.combined", clause, tension, cap, Kind.FORCE)


def _slip_resistance(hole: HoleType, slot_parallel: bool) -> Resistance:
    if hole is HoleType.STANDARD or (hole is HoleType.SHORT_SLOT and not slot_parallel):
        return Resistance(1.00, 1.50)
    if hole is HoleType.LONG_SLOT:
        return Resistance(0.70, 2.14)
    return Resistance(0.85, 1.76)


def bolt_slip(bolt: BoltSpec, demand: float, method: Method, pretension: float,
              slip_class: SlipClass = SlipClass.A, slip_planes: int = 1,
              fillers: int = 0, tension: float = 0.0, bolts_in_tension: int = 1,
              slot_parallel: bool = False, combo: str = "") -> CheckResult:
    """Slip resistance Rn = μ Du hf Tb ns (§J3.9, Eq. J3-4), reduced by ksc (§J3.10).

    ``pretension`` is Tb (Table J3.1); ``fillers`` is the number of fillers
    between connected parts (hf = 1.0 for none or one, 0.85 for two or more);
    ``tension`` is the applied tension shared by ``bolts_in_tension`` bolts.
    ``slot_parallel`` tells whether a slot is parallel to the load.
    """
    clause = f"{SPEC} §J3.9, Eq. J3-4"
    c = Calc(method, combo)
    hf = 1.0 if fillers <= 1 else 0.85
    rn = c.step("R_n", r"\mu D_u h_f T_b n_s",
                slip_class.mu * D_U * hf * pretension * slip_planes, Kind.FORCE, clause,
                mu=(slip_class.mu, Kind.DIMENSIONLESS), D_u=(D_U, Kind.DIMENSIONLESS),
                h_f=(hf, Kind.DIMENSIONLESS), T_b=(pretension, Kind.FORCE),
                n_s=(slip_planes, Kind.DIMENSIONLESS))
    if tension > 0:
        k = 1.0 if method is Method.LRFD else 1.5
        expr = (r"1 - \frac{T_u}{D_u T_b n_b}" if method is Method.LRFD
                else r"1 - \frac{1.5 T_a}{D_u T_b n_b}")
        ksc = c.step("k_{sc}", expr, max(0.0, 1 - k * tension / (D_U * pretension
                     * bolts_in_tension)), Kind.DIMENSIONLESS, f"{SPEC} §J3.10, Eq. J3-5")
        rn = c.step("R_n", r"k_{sc} R_n", ksc * rn, Kind.FORCE)
    cap = c.available(rn, _slip_resistance(bolt.hole, slot_parallel), Kind.FORCE, clause)
    return c.result("bolt.slip", clause, demand, cap, Kind.FORCE)


def bolt_bearing(bolt: BoltSpec, thickness: float, Fu: float, demand: float, method: Method,
                 deformation_considered: bool = True, slot_perpendicular: bool = False,
                 combo: str = "") -> CheckResult:
    """Bearing at a bolt hole (§J3.11a): 2.4, 3.0 or 2.0 d t Fu."""
    clause = f"{SPEC} §J3.11(a)"
    c = Calc(method, combo)
    if bolt.hole is HoleType.LONG_SLOT and slot_perpendicular:
        k = 2.0
    else:
        k = 2.4 if deformation_considered else 3.0
    rn = c.step("R_n", rf"{k:g} d t F_u", k * bolt.diameter * thickness * Fu, Kind.FORCE,
                clause, d=(bolt.diameter, Kind.LENGTH), t=(thickness, Kind.THICKNESS),
                F_u=(Fu, Kind.STRESS))
    cap = c.available(rn, BOLT, Kind.FORCE, clause)
    return c.result("bolt.bearing", clause, demand, cap, Kind.FORCE)


def bolt_tearout(bolt: BoltSpec, thickness: float, Fu: float, lc: float, demand: float,
                 method: Method, deformation_considered: bool = True,
                 slot_perpendicular: bool = False, combo: str = "") -> CheckResult:
    """Tearout at a bolt hole (§J3.11b): 1.2, 1.5 or 1.0 lc t Fu."""
    clause = f"{SPEC} §J3.11(b)"
    c = Calc(method, combo)
    if bolt.hole is HoleType.LONG_SLOT and slot_perpendicular:
        k = 1.0
    else:
        k = 1.2 if deformation_considered else 1.5
    rn = c.step("R_n", rf"{k:g} l_c t F_u", k * lc * thickness * Fu, Kind.FORCE, clause,
                l_c=(lc, Kind.LENGTH), t=(thickness, Kind.THICKNESS), F_u=(Fu, Kind.STRESS))
    cap = c.available(rn, BOLT, Kind.FORCE, clause)
    return c.result("bolt.tearout", clause, demand, cap, Kind.FORCE)


def clear_distance(bolt: BoltSpec, distance: float, to_edge: bool,
                   along_slot: bool = False) -> float:
    """Clear distance lc in the direction of the force [mm].

    ``distance`` is centre-of-hole to edge (``to_edge``) or centre-to-centre
    spacing; the hole dimension is taken along the force (its length when the
    force acts ``along_slot``).
    """
    width, length = bolt.hole_dimensions
    hole = length if along_slot else width
    return distance - (hole / 2 if to_edge else hole)


def bolt_spacing_checks(bolt: BoltSpec, spacing: float | None, edge: float | None,
                        thickness: float, weathering: bool = False) -> list[CheckResult]:
    """Detailing limits: minimum spacing (§J3.3), minimum edge distance (§J3.4,
    Table J3.4, standard holes) and maximum spacing and edge distance (§J3.5).

    Minimum checks use demand = required minimum and capacity = provided.
    """
    results: list[CheckResult] = []
    d_in = from_internal(bolt.diameter, Kind.LENGTH, "in")
    inch = to_internal(1.0, "in", Kind.LENGTH)
    if spacing is not None:
        c = Calc(Method.LRFD)
        smin = c.step("s_{min}", r"2\tfrac{2}{3} d", min_spacing(bolt.diameter), Kind.LENGTH,
                      f"{SPEC} §J3.3")
        results.append(c.result("bolt.min_spacing", f"{SPEC} §J3.3", smin, spacing, Kind.LENGTH))
        c = Calc(Method.LRFD)
        k, cap = (14, 7) if weathering else (24, 12)
        smax = c.step("s_{max}", rf"\min({k} t, {cap}\ in.)", min(k * thickness, cap * inch),
                      Kind.LENGTH, f"{SPEC} §J3.5")
        results.append(c.result("bolt.max_spacing", f"{SPEC} §J3.5", spacing, smax, Kind.LENGTH))
    if edge is not None:
        c = Calc(Method.LRFD)
        emin = c.step("l_{e,min}", "Table J3.4", min_edge_distance(d_in), Kind.LENGTH,
                      f"{SPEC} §J3.4")
        results.append(c.result("bolt.min_edge", f"{SPEC} §J3.4, Table J3.4", emin, edge,
                                Kind.LENGTH))
        c = Calc(Method.LRFD)
        emax = c.step("l_{e,max}", r"\min(12 t, 6\ in.)", min(12 * thickness, 6 * inch),
                      Kind.LENGTH, f"{SPEC} §J3.5")
        results.append(c.result("bolt.max_edge", f"{SPEC} §J3.5", edge, emax, Kind.LENGTH))
    return results
