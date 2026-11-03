# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Extended single-plate connection (AISC Manual Part 10; Design Example II.A-19A).

A plate welded to the support (typically a column web, with the beam framing
between the flanges) and bolted to the beam web with one or two vertical lines
of bolts far from the weld. Limit states for the beam end reaction R:

* bolt group: C times the least single-bolt strength (bolt shear, bearing on
  the beam web and the plate, tearout of the bottom edge bolt of the plate);
  C by the instantaneous center for the eccentricity from the support to the
  centroid of the group;
* maximum plate thickness so that the plate yields before the bolts shear,
  t_max = 6 M_max / (F_y l^2) with M_max = F_nv A_b C' / 0.90 (Manual Eq. 10-6,
  10-7), C' being the pure-moment coefficient of the group;
* plate shear yielding and rupture, block shear (U_bs = 0.5 with two lines),
  flexural yielding and lateral-torsional buckling at the first bolt line
  (M = R a, L_b = a, C_b = 1.84), their interaction with shear and flexural
  rupture with the net plastic modulus of that line;
* weld size w ≥ 5/8 t_p and the support thickness that develops it.

The tearout of the beam web is not checked: as in the example, the beam flange
is assumed to be above the top bolt.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from openconex.core.checks import CheckResult
from openconex.core.loads import Method
from openconex.core.materials import E_STEEL
from openconex.core.model import BoltSpec
from openconex.kernel import bolts, elements
from openconex.kernel.bolt_group import _bolt_response, icr_coefficient
from openconex.kernel.bolts import clear_distance
from openconex.kernel.design import FLEXURE, Calc
from openconex.units import Kind, from_internal, to_internal

from .double_angle import SPEC, _hole_net

__all__ = ["ExtendedSinglePlate", "check_extended_single_plate"]

PART10 = "AISC Manual 16th ed., Part 10"
CB = 1.84


@dataclass(frozen=True)
class ExtendedSinglePlate:
    bolt: BoltSpec
    rows: int
    """Bolts in each vertical line."""
    spacing: float
    length: float
    thickness: float
    lev: float
    leh: float
    """Horizontal edge distance from the last bolt line to the end of the plate."""
    a: float
    """Distance from the weld line to the first bolt line."""
    plate_Fy: float
    plate_Fu: float
    beam_tw: float
    beam_Fu: float
    weld: float
    support_t: float
    support_Fu: float
    lines: int = 1
    gage: float = 0.0
    """Distance between the bolt lines."""
    deformation_considered: bool = True


def _rename(key: str, check: CheckResult) -> CheckResult:
    return check.model_copy(update={"id": f"extended_plate.{key}",
                                    "text_id": f"check.extended_plate.{key}"})


def _group(sp: ExtendedSinglePlate) -> list[tuple[float, float]]:
    return [(j * sp.gage, i * sp.spacing) for j in range(sp.lines) for i in range(sp.rows)]


def _bolts(sp: ExtendedSinglePlate, R: float, method: Method, combo: str) -> CheckResult:
    c = Calc(method, combo)
    clause = f"{SPEC} §J3.7, §J3.11; AISC Manual 16th ed., Part 7"
    b = sp.bolt
    kw = {"deformation_considered": sp.deformation_considered}
    per_bolt = [
        c.step(r"r_{n,bolt}", "", bolts.bolt_shear(b, 0.0, method).capacity, Kind.FORCE,
               f"{SPEC} §J3.7"),
        c.step(r"r_{n,web}", r"2.4 d t_w F_u",
               bolts.bolt_bearing(b, sp.beam_tw, sp.beam_Fu, 0.0, method, **kw).capacity,
               Kind.FORCE, f"{SPEC} §J3.11(a)"),
        c.step(r"r_{n,plate}", r"2.4 d t_p F_u",
               bolts.bolt_bearing(b, sp.thickness, sp.plate_Fu, 0.0, method, **kw).capacity,
               Kind.FORCE, f"{SPEC} §J3.11(a)"),
        c.step(r"r_{n,plate,edge}", r"1.2 l_c t_p F_u",
               bolts.bolt_tearout(b, sp.thickness, sp.plate_Fu,
                                  clear_distance(b, sp.lev, to_edge=True), 0.0, method,
                                  **kw).capacity, Kind.FORCE, f"{SPEC} §J3.11(b)"),
    ]
    rn = c.step("r_n", r"\min", min(per_bolt), Kind.FORCE, clause)
    e = c.step("e", r"a + (n_l - 1)g/2", sp.a + (sp.lines - 1) * sp.gage / 2, Kind.LENGTH,
               PART10)
    group = _group(sp)
    C = c.step("C", "IC", icr_coefficient(group, ((sp.lines - 1) * sp.gage / 2 + e,
                                                  (sp.rows - 1) * sp.spacing / 2)).C,
               clause=clause)
    return c.result("extended_plate.bolts", clause, R,
                    c.step("C r_n", "", C * rn, Kind.FORCE, clause), Kind.FORCE)


def _max_thickness(sp: ExtendedSinglePlate, method: Method, combo: str) -> CheckResult:
    c = Calc(method, combo)
    clause = f"{PART10}, Eq. 10-6, 10-7"
    group = _group(sp)
    cx = sum(x for x, _ in group) / len(group)
    cy = sum(y for _, y in group) / len(group)
    dist = [math.hypot(x - cx, y - cy) for x, y in group]
    c_prime = c.step("C'", r"\sum R_i d_i / R_{ult}",
                     sum(_bolt_response(d, max(dist)) * d for d in dist), Kind.LENGTH,
                     "AISC Manual 16th ed., Part 7 (pure moment)")
    b = sp.bolt
    m_max = c.step("M_{max}", r"\frac{F_{nv}}{0.90} A_b C'",
                   b.Fnv / 0.90 * b.area * c_prime, Kind.MOMENT, f"{PART10}, Eq. 10-7",
                   F_nv=(b.Fnv, Kind.STRESS))
    t_max = c.step("t_{max}", r"\frac{6 M_{max}}{F_y l^2}",
                   6 * m_max / (sp.plate_Fy * sp.length**2), Kind.THICKNESS,
                   f"{PART10}, Eq. 10-6")
    return c.result("extended_plate.max_thickness", clause, sp.thickness, t_max,
                    Kind.THICKNESS)


def _ltb(sp: ExtendedSinglePlate, M: float, method: Method, combo: str) -> CheckResult:
    c = Calc(method, combo)
    clause = f"{SPEC} §F11.2"
    t, d, Fy = sp.thickness, sp.length, sp.plate_Fy
    Z, S = t * d**2 / 4, t * d**2 / 6
    ratio = c.step(r"\frac{L_b d}{t^2}", "", sp.a * d / t**2, clause=clause,
                   L_b=(sp.a, Kind.LENGTH))
    mp = min(Fy * Z, 1.5 * Fy * S)
    if ratio <= 0.08 * E_STEEL / Fy:
        mn = c.step("M_n", "M_p", mp, Kind.MOMENT, f"{SPEC} Eq. F11-1")
    elif ratio <= 1.9 * E_STEEL / Fy:
        mn = c.step("M_n", r"C_b\left[1.52 - 0.274\frac{L_b d}{t^2}\frac{F_y}{E}\right]M_y"
                    r" \le M_p", min(CB * (1.52 - 0.274 * ratio * Fy / E_STEEL) * Fy * S, mp),
                    Kind.MOMENT, f"{SPEC} Eq. F11-3", C_b=(CB, Kind.DIMENSIONLESS))
    else:
        fcr = c.step("F_{cr}", r"\frac{1.9 E C_b}{L_b d/t^2}", 1.9 * E_STEEL * CB / ratio,
                     Kind.STRESS, f"{SPEC} Eq. F11-4")
        mn = c.step("M_n", r"F_{cr}S_x \le M_p", min(fcr * S, mp), Kind.MOMENT,
                    f"{SPEC} Eq. F11-4")
    return c.result("extended_plate.flexural_ltb", clause, M,
                    c.available(mn, FLEXURE, Kind.MOMENT, clause, "M_n"), Kind.MOMENT)


def check_extended_single_plate(sp: ExtendedSinglePlate, R: float, method: Method,
                                combo: str = "") -> list[CheckResult]:
    """All limit states of the connection for the beam end reaction ``R``."""
    t, L, n, hole = sp.thickness, sp.length, sp.rows, _hole_net(sp.bolt)
    Fy, Fu = sp.plate_Fy, sp.plate_Fu
    M = R * sp.a
    Z, S = t * L**2 / 4, t * L**2 / 6
    center = (n - 1) * sp.spacing / 2
    ys = [abs(i * sp.spacing - center) for i in range(n)]
    Znet = Z - sum(t * hole * y if y >= hole / 2 else t * hole**2 / 4 for y in ys)

    shear_y = _rename("shear_yielding", elements.shear_yielding(L * t, Fy, R, method, combo))
    flex_y = _rename("flexural_yielding", elements.flexural_yielding(min(Z, 1.5 * S), Fy, M,
                                                                     method, combo))
    ltb = _ltb(sp, M, method, combo)
    c = Calc(method, combo)
    clause = f"{PART10} (shear and flexural yielding)"
    u = c.step("U", r"\left(\frac{V}{V_c}\right)^2 + \left(\frac{M}{M_c}\right)^2",
               (R / shear_y.capacity) ** 2 + (M / min(flex_y.capacity, ltb.capacity)) ** 2,
               clause=clause)
    interaction = c.result("extended_plate.interaction", clause, u, 1.0, Kind.DIMENSIONLESS)

    agv = (L - sp.lev) * t
    anv = agv - (n - 0.5) * hole * t
    ant = (sp.leh + (sp.lines - 1) * sp.gage - (sp.lines - 0.5) * hole) * t
    block = _rename("block_shear", elements.block_shear(
        agv, anv, ant, Fy, Fu, R, method, Ubs=1.0 if sp.lines == 1 else 0.5, combo=combo))

    sixteenths = from_internal(sp.weld, Kind.LENGTH, "in") * 16
    t_min = to_internal(3.09 * sixteenths / from_internal(sp.support_Fu, Kind.STRESS, "ksi"),
                        "in", Kind.LENGTH)
    weld = Calc(method, combo)
    weld.step(r"\frac{5}{8}t_p", "", 5 * t / 8, Kind.THICKNESS, PART10)
    support = Calc(method, combo)
    support.step("t_{min}", r"\frac{3.09 D}{F_u}", t_min, Kind.THICKNESS,
                 "AISC Manual 16th ed., Eq. 9-6")
    return [
        _bolts(sp, R, method, combo),
        _max_thickness(sp, method, combo),
        shear_y,
        _rename("shear_rupture", elements.shear_rupture((L - n * hole) * t, Fu, R, method,
                                                        combo)),
        block, flex_y, ltb, interaction,
        _rename("flexural_rupture", elements.flexural_rupture(Znet, Fu, M, method, combo)),
        weld.result("extended_plate.weld_size", PART10, 5 * t / 8, sp.weld, Kind.THICKNESS),
        support.result("extended_plate.support_thickness", "AISC Manual 16th ed., Eq. 9-6",
                       t_min, sp.support_t, Kind.THICKNESS),
    ]
