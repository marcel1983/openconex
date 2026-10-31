# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Seismic base connections (AISC DG1 3rd ed., Chapters 5 and 6; ACI 318-19 §17.10).

* Weak base with ductile anchor rods (DG1 §6.4): reduced (upset-thread) section
  that yields, stretch length, and capacity design of the nonductile limit
  states for n Rt T_reduced.
* Embedded base, Type I (DG1 §5.2): horizontal bearing moment strength M_HB.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from openconex.core.checks import CheckResult
from openconex.core.loads import Method
from openconex.kernel.design import Calc
from openconex.units import Kind, from_internal, to_internal

__all__ = ["DuctileAnchors", "ductile_anchors", "embedded_base_moment", "face_plate_design"]

DG1 = "AISC DG1 3rd ed."
PHI_T = 0.9


@dataclass(frozen=True)
class DuctileAnchors:
    A_reduced_min: float
    T_reduced: float
    RtT_reduced: float
    N_required: float
    L_stretch_min: float


def ductile_anchors(T: float, rods_per_side: int, Fy: float, Fu: float, d_reduced: float,
                    f: float, d_rod: float, Rt: float = 1.2) -> DuctileAnchors:
    """Ductile anchor rods with a reduced section (DG1 §6.4.2, Example 6.4-1).

    A_reduced ≥ T/(n φt Fy); T_reduced = A_reduced Fu; nonductile limit states
    are designed for n Rt T_reduced. Stretch length ≥ max(8 da, f).
    """
    a_min = T / (rods_per_side * PHI_T * Fy)
    t_red = math.pi * d_reduced**2 / 4 * Fu
    return DuctileAnchors(a_min, t_red, Rt * t_red, rods_per_side * Rt * t_red,
                          max(8 * d_rod, f))


def embedded_base_moment(V: float, d_embed: float, bf: float, bw: float, fc: float,
                         demand: float, beta1: float = 0.85, combo: str = "",
                         bj: float | None = None, F_rebar_top: float = 0.0,
                         F_rebar_bottom: float = 0.0, d_rebar_top: float = 0.0,
                         d_rebar_bottom: float = 0.0,
                         damage_limit: bool = False) -> CheckResult:
    """Type I embedded-base moment strength (DG1 Eq. 5-1 and 5-6), φ = 0.75.

    ``bj`` is the effective concrete panel width; ``b_f`` when no embedded plate
    is provided, or ``(b_f + B)/2`` with an embedded plate. ``F_rebar`` and
    ``d_rebar`` are the forces and depths of the horizontal reinforcement
    layers; zero when no attached reinforcement is present.
    """
    clause = f"{DG1} §5.2, Eq. 5-6"
    c = Calc(Method.LRFD, combo)
    fc_ksi = from_internal(fc, Kind.STRESS, "ksi")
    fb = c.step("f_b", r"1.54\sqrt{f'_c}\left(\frac{b_w}{b_f}\right)^{0.66} \le 1.7f'_c",
                to_internal(min(1.54 * math.sqrt(fc_ksi) * (bw / bf) ** 0.66, 1.7 * fc_ksi),
                            "ksi", Kind.STRESS), Kind.STRESS, f"{DG1} Eq. 5-1")
    bj = bf if bj is None else bj
    if bj != bf:
        c.step("b_j", r"\frac{b_f + B}{2}", bj, Kind.LENGTH, f"{DG1} §5.2")
    forces = (F_rebar_top, F_rebar_bottom, d_rebar_top, d_rebar_bottom)
    if any(forces):
        c.step("F_{rebar,top}", "A_{sr,top}F_{ysr,top}", F_rebar_top, Kind.FORCE,
               f"{DG1} §5.2")
        c.step("F_{rebar,bottom}", "A_{sr,bottom}F_{ysr,bottom}", F_rebar_bottom,
               Kind.FORCE, f"{DG1} §5.2")
        c.step("d_{rebar,top}", "", d_rebar_top, Kind.LENGTH, f"{DG1} §5.2")
        c.step("d_{rebar,bottom}", "", d_rebar_bottom, Kind.LENGTH, f"{DG1} §5.2")
    m = ((F_rebar_top - F_rebar_bottom - V) * d_embed / 2
         - (F_rebar_bottom - F_rebar_top + V) ** 2 / (4 * bj * fb)
         - beta1 * bj * d_embed**2 * fb * (beta1 - 2) / 4
         - F_rebar_top * d_rebar_top + F_rebar_bottom * d_rebar_bottom)
    expression = (r"\frac{(F_{r,t}-F_{r,b}-V)d}{2} - "
                  r"\frac{(F_{r,b}-F_{r,t}+V)^2}{4b_jf_b} - "
                  r"\frac{\beta_1 b_j d^2 f_b(\beta_1-2)}{4} - "
                  r"F_{r,t}d_{r,t} + F_{r,b}d_{r,b}")
    m = c.step("M_{HB}", expression, m, Kind.MOMENT, clause)
    factor = 0.75 * (0.8 if damage_limit else 1.0)
    cap = c.step(r"\phi M_{HB}", "0.75(0.8 M_{HB})" if damage_limit else "0.75 M_{HB}",
                 factor * m, Kind.MOMENT, clause)
    return c.result("base_plate.embedded_moment", clause, demand, cap, Kind.MOMENT)


def face_plate_design(P: float, d: float, bf: float, tf: float, tw: float, fc: float,
                      Fy: float) -> dict[str, float]:
    """Face bearing plates on top of the foundation (DG1 §5.3, Eq. 5-7, 5-8).

    The minimum seismic thickness is ``max(0.75 tw, 3/8 in.)``.
    """
    a1 = (bf - tw) * (d - 2 * tf)
    l_crit = math.sqrt(d * bf) / 4
    return {
        "A1": a1,
        "phiPp": 0.65 * 1.7 * fc * a1,
        "l": l_crit,
        "tp_min": l_crit * math.sqrt(max(2 * P, 0.0) / (0.9 * Fy * a1)),
        "tp_min_seismic": max(0.75 * tw, to_internal(0.375, "in", Kind.THICKNESS)),
    }
