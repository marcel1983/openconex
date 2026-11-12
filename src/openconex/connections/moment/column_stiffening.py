# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Column stiffening at moment connections (AISC Design Guide 13, 1999, rev. 2003).

Transverse stiffeners (continuity plates), wind and low-seismic applications:

* required strength R_ust = P_uf − φR_n,min of the column flange and web limit
  states (Eq. 4.2-1), against the stiffener area 2(b_s − clip)t_s (Eq. 4.3-1);
* minimum width b_s ≥ b/3 − t_pz/2 (Eq. 4.3-2) and thickness
  t_s ≥ max(t/2, b_s√F_y/95) (Eq. 4.3-3, F_y in ksi);
* minimum length, half the clear web depth for partial-depth stiffeners;
* shear in the stiffeners transferring the force to the panel zone (Eq. 4.3-4,
  4.3-5), the fillet welds to the column flanges (Eq. 4.3-6) and to the web
  (Eq. 4.3-9, 4.3-10), and the column web (or doubler) carrying it (Eq. 4.4-2,
  4.4-3).

Web doubler plates: shear buckling, t_d ≥ h√F_y/418 (Eq. 4.4-5), and, for a
fillet-welded edge with a bevel equal to the plate thickness, the weld to the
column flanges (Eq. 4.4-7). The doubler adds to the panel zone strength in
:mod:`openconex.connections.moment.panel_zone`.

Design Guide 13 uses φ = 0.9 for shear yielding of the stiffeners and the
panel zone (LRFD 1993); the same factor (Ω = 1.67 in ASD) is kept here.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from openconex.core.checks import CheckResult
from openconex.core.loads import Method
from openconex.kernel.design import TENSION_YIELD, Calc, Resistance, available
from openconex.kernel.welds import fillet_weld_per_length
from openconex.units import Kind, from_internal

if TYPE_CHECKING:
    from .fr_moment import MomentConnection

__all__ = ["doubler_checks", "stiffener_checks"]

DG13 = "AISC Design Guide 13"
SPEC = "AISC 360-22"
SHEAR = Resistance(0.90, 1.67)
L, T, F = Kind.LENGTH, Kind.THICKNESS, Kind.FORCE


def _ksi(stress: float) -> float:
    return from_internal(stress, Kind.STRESS, "ksi")


def stiffener_length(mc: MomentConnection) -> float:
    col = mc.column
    clear = col.d - 2 * col.tf
    if mc.continuity_plate_length > 0:
        return mc.continuity_plate_length
    return clear if mc.continuity_plate_full_depth else clear / 2


def stiffener_width(mc: MomentConnection) -> float:
    col = mc.column
    return mc.continuity_plate_width or (col.bf - col.tw) / 2


def stiffener_checks(mc: MomentConnection, Puf: float, strengths: list[float], b: float,
                     t: float, method: Method, combo: str = "") -> list[CheckResult]:
    """Continuity plate checks for the flange force ``Puf`` delivered by a flange or plate
    of width ``b`` and thickness ``t``; ``strengths`` are the available strengths of the
    unstiffened column limit states."""
    col = mc.column
    ts = mc.continuity_plate
    bs = stiffener_width(mc)
    clip = mc.continuity_plate_clip
    Fy = mc.plate_Fy or col.material.Fy
    length = stiffener_length(mc)
    ends = 2 if mc.continuity_plate_full_depth else 1
    out: list[CheckResult] = []

    c = Calc(method, combo)
    clause = f"{DG13}, Eq. 4.2-1, 4.3-1; {SPEC} §J10.8"
    rust = c.step("R_{ust}", r"P_{uf} - \phi R_{n,min}", max(Puf - min(strengths), 0.0), F,
                  clause, P_uf=(Puf, F))
    area = c.step("A_{st}", r"2(b_s - clip)t_s", 2 * (bs - clip) * ts, Kind.AREA, clause,
                  b_s=(bs, L), t_s=(ts, T))
    cap = c.available(Fy * area, TENSION_YIELD, F, clause, "F_y A_{st}")
    out.append(c.result("moment.continuity_plates", clause, rust, cap, F))

    c = Calc(method, combo)
    clause = f"{DG13}, Eq. 4.3-2; {SPEC} §J10.8"
    need = c.step("b_{s,min}", r"\frac{b}{3} - \frac{t_{pz}}{2}", b / 3 - col.tw / 2, L, clause,
                  b=(b, L))
    out.append(c.result("moment.continuity_plate_width", clause, need, bs, L))

    c = Calc(method, combo)
    clause = f"{DG13}, Eq. 4.3-3; {SPEC} §J10.8"
    need = c.step("t_{s,min}", r"\max\left(\frac{t}{2},\ \frac{b_s\sqrt{F_y}}{95}\right)",
                  max(t / 2, bs * math.sqrt(_ksi(Fy)) / 95), T, clause, t=(t, T))
    out.append(c.result("moment.continuity_plate_thickness", clause, need, ts, T))

    if not mc.continuity_plate_full_depth:
        c = Calc(method, combo)
        clause = f"{DG13}, §4.3.3; {SPEC} §J10.8"
        need = c.step("l_{min}", r"\frac{d_c - 2t_{fc}}{2}", (col.d - 2 * col.tf) / 2, L,
                      clause)
        out.append(c.result("moment.continuity_plate_length", clause, need, length, L))

    # force transferred to the panel zone: both ends add with beams on both flanges
    total = 2 * rust if (mc.two_sided and ends == 2) else rust
    net = length - ends * clip
    c = Calc(method, combo)
    clause = f"{DG13}, Eq. 4.3-4, 4.3-5"
    c.step("R_{ust,1} + R_{ust,2}", "", total, F, clause)
    rn = c.step("R_n", r"0.6 F_y (l - n\,clip)\,2t_s", 0.6 * Fy * net * 2 * ts, F, clause,
                l=(length, L))
    out.append(c.result("moment.continuity_plate_shear", clause, total,
                        c.available(rn, SHEAR, F, clause), F))

    if mc.continuity_plate_weld > 0:
        c = Calc(method, combo)
        clause = f"{DG13}, Eq. 4.3-6; {SPEC} §J2.4, Eq. J2-5"
        need = c.step(r"F_y t_s", "", available(Fy * ts, TENSION_YIELD, method),
                      Kind.FORCE_PER_LENGTH, clause)
        rw = fillet_weld_per_length(mc.continuity_plate_weld, mc.FEXX, 0.0, method).capacity
        cap = c.step("r_n", r"2 \times 1.5\,r_w", 2 * 1.5 * rw, Kind.FORCE_PER_LENGTH, clause,
                     w=(mc.continuity_plate_weld, T))
        out.append(c.result("moment.continuity_plate_flange_weld", clause, need, cap,
                            Kind.FORCE_PER_LENGTH))

    if mc.continuity_plate_web_weld > 0:
        c = Calc(method, combo)
        clause = f"{DG13}, Eq. 4.3-9, 4.3-10; {SPEC} §J2.4"
        rw = fillet_weld_per_length(mc.continuity_plate_web_weld, mc.FEXX, 0.0, method).capacity
        cap = c.step("R_n", r"4 r_w (l - n\,clip)", 4 * rw * net, F, clause,
                     w=(mc.continuity_plate_web_weld, T))
        out.append(c.result("moment.continuity_plate_web_weld", clause, total, cap, F))

    c = Calc(method, combo)
    clause = f"{DG13}, Eq. 4.4-2, 4.4-3"
    sheets = [(col.material.Fy, col.tw)]
    if mc.doubler_plate > 0:
        sheets.append((Fy, mc.doubler_plate))
    fyt = min(fy * tt for fy, tt in sheets)
    rn = c.step("R_n", r"\min[0.6 F_y t\,4(l - n\,clip),\ 0.6 F_y t\,2d_c]",
                min(0.6 * fyt * 4 * net, 0.6 * fyt * 2 * col.d), F, clause)
    out.append(c.result("moment.continuity_plate_web_shear", clause, total,
                        c.available(rn, SHEAR, F, clause), F))
    return out


def doubler_checks(mc: MomentConnection, method: Method, combo: str = "",
                   panel_demand: float | None = None,
                   web_strength: float | None = None) -> list[CheckResult]:
    """Web doubler plate: shear buckling and, with ``doubler_weld``, the fillet weld to the
    column flanges for the shear the doubler carries (``panel_demand`` less the available
    strength of the column web alone, ``web_strength``)."""
    col = mc.column
    td = mc.doubler_plate
    Fy = mc.plate_Fy or col.material.Fy
    out: list[CheckResult] = []
    c = Calc(method, combo)
    clause = f"{DG13}, Eq. 4.4-5"
    h = c.step("h", "d_c - 2t_{fc}", col.d - 2 * col.tf, L, clause)
    need = c.step("t_{d,min}", r"\frac{h\sqrt{F_y}}{418}", h * math.sqrt(_ksi(Fy)) / 418, T,
                  clause)
    out.append(c.result("moment.doubler_plate_buckling", clause, need, td, T))
    if mc.doubler_weld > 0 and panel_demand is not None and web_strength is not None:
        c = Calc(method, combo)
        clause = f"{DG13}, Eq. 4.2-2, 4.4-1, 4.4-7"
        vudp = c.step("V_{udp}", r"V_u - \phi R_{v,cw}", max(panel_demand - web_strength, 0.0),
                      F, clause)
        teff = c.step("t_{eff}", r"\frac{V_{udp}}{\phi\,0.6 F_y d_c}",
                      vudp / available(0.6 * Fy * col.d, SHEAR, method), T, clause)
        fexx = _ksi(mc.FEXX)
        need = c.step("w_{min}", r"\max\left(\frac{1.70 F_y t_{eff}}{F_{EXX}},\ "
                      r"\sqrt{2}\,t_{eff}\right)",
                      max(1.70 * _ksi(Fy) * teff / fexx, math.sqrt(2) * teff), T, clause)
        out.append(c.result("moment.doubler_plate_weld", clause, need, mc.doubler_weld, T))
    return out

