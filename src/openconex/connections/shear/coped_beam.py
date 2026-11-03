# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Strength of a coped beam end (AISC Manual Part 9; Design Examples II.A-4, II.A-6, II.A-7).

The beam end reaction R acts at e = c + setback from the end of the cope.
Limit states:

* flexure of the coped section, R = M_n / e (Manual Eq. 9-9):

  - coped at the top flange only: flexural yielding and local web buckling with
    the plate buckling coefficients f and k (Manual Eq. 9-10 to 9-20);
  - coped at both flanges: lateral-torsional buckling of the remaining web as a
    rectangular bar (AISC 360-22 §F11), L_b = c and C_b per Manual Eq. 9-21;

* shear yielding and shear rupture of the reduced web (§J4.2);
* block shear of the web for a bolted connection when ``leh`` is given (one line of bolts, U_bs = 1;
  two lines, U_bs = 0.5), with the beam length underrun subtracted from l_eh.

The section properties of the tee left by a top cope are computed without
fillets, like Manual Table 9-2.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from openconex.core.checks import CheckResult
from openconex.core.loads import Method
from openconex.core.materials import E_STEEL
from openconex.kernel import elements
from openconex.kernel.design import FLEXURE, Calc
from openconex.units import Kind, to_internal

__all__ = ["CopedBeam", "check_coped_beam", "tee_properties"]

PART9 = "AISC Manual 16th ed., Part 9"
SPEC = "AISC 360-22"


@dataclass(frozen=True)
class CopedBeam:
    d: float
    tw: float
    bf: float
    tf: float
    Fy: float
    Fu: float
    c: float
    """Cope length."""
    dc: float
    """Cope depth at the top flange."""
    dc_bottom: float = 0.0
    """Cope depth at the bottom flange (0 when only the top flange is coped)."""
    setback: float = to_internal(0.5, "in", Kind.LENGTH)
    rows: int = 0
    """Bolts in each line through the web (0 for a welded connection)."""
    lines: int = 1
    spacing: float = 0.0
    lev: float = 0.0
    """Distance from the top of the coped web to the top bolt."""
    leh: float = 0.0
    """Distance from the end of the beam to the bolt line nearest to it."""
    gage: float = 0.0
    """Distance between bolt lines when ``lines`` = 2."""
    hole: float = 0.0
    """Hole width plus 1/16 in. for net areas."""
    underrun: float = to_internal(0.25, "in", Kind.LENGTH)


def tee_properties(cb: CopedBeam) -> tuple[float, float]:
    """(S_c, Z_c) of the tee left by a top cope, about its own centroid (no fillets)."""
    h = cb.d - cb.dc
    web = (h - cb.tf) * cb.tw
    flange = cb.bf * cb.tf
    area = web + flange
    y = (flange * cb.tf / 2 + web * (cb.tf + (h - cb.tf) / 2)) / area
    inertia = (cb.bf * cb.tf**3 / 12 + flange * (y - cb.tf / 2) ** 2
               + cb.tw * (h - cb.tf) ** 3 / 12 + web * (cb.tf + (h - cb.tf) / 2 - y) ** 2)
    S = inertia / max(y, h - y)
    half = area / 2
    if flange >= half:  # plastic neutral axis in the flange
        yp = half / cb.bf
        Z = (cb.bf * yp**2 / 2 + cb.bf * (cb.tf - yp) ** 2 / 2
             + web * (cb.tf + (h - cb.tf) / 2 - yp))
    else:
        yp = cb.tf + (half - flange) / cb.tw
        Z = (flange * (yp - cb.tf / 2) + cb.tw * (yp - cb.tf) ** 2 / 2
             + cb.tw * (h - yp) ** 2 / 2)
    return S, Z


def _flexure_top(cb: CopedBeam, c: Calc, e: float) -> float:
    hc = c.step("h_c", "d - d_c", cb.d - cb.dc, Kind.LENGTH, f"{PART9}, Fig. 9-2")
    cd, ch = cb.c / cb.d, cb.c / hc
    f = c.step("f", r"2c/d" if cd <= 1 else r"1 + c/d", 2 * cd if cd <= 1 else 1 + cd,
               clause=f"{PART9}, Eq. 9-20")
    k = c.step("k", r"2.2(h_c/c)^{1.65}" if ch <= 1 else r"2.2 h_c/c",
               2.2 * (hc / cb.c) ** 1.65 if ch <= 1 else 2.2 * hc / cb.c,
               clause=f"{PART9}, Eq. 9-19")
    k1 = c.step("k_1", r"f k \ge 1.61", max(f * k, 1.61), clause=f"{PART9}, Eq. 9-14")
    S, Z = tee_properties(cb)
    mp = c.step("M_p", "F_y Z_c", cb.Fy * Z, Kind.MOMENT, f"{PART9}, Eq. 9-15",
                Z_c=(Z, Kind.SECTION_MODULUS))
    my = c.step("M_y", "F_y S_c", cb.Fy * S, Kind.MOMENT, f"{PART9}, Eq. 9-16",
                S_c=(S, Kind.SECTION_MODULUS))
    lam = c.step(r"\lambda", "h_c/t_w", hc / cb.tw, clause=f"{PART9}, Eq. 9-17")
    lp = c.step(r"\lambda_p", r"0.475\sqrt{k_1 E/F_y}", 0.475 * math.sqrt(k1 * E_STEEL / cb.Fy),
                clause=f"{PART9}, Eq. 9-18")
    if lam <= lp:
        return c.step("M_n", "M_p", mp, Kind.MOMENT, f"{PART9}, Eq. 9-10")
    if lam <= 2 * lp:
        return c.step("M_n", r"M_p - (M_p - M_y)(\lambda/\lambda_p - 1)",
                      mp - (mp - my) * (lam / lp - 1), Kind.MOMENT, f"{PART9}, Eq. 9-11")
    fcr = c.step("F_{cr}", r"0.903 E k_1 (t_w/h_c)^2", 0.903 * E_STEEL * k1 * (cb.tw / hc) ** 2,
                 Kind.STRESS, f"{PART9}, Eq. 9-13")
    return c.step("M_n", "F_{cr} S_c", fcr * S, Kind.MOMENT, f"{PART9}, Eq. 9-12")


def _flexure_double(cb: CopedBeam, c: Calc, e: float) -> float:
    hc = c.step("h_c", "d - d_{ct} - d_{cb}", cb.d - cb.dc - cb.dc_bottom, Kind.LENGTH,
                f"{PART9}, Fig. 9-3")
    Cb = c.step("C_b", r"3 + \ln(L_b/d)(1 - d_{ct}/d) \ge 1.84",
                max(3 + math.log(cb.c / cb.d) * (1 - cb.dc / cb.d), 1.84),
                clause=f"{PART9}, Eq. 9-21")
    S, Z = cb.tw * hc**2 / 6, cb.tw * hc**2 / 4
    my = c.step("M_y", "F_y t_w h_c^2/6", cb.Fy * S, Kind.MOMENT, f"{SPEC} §F11")
    mp = c.step("M_p", "F_y t_w h_c^2/4", cb.Fy * Z, Kind.MOMENT, f"{SPEC} §F11")
    ratio = c.step(r"\frac{L_b d}{t^2}", "", cb.c * hc / cb.tw**2, clause=f"{SPEC} §F11.2")
    if ratio <= 0.08 * E_STEEL / cb.Fy:
        return c.step("M_n", "M_p", mp, Kind.MOMENT, f"{SPEC} Eq. F11-1")
    if ratio <= 1.9 * E_STEEL / cb.Fy:
        return c.step("M_n", r"C_b\left[1.52 - 0.274\frac{L_b d}{t^2}\frac{F_y}{E}\right]M_y"
                      r" \le M_p", min(Cb * (1.52 - 0.274 * ratio * cb.Fy / E_STEEL) * my, mp),
                      Kind.MOMENT, f"{SPEC} Eq. F11-3")
    fcr = c.step("F_{cr}", r"\frac{1.9 E C_b}{L_b d/t^2}", 1.9 * E_STEEL * Cb / ratio,
                 Kind.STRESS, f"{SPEC} Eq. F11-4")
    return c.step("M_n", r"F_{cr} S \le M_p", min(fcr * S, mp), Kind.MOMENT, f"{SPEC} Eq. F11-4")


def _rename(key: str, check: CheckResult) -> CheckResult:
    return check.model_copy(update={"id": f"coped_beam.{key}",
                                    "text_id": f"check.coped_beam.{key}"})


def check_coped_beam(cb: CopedBeam, R: float, method: Method,
                     combo: str = "") -> list[CheckResult]:
    """Limit states of the coped beam end for the end reaction ``R``."""
    c = Calc(method, combo)
    clause = f"{PART9}, Eq. 9-9"
    e = c.step("e", r"c + \mathrm{setback}", cb.c + cb.setback, Kind.LENGTH, clause)
    mn = (_flexure_double if cb.dc_bottom > 0 else _flexure_top)(cb, c, e)
    rn = c.step("R_n", "M_n/e", mn / e, Kind.FORCE, clause)
    flexure = c.result("coped_beam.flexure", clause, R,
                       c.available(rn, FLEXURE, Kind.FORCE, clause), Kind.FORCE)

    hc = cb.d - cb.dc - cb.dc_bottom
    holes = cb.rows * cb.hole
    out = [
        flexure,
        _rename("shear_yielding", elements.shear_yielding(hc * cb.tw, cb.Fy, R, method, combo)),
        _rename("shear_rupture", elements.shear_rupture((hc - holes) * cb.tw, cb.Fu, R, method,
                                                        combo)),
    ]
    if cb.rows and cb.leh > 0:
        length = cb.lev + (cb.rows - 1) * cb.spacing
        agv = length * cb.tw
        anv = agv - (cb.rows - 0.5) * cb.hole * cb.tw
        tension = cb.leh - cb.underrun + (cb.lines - 1) * cb.gage
        ant = (tension - (cb.lines - 0.5) * cb.hole) * cb.tw
        out.append(_rename("block_shear", elements.block_shear(
            agv, anv, ant, cb.Fy, cb.Fu, R, method, Ubs=1.0 if cb.lines == 1 else 0.5,
            combo=combo)))
    return out
