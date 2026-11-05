# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Reinforcement of a top-coped beam end (AISC Manual Part 9; II.A-6 C and D).

* Doubler plate welded to the coped web (II.A-6 C): reinforced elastic and
  plastic section moduli, flexural strength with Manual Eq. 9-7, shear yielding
  and rupture of web plus plate, plate compactness and weld shear flow.
* Longitudinal stiffener welded along the cope line (II.A-6 D): reinforced
  section properties, flexural strength from AISC 360-22 §F4 with R_pc = 1.0,
  compactness of the stiffener and web, weld shear flow and web shear rupture.

The section is modelled as the tee left by the cope (flange at the top of the
model) plus rectangles for the reinforcement. The real top cope leaves the
bottom flange, so the cope line is the opposite fibre; the model is inverted,
which does not change S or Z. Reinforcement dimensions are in internal units.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import pairwise

from openconex.core.checks import CheckResult
from openconex.core.loads import Method
from openconex.core.materials import E_STEEL
from openconex.kernel import elements
from openconex.kernel.design import FLEXURE, Calc
from openconex.units import Kind

__all__ = ["DoublerPlate", "LongitudinalStiffener", "ReinforcedSection",
           "check_doubler_plate", "check_longitudinal_stiffener", "reinforced_section"]

PART9 = "AISC Manual 16th ed., Part 9"
SPEC = "AISC 360-22"


@dataclass(frozen=True)
class DoublerPlate:
    thickness: float
    depth: float
    gap: float
    """Distance from the cope line to the near face of the plate."""
    weld: float = 0.0
    """Fillet weld size on each side of the plate."""


@dataclass(frozen=True)
class LongitudinalStiffener:
    width: float
    thickness: float
    weld: float = 0.0
    length: float | None = None
    """Length along the beam; defaults to ``c + d_c``."""


@dataclass(frozen=True)
class ReinforcedSection:
    A: float
    ybar: float
    inertia: float
    S_top: float
    S_bottom: float
    S_min: float
    Z: float
    Iy: float
    Iyc: float


def _rectangles(cb, doubler: DoublerPlate | None,
                stiffener: LongitudinalStiffener | None) -> list[tuple[float, float, float]]:
    h = cb.d - cb.dc
    rects = [(0.0, cb.tf, cb.bf), (cb.tf, h, cb.tw)]
    if doubler is not None:
        y1 = h - doubler.gap
        rects.append((y1 - doubler.depth, y1, doubler.thickness))
    if stiffener is not None:
        rects.append((h - stiffener.thickness, h, stiffener.width))
    return rects


def _section(rects: list[tuple[float, float, float]], tw: float) -> ReinforcedSection:
    points = sorted({p for rect in rects for p in rect[:2]})
    intervals = []
    for a, b in pairwise(points):
        if b <= a:
            continue
        mid = (a + b) / 2
        width = sum(w for y0, y1, w in rects if y0 <= mid <= y1)
        if width > 0:
            intervals.append((a, b, width))
    A = sum((b - a) * w for a, b, w in intervals)
    ybar = sum(w * (b * b - a * a) / 2 for a, b, w in intervals) / A
    inertia = sum(w * ((b - ybar) ** 3 - (a - ybar) ** 3) / 3
                  for a, b, w in intervals)
    cum = 0.0
    yp = 0.0
    for a, b, w in intervals:
        da = (b - a) * w
        if cum + da >= A / 2:
            yp = a + (A / 2 - cum) / w
            break
        cum += da
    Z = 0.0
    for a, b, w in intervals:
        if b <= yp:
            Z += w * ((yp - a) ** 2 - (yp - b) ** 2) / 2
        elif a >= yp:
            Z += w * ((b - yp) ** 2 - (a - yp) ** 2) / 2
        else:
            Z += w * ((yp - a) ** 2 + (b - yp) ** 2) / 2
    S_top, S_bottom = inertia / ybar, inertia / (points[-1] - ybar)
    # About the vertical axis: the web is thin and centred, so its contribution
    # is included explicitly but is negligible.
    Iy = 0.0
    Iyc = 0.0
    for y0, y1, w in rects:
        depth = y1 - y0
        if depth <= 0:
            continue
        Iy += depth * w**3 / 12
    # Compression flange at the cope line: the stiffener when present, else the
    # beam flange (the only flange left by the cope).
    if len(rects) > 2:
        y0, y1, w = rects[-1]
        Iyc = (y1 - y0) * w**3 / 12
    else:
        Iyc = rects[0][1] * rects[0][2] ** 3 / 12
    return ReinforcedSection(A, ybar, inertia, S_top, S_bottom,
                             min(S_top, S_bottom), Z, Iy, Iyc)


def reinforced_section(cb, doubler: DoublerPlate | None = None,
                       stiffener: LongitudinalStiffener | None = None) -> ReinforcedSection:
    return _section(_rectangles(cb, doubler, stiffener), cb.tw)


def _buckling_parameters(cb, c: Calc) -> tuple[float, float]:
    hc = cb.d - cb.dc
    cd, ch = cb.c / cb.d, cb.c / hc
    f = c.step("f", r"2c/d" if cd <= 1 else r"1 + c/d", 2 * cd if cd <= 1 else 1 + cd,
               clause=f"{PART9}, Eq. 9-20")
    k = c.step("k", r"2.2(h_c/c)^{1.65}" if ch <= 1 else r"2.2 h_c/c",
               2.2 * (hc / cb.c) ** 1.65 if ch <= 1 else 2.2 * hc / cb.c,
               clause=f"{PART9}, Eq. 9-19")
    k1 = c.step("k_1", r"f k \ge 1.61", max(f * k, 1.61), clause=f"{PART9}, Eq. 9-14")
    return k1, hc


def _rename(key: str, check: CheckResult) -> CheckResult:
    return check.model_copy(update={"id": f"coped_beam.{key}",
                                    "text_id": f"check.coped_beam.{key}"})


def _weld_capacity(weld: float, method: Method) -> float:
    """Available fillet-weld strength per unit length for one weld [N/mm]."""
    D = weld / 25.4 * 16  # sixteenths of an inch
    return (1.392 if method is Method.LRFD else 0.928) * D * 175.1268  # kip/in -> N/mm


def check_doubler_plate(cb, R: float, method: Method, combo: str = "") -> list[CheckResult]:
    """Checks of a doubler plate on a top-coped web (II.A-6 C)."""
    dp = cb.doubler
    if dp is None:
        return []
    c = Calc(method, combo)
    h = cb.d - cb.dc
    e = cb.c + cb.setback
    sec = reinforced_section(cb, doubler=dp)
    mp = c.step("M_p", "F_y Z_{net}", cb.Fy * sec.Z, Kind.MOMENT, f"{PART9}, Eq. 9-15")
    my = c.step("M_y", "F_y S_{net}", cb.Fy * sec.S_min, Kind.MOMENT, f"{PART9}, Eq. 9-16")
    k1, hc = _buckling_parameters(cb, c)
    lam = c.step(r"\lambda", "h_c/t_w", hc / cb.tw, clause=f"{PART9}, Eq. 9-17")
    lp = c.step(r"\lambda_p", r"0.475\sqrt{k_1 E/F_y}",
                0.475 * math.sqrt(k1 * E_STEEL / cb.Fy), clause=f"{PART9}, Eq. 9-18")
    if lam <= lp:
        mn = c.step("M_n", "M_p", mp, Kind.MOMENT, f"{PART9}, Eq. 9-10")
    elif lam <= 2 * lp:
        mn = c.step("M_n", r"M_p - (M_p - M_y)(\lambda/\lambda_p - 1)",
                    mp - (mp - my) * (lam / lp - 1), Kind.MOMENT, f"{PART9}, Eq. 9-7")
    else:
        fcr = c.step("F_{cr}", r"0.903 E k_1 (t_w/h_c)^2",
                     0.903 * E_STEEL * k1 * (cb.tw / hc) ** 2, Kind.STRESS,
                     f"{PART9}, Eq. 9-13")
        mn = c.step("M_n", "F_{cr} S_{net}", fcr * sec.S_min, Kind.MOMENT,
                    f"{PART9}, Eq. 9-12")
    rn = c.step("R_n", "M_n/e", mn / e, Kind.FORCE, f"{PART9}, Eq. 9-9")
    flexure = c.result("coped_beam.doubler_flexure", f"{PART9}, Eq. 9-7", R,
                       c.available(rn, FLEXURE, Kind.FORCE, f"{PART9}, Eq. 9-7"), Kind.FORCE)

    web = (h - cb.rows * cb.hole) * cb.tw
    plate = dp.depth * dp.thickness
    shear_y = _rename("doubler_shear_yielding", elements.shear_yielding(
        h * cb.tw + plate, cb.Fy, R, method, combo))
    shear_r = _rename("doubler_shear_rupture", elements.shear_rupture(
        web + plate, cb.Fu, R, method, combo))

    compact = Calc(method, combo)
    b_t = compact.step("d_p/t_p", "", dp.depth / dp.thickness, clause=f"{SPEC} Table B4.1b")
    limit = compact.step("1.12\\sqrt{E/F_y}", "", 1.12 * math.sqrt(E_STEEL / cb.Fy),
                         clause=f"{SPEC} Table B4.1b")
    compact_check = compact.result("coped_beam.doubler_compact",
                                   f"{SPEC} Table B4.1b", b_t, limit,
                                   Kind.DIMENSIONLESS)

    weld = Calc(method, combo)
    q = dp.depth * dp.thickness * abs(sec.ybar - (h - dp.gap - dp.depth / 2))
    flow = weld.step("r", r"\frac{R Q}{I}", R * q / sec.inertia, Kind.FORCE_PER_LENGTH,
                     f"{PART9}, Eq. 9-6")
    capacity = _weld_capacity(dp.weld, method)
    weld_check = weld.result("coped_beam.doubler_weld", f"{SPEC} §J2.4", flow,
                             2 * capacity, Kind.FORCE_PER_LENGTH)
    return [flexure, shear_y, shear_r, compact_check, weld_check]


def check_longitudinal_stiffener(cb, R: float, method: Method,
                                 combo: str = "") -> list[CheckResult]:
    """Checks of a longitudinal stiffener on a top-coped web (II.A-6 D)."""
    st = cb.stiffener
    if st is None:
        return []
    c = Calc(method, combo)
    h = cb.d - cb.dc
    e = cb.c + cb.setback
    sec = reinforced_section(cb, stiffener=st)
    sxc, sxt = sec.S_bottom, sec.S_top
    my_c = c.step("M_{y,c}", "F_y S_{xc}", cb.Fy * sxc, Kind.MOMENT, f"{SPEC} §F4")
    my_t = c.step("M_{y,t}", "F_y S_{xt}", cb.Fy * sxt, Kind.MOMENT, f"{SPEC} §F4")
    rpc = 1.0
    mn = c.step("M_n", r"R_{pc} M_{y,c} \le M_{y,t}", min(rpc * my_c, my_t),
                Kind.MOMENT, f"{SPEC} §F4")
    rn = c.step("R_n", "M_n/e", mn / e, Kind.FORCE, f"{PART9}, Eq. 9-9")
    flexure = c.result("coped_beam.stiffener_flexure", f"{SPEC} §F4", R,
                       c.available(rn, FLEXURE, Kind.FORCE, f"{SPEC} §F4"), Kind.FORCE)

    compact = Calc(method, combo)
    b = (st.width - cb.tw) / 2
    lam_st = compact.step("b/t", "", b / st.thickness, clause=f"{SPEC} Table B4.1b")
    lp_st = compact.step(r"0.38\sqrt{E/F_y}", "", 0.38 * math.sqrt(E_STEEL / cb.Fy),
                         clause=f"{SPEC} Table B4.1b, Case 11")
    stiffener_compact = compact.result("coped_beam.stiffener_compact",
                                       f"{SPEC} Table B4.1b, Case 11", lam_st, lp_st,
                                       Kind.DIMENSIONLESS)
    web_compact = Calc(method, combo)
    lam_w = web_compact.step("h_c/t_w", "", h / cb.tw, clause=f"{SPEC} Table B4.1b")
    lp_w = web_compact.step(r"5.70\sqrt{E/F_y}", "", 5.70 * math.sqrt(E_STEEL / cb.Fy),
                            clause=f"{SPEC} Table B4.1b, Case 16")
    web_check = web_compact.result("coped_beam.stiffener_web_compact",
                                   f"{SPEC} Table B4.1b, Case 16", lam_w, lp_w,
                                   Kind.DIMENSIONLESS)

    length = st.length if st.length is not None else cb.c + cb.dc
    weld = Calc(method, combo)
    q = st.width * st.thickness * abs(sec.ybar - (h - st.thickness / 2))
    r1 = R * q / sec.inertia
    r2 = R * e * q / (sec.inertia * max(length - cb.c, 1e-9))
    flow = weld.step("r", r"\frac{V Q}{I} \le 2.77", max(r1, r2),
                     Kind.FORCE_PER_LENGTH, f"{PART9} (shear flow)")
    capacity = _weld_capacity(st.weld, method)
    weld_check = weld.result("coped_beam.stiffener_weld", f"{SPEC} §J2.4", flow,
                             2 * capacity, Kind.FORCE_PER_LENGTH)
    web_shear = _rename("stiffener_web_shear", elements.shear_rupture(
        2 * length * cb.tw, cb.Fu, R, method, combo))
    return [flexure, stiffener_compact, web_check, weld_check, web_shear]
