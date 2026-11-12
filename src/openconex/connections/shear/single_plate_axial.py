# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Single plate under shear and axial tension (AISC Manual Part 12; Design Example II.A-17B).

The plate of :class:`~openconex.connections.shear.single_plate.SinglePlate`
carries the beam shear V and an axial tension N. Following the Manual Part 12
method, the plate is a cantilever from the weld with M = V e, e = a. Limit states:

* bolts: C times the least single-bolt strength (bolt shear, bearing and
  tearout on the plate and on the beam web), C from the instantaneous center
  for the resultant at angle θ = atan(N/V) from the vertical. Tearout uses the
  worst edge distance because the direction of the bolt force is not known:
  l_ev on the plate and l_eh minus the length underrun on the beam web;
* plate shear yielding and rupture, tensile yielding and rupture, flexural
  yielding (F11.1) and lateral-torsional buckling (F11.2, C_b = 1.84) and
  flexural rupture (Manual Eq. 9-8);
* interaction of axial, flexure and shear (Manual Eq. 12-2 and 12-3) for
  yielding and for rupture;
* block shear in the shear direction (L), in the axial direction (L and U) and
  their interaction (Manual Eq. 12-1);
* shear rupture of the support on two planes, weld size w ≥ 5/8 t_p and the
  support thickness that develops it.

The beam itself (web shear, tension, block shear of the web) is not checked.
"""

from __future__ import annotations

import math

from openconex.core.checks import CheckResult
from openconex.core.loads import Method
from openconex.core.materials import E_STEEL
from openconex.kernel import bolts, elements
from openconex.kernel.bolt_group import icr_coefficient
from openconex.kernel.design import FLEXURE, Calc, Resistance
from openconex.units import Kind, to_internal

from .double_angle import SPEC, _hole_net
from .plate_compression import plate_compression
from .single_plate import SinglePlate, check_single_plate

__all__ = ["check_single_plate_axial"]

PART12 = "AISC Manual 16th ed., Part 12"
FLEXURAL_RUPTURE = Resistance(0.75, 2.00)
CB = 1.84
"""Lateral-torsional buckling modification factor for single plates (Manual Part 10)."""


def _rename(key: str, check: CheckResult) -> CheckResult:
    return check.model_copy(update={"id": f"single_plate.{key}",
                                    "text_id": f"check.single_plate.{key}"})


def _bolts(sp: SinglePlate, V: float, N: float, method: Method, combo: str,
           underrun: float, angle: float | None) -> CheckResult:
    c = Calc(method, combo)
    clause = f"{SPEC} §J3.7, §J3.11; {PART12}"
    b, dh = sp.bolt, sp.bolt.hole_dimensions[0]
    kw = {"deformation_considered": sp.deformation_considered}
    shear = c.step(r"r_{n,bolt}", "", bolts.bolt_shear(b, 0.0, method).capacity, Kind.FORCE,
                   f"{SPEC} §J3.7")
    lc_web = c.step(r"l_{c,web}", r"l_{eh,web} - d_h/2 - \mathrm{underrun}",
                    (sp.beam_leh or sp.leh) - dh / 2 - underrun, Kind.LENGTH, f"{SPEC} §J3.11")
    lc_plate = c.step(r"l_{c,plate}", r"\min(l_{ev}, l_{eh}) - d_h/2",
                      min(sp.lev, sp.leh) - dh / 2, Kind.LENGTH, f"{SPEC} §J3.11")
    per_bolt = [shear]
    for t, Fu, lc, name in ((sp.beam_tw, sp.beam_Fu, lc_web, "web"),
                            (sp.thickness, sp.plate_Fu, lc_plate, "plate")):
        per_bolt.append(c.step(rf"r_{{n,bearing,{name}}}", r"k\,d t F_u",
                               bolts.bolt_bearing(b, t, Fu, 0.0, method, **kw).capacity,
                               Kind.FORCE, f"{SPEC} §J3.11(a)"))
        per_bolt.append(c.step(rf"r_{{n,tearout,{name}}}", r"k\,l_c t F_u",
                               bolts.bolt_tearout(b, t, Fu, lc, 0.0, method, **kw).capacity,
                               Kind.FORCE, f"{SPEC} §J3.11(b)"))
    rn = c.step(r"r_n", r"\min", min(per_bolt), Kind.FORCE, clause)
    theta = c.step(r"\theta", r"\tan^{-1}(N/V)",
                   math.degrees(math.atan2(N, V)) if angle is None else angle,
                   clause=PART12)
    group = [(0.0, sp.spacing * i) for i in range(sp.rows)]
    C = c.step("C", "IC", icr_coefficient(group, (sp.a, sp.spacing * (sp.rows - 1) / 2),
                                          theta).C, clause=f"{PART12} (e = a)")
    return c.result("single_plate.bolts", clause, math.hypot(V, N), c.step(
        r"C r_n", "", C * rn, Kind.FORCE, clause), Kind.FORCE)


def _ltb(sp: SinglePlate, M: float, method: Method, combo: str) -> CheckResult:
    """Lateral-torsional buckling of the rectangular plate (AISC 360-22 §F11.2)."""
    c = Calc(method, combo)
    clause = f"{SPEC} §F11.2"
    t, d, Fy = sp.thickness, sp.length, sp.plate_Fy
    Z, S = t * d**2 / 4, t * d**2 / 6
    ratio = c.step(r"\frac{L_b d}{t^2}", "", sp.a * d / t**2, clause=clause,
                   L_b=(sp.a, Kind.LENGTH))
    Mp = min(Fy * Z, 1.5 * Fy * S)
    if ratio <= 0.08 * E_STEEL / Fy:
        mn = c.step("M_n", "M_p", Mp, Kind.MOMENT, f"{SPEC} Eq. F11-1")
    elif ratio <= 1.9 * E_STEEL / Fy:
        mn = c.step("M_n", r"C_b\left[1.52 - 0.274\frac{L_b d}{t^2}\frac{F_y}{E}\right]M_y"
                    r" \le M_p", min(CB * (1.52 - 0.274 * ratio * Fy / E_STEEL) * Fy * S, Mp),
                    Kind.MOMENT, f"{SPEC} Eq. F11-3", C_b=(CB, Kind.DIMENSIONLESS))
    else:
        fcr = c.step("F_{cr}", r"\frac{1.9 E C_b}{L_b d/t^2}", 1.9 * E_STEEL * CB / ratio,
                     Kind.STRESS, f"{SPEC} Eq. F11-4")
        mn = c.step("M_n", r"F_{cr}S_x \le M_p", min(fcr * S, Mp), Kind.MOMENT,
                    f"{SPEC} Eq. F11-4")
    return c.result("single_plate.flexural_ltb", clause, M,
                    c.available(mn, FLEXURE, Kind.MOMENT, clause, "M_n"), Kind.MOMENT)


def _interaction(key: str, N: float, Nc: float, M: float, Mc: float, V: float, Vc: float,
                 method: Method, combo: str) -> CheckResult:
    """Manual Eq. 12-2 (N/Nc < 0.2) or 12-3, with the minor-axis term taken as zero."""
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
    return c.result(f"single_plate.{key}", clause, value, 1.0, Kind.DIMENSIONLESS)


def check_single_plate_axial(sp: SinglePlate, V: float, N: float, method: Method,
                             combo: str = "", underrun: float | None = None,
                             angle: float | None = None,
                             compression: bool = False) -> list[CheckResult]:
    """Limit states for the beam shear ``V`` and the axial force ``N`` (both ≥ 0).

    ``N`` is tension unless ``compression`` is true: then the plate is checked
    for compression buckling (§J4.4) instead of tensile yielding and rupture,
    and the axial block shear does not apply.

    ``underrun`` is the beam length tolerance subtracted from the web edge
    distance (default 1/4 in.). ``angle`` overrides the load angle used for C
    (the Manual examples use the tabulated 30° conservatively).
    """
    if N <= 0:
        return check_single_plate(sp, V, method, combo)
    if underrun is None:
        underrun = to_internal(0.25, "in", Kind.LENGTH)
    t, L, hole, n = sp.thickness, sp.length, _hole_net(sp.bolt), sp.rows
    Fy, Fu = sp.plate_Fy, sp.plate_Fu
    M = V * sp.a
    Z = t * L**2 / 4
    S = t * L**2 / 6
    center = (n - 1) * sp.spacing / 2
    ys = [abs(i * sp.spacing - center) for i in range(n)]
    Znet = Z - sum(t * hole * y if y >= hole / 2 else t * hole**2 / 4 for y in ys)

    shear_y = _rename("shear_yielding", elements.shear_yielding(L * t, Fy, V, method, combo))
    shear_r = _rename("shear_rupture", elements.shear_rupture((L - n * hole) * t, Fu, V,
                                                              method, combo))
    tens_y = _rename("tension_yielding", elements.tension_yielding(L * t, Fy, N, method, combo))
    tens_r = _rename("tension_rupture", elements.tension_rupture((L - n * hole) * t, Fu, N,
                                                                 method, combo))
    flex_y = _rename("flexural_yielding", elements.flexural_yielding(min(Z, 1.5 * S), Fy, M,
                                                                     method, combo))
    ltb = _ltb(sp, M, method, combo)
    flex_r = _rename("flexural_rupture", elements.flexural_rupture(Znet, Fu, M, method, combo))

    agv = (L - sp.lev) * t
    block_v = _rename("block_shear", elements.block_shear(
        agv, agv - (n - 0.5) * hole * t, (sp.leh - 0.5 * hole) * t, Fy, Fu, V, method,
        combo=combo))
    block_l = elements.block_shear(sp.leh * t, (sp.leh - 0.5 * hole) * t,
                                   (L - sp.lev - (n - 0.5) * hole) * t, Fy, Fu, N, method,
                                   combo=combo)
    block_u = elements.block_shear(2 * sp.leh * t, 2 * (sp.leh - 0.5 * hole) * t,
                                   (L - 2 * sp.lev - (n - 1) * hole) * t, Fy, Fu, N, method,
                                   combo=combo)
    block_n = _rename("block_shear_axial", min(block_l, block_u, key=lambda r: r.capacity))

    c = Calc(method, combo)
    clause = f"{PART12}, Eq. 12-1"
    u = c.step("U", r"\left(\frac{V}{R_{v}}\right)^2 + \left(\frac{N}{R_{t}}\right)^2",
               (V / block_v.capacity) ** 2 + (N / block_n.capacity) ** 2, clause=clause)
    block_i = c.result("single_plate.block_shear_interaction", clause, u, 1.0,
                       Kind.DIMENSIONLESS)

    flex_cap = min(flex_y.capacity, ltb.capacity)
    support = _rename("support_shear_rupture", elements.shear_rupture(
        2 * L * sp.support_t, sp.support_Fu, V, method, combo))
    dims = {r.id: r for r in check_single_plate(sp, V, method, combo)}
    if compression:
        comp = plate_compression("single_plate", L, t, sp.a, Fy, N, method, combo)
        return [
            _bolts(sp, V, N, method, combo, underrun, angle),
            shear_y, comp, flex_y, ltb,
            _interaction("interaction_yielding", N, comp.capacity, M, flex_cap, V,
                         shear_y.capacity, method, combo),
            shear_r, flex_r, block_v, support,
            dims["single_plate.weld_size"], dims["single_plate.support_thickness"],
        ]
    return [
        _bolts(sp, V, N, method, combo, underrun, angle),
        shear_y, tens_y, flex_y, ltb,
        _interaction("interaction_yielding", N, tens_y.capacity, M, flex_cap, V,
                     shear_y.capacity, method, combo),
        shear_r, tens_r, flex_r,
        _interaction("interaction_rupture", N, tens_r.capacity, M, flex_r.capacity, V,
                     shear_r.capacity, method, combo),
        block_v, block_n, block_i, support,
        dims["single_plate.weld_size"], dims["single_plate.support_thickness"],
    ]
