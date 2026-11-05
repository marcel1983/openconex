# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Extended single plate under shear and axial tension (AISC Manual Part 12; II.A-19B).

The plate of :class:`~openconex.connections.shear.extended_single_plate.ExtendedSinglePlate`
carries the beam shear ``V`` and an axial tension ``N``. Limit states:

* bolt group: C from the instantaneous centre for the resultant at angle
  ``theta = atan(N/V)`` from the vertical, times the least single-bolt strength
  (bolt shear, bearing and tearout on the plate and on the beam web);
* plate shear yielding and rupture, tensile yielding and rupture, flexural
  yielding (F11.1), lateral-torsional buckling (F11.2, C_b = 1.84) and flexural
  rupture (Manual Eq. 9-8);
* interaction of axial, flexure and shear (Manual Eq. 12-2 and 12-3);
* block shear in the shear direction (L), in the axial direction (L and U) and
  their interaction (Manual Eq. 12-1), for two bolt lines;
* maximum plate thickness of the extended configuration (Manual Eq. 10-6/10-7);
* weld size and support thickness.

The beam limit states and the column-web yield line of the example are not
checked here.
"""

from __future__ import annotations

import math

from openconex.core.checks import CheckResult
from openconex.core.loads import Method
from openconex.core.materials import E_STEEL
from openconex.kernel import bolts, elements
from openconex.kernel.bolt_group import icr_coefficient
from openconex.kernel.design import FLEXURE, Calc
from openconex.units import Kind, to_internal

from .double_angle import SPEC, _hole_net
from .extended_single_plate import (
    ExtendedSinglePlate,
    _group,
    check_extended_single_plate,
)

__all__ = ["check_extended_single_plate_axial"]

PART12 = "AISC Manual 16th ed., Part 12"
CB = 1.84


def _rename(check: CheckResult, key: str | None = None) -> CheckResult:
    suffix = key or check.id.split(".", 1)[1]
    return check.model_copy(update={"id": f"extended_plate.{suffix}",
                                    "text_id": f"check.extended_plate.{suffix}"})


def _bolts(sp: ExtendedSinglePlate, V: float, N: float, method: Method, combo: str,
           angle: float | None) -> CheckResult:
    c = Calc(method, combo)
    clause = f"{SPEC} §§J3.7, §§J3.11; {PART12}"
    b, dh = sp.bolt, sp.bolt.hole_dimensions[0]
    kw = {"deformation_considered": sp.deformation_considered}
    shear = c.step(r"r_{n,bolt}", "", bolts.bolt_shear(b, 0.0, method).capacity, Kind.FORCE,
                   f"{SPEC} §§J3.7")
    underrun = to_internal(0.25, "in", Kind.LENGTH)
    lc_web = c.step(r"l_{c,web}", r"l_{eh,web} - d_h/2 - \mathrm{underrun}",
                    (sp.beam_leh or sp.leh) - dh / 2 - underrun, Kind.LENGTH, f"{SPEC} §§J3.11")
    lc_plate = c.step(r"l_{c,plate}", r"\min(l_{ev}, l_{eh}) - d_h/2",
                      min(sp.lev, sp.leh) - dh / 2, Kind.LENGTH, f"{SPEC} §§J3.11")
    per_bolt = [shear]
    for t, Fu, lc, name in ((sp.beam_tw, sp.beam_Fu, lc_web, "web"),
                            (sp.thickness, sp.plate_Fu, lc_plate, "plate")):
        per_bolt.append(c.step(rf"r_{{n,bearing,{name}}}", r"k\,d t F_u",
                               bolts.bolt_bearing(b, t, Fu, 0.0, method, **kw).capacity,
                               Kind.FORCE, f"{SPEC} §§J3.11(a)"))
        per_bolt.append(c.step(rf"r_{{n,tearout,{name}}}", r"k\,l_c t F_u",
                               bolts.bolt_tearout(b, t, Fu, lc, 0.0, method, **kw).capacity,
                               Kind.FORCE, f"{SPEC} §§J3.11(b)"))
    rn = c.step(r"r_n", r"\min", min(per_bolt), Kind.FORCE, clause)
    theta = c.step(r"\theta", r"\tan^{-1}(N/V)",
                   math.degrees(math.atan2(N, V)) if angle is None else angle,
                   clause=PART12)
    load_point = (-sp.a, (sp.rows - 1) * sp.spacing / 2)
    C = c.step("C", "IC", icr_coefficient(_group(sp), load_point, theta).C,
               clause=f"{PART12} (e = a + (n_l - 1)g/2)")
    return c.result("extended_plate.bolts", clause, math.hypot(V, N),
                    c.step(r"C r_n", "", C * rn, Kind.FORCE, clause), Kind.FORCE)


def _ltb(sp: ExtendedSinglePlate, M: float, method: Method, combo: str) -> CheckResult:
    c = Calc(method, combo)
    clause = f"{SPEC} §§F11.2"
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


def _interaction(key: str, N: float, Nc: float, M: float, Mc: float, V: float, Vc: float,
                 method: Method, combo: str) -> CheckResult:
    c = Calc(method, combo)
    n = c.step(r"\frac{N}{N_c}", "", N / Nc, clause=PART12)
    if n < 0.2:
        value = (n / 2 + M / Mc) ** 2 + (V / Vc) ** 2
        clause, expr = f"{PART12}, Eq. 12-2", (r"\left(\frac{N}{2N_c} + \frac{M}{M_c}\right)^2"
                                               r" + \left(\frac{V}{V_c}\right)^2")
    else:
        value = (n + 8 / 9 * M / Mc) ** 2 + (V / Vc) ** 2
        clause, expr = f"{PART12}, Eq. 12-3", (r"\left(\frac{N}{N_c} + \frac{8}{9}"
                                               r"\frac{M}{M_c}\right)^2 + \left(\frac{V}{V_c}"
                                               r"\right)^2")
    c.step("U", expr, value, clause=clause)
    return c.result(f"extended_plate.{key}", clause, value, 1.0, Kind.DIMENSIONLESS)


def _block(check: CheckResult, key: str) -> CheckResult:
    return _rename(check, key)


def check_extended_single_plate_axial(sp: ExtendedSinglePlate, V: float, N: float,
                                      method: Method, combo: str = "",
                                      angle: float | None = None) -> list[CheckResult]:
    """Limit states for the beam shear ``V`` and axial tension ``N`` (both ≥ 0)."""
    if N <= 0:
        return check_extended_single_plate(sp, V, method, combo)
    if sp.lines < 1:
        raise ValueError("extended single plate needs at least one bolt line")
    t, L, n, m = sp.thickness, sp.length, sp.rows, sp.lines
    Fy, Fu = sp.plate_Fy, sp.plate_Fu
    hole = _hole_net(sp.bolt)
    M = V * sp.a
    Z, S = t * L**2 / 4, t * L**2 / 6
    center = (n - 1) * sp.spacing / 2
    ys = [abs(i * sp.spacing - center) for i in range(n)]
    Znet = Z - sum(t * hole * y if y >= hole / 2 else t * hole**2 / 4 for y in ys)

    shear_y = _rename(elements.shear_yielding(L * t, Fy, V, method, combo), "shear_yielding")
    shear_r = _rename(elements.shear_rupture((L - n * hole) * t, Fu, V, method, combo),
                      "shear_rupture")
    tens_y = _rename(elements.tension_yielding(L * t, Fy, N, method, combo),
                     "tension_yielding")
    tens_r = _rename(elements.tension_rupture((L - n * hole) * t, Fu, N, method, combo),
                     "tension_rupture")
    flex_y = _rename(elements.flexural_yielding(min(Z, 1.5 * S), Fy, M, method, combo),
                     "flexural_yielding")
    ltb = _ltb(sp, M, method, combo)
    flex_r = _rename(elements.flexural_rupture(Znet, Fu, M, method, combo),
                     "flexural_rupture")

    # Block shear of the plate: L-shape in the shear direction (Ubs = 0.5).
    agv_v = (L - sp.lev) * t
    anv_v = agv_v - (n - 0.5) * hole * t
    ant_v = (sp.leh + (m - 1) * sp.gage - (m - 0.5) * hole) * t
    block_v = _block(elements.block_shear(agv_v, anv_v, ant_v, Fy, Fu, V, method,
                                          Ubs=0.5, combo=combo), "block_shear")

    # Axial direction: L-shape and U-shape (Ubs = 1.0).
    agv_l = ((m - 1) * sp.gage + sp.leh) * t
    anv_l = agv_l - (m - 0.5) * hole * t
    ant_l = (sp.lev + (n - 1) * sp.spacing - (n - 0.5) * hole) * t
    block_l = elements.block_shear(agv_l, anv_l, ant_l, Fy, Fu, N, method, Ubs=1.0,
                                   combo=combo)
    agv_u = 2 * ((m - 1) * sp.gage + sp.leh) * t
    anv_u = agv_u - 2 * (m - 0.5) * hole * t
    ant_u = ((n - 1) * sp.spacing - (n - 1) * hole) * t
    block_u = elements.block_shear(agv_u, anv_u, ant_u, Fy, Fu, N, method, Ubs=1.0,
                                   combo=combo)
    block_n = _block(min(block_l, block_u, key=lambda r: r.capacity), "block_shear_axial")

    c = Calc(method, combo)
    clause = f"{PART12}, Eq. 12-1"
    u = c.step("U", r"\left(\frac{V}{R_{v}}\right)^2 + \left(\frac{N}{R_{t}}\right)^2",
               (V / block_v.capacity) ** 2 + (N / block_n.capacity) ** 2, clause=clause)
    block_i = c.result("extended_plate.block_shear_interaction", clause, u, 1.0,
                       Kind.DIMENSIONLESS)

    flex_cap = min(flex_y.capacity, ltb.capacity)
    support = _rename(elements.shear_rupture(2 * L * sp.support_t, sp.support_Fu, V,
                                             method, combo), "support_shear_rupture")
    base = {check.id: check for check in check_extended_single_plate(sp, V, method, combo)}
    return [
        _bolts(sp, V, N, method, combo, angle),
        shear_y, tens_y, flex_y, ltb,
        _interaction("interaction_yielding", N, tens_y.capacity, M, flex_cap, V,
                     shear_y.capacity, method, combo),
        shear_r, tens_r, flex_r,
        _interaction("interaction_rupture", N, tens_r.capacity, M, flex_r.capacity, V,
                     shear_r.capacity, method, combo),
        block_v, block_n, block_i, support,
        base["extended_plate.max_thickness"],
        base["extended_plate.weld_size"], base["extended_plate.support_thickness"],
    ]
