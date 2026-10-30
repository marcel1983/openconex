# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Cast-in anchors in concrete, ACI 318-19 Chapter 17.

ACI 318 is a strength design method: the checks accept LRFD (factored)
demands only. The empirical equations of ACI 318 are written in psi and inches; they are
evaluated in those units and converted back, so results do not depend on the
unit system of the user. Inputs and outputs are in internal units (N, mm, MPa).

Groups are rectangular: ``span_x`` and ``span_y`` are the distances between
the outermost anchors, and ``edges`` gives the distance from those anchors to
each concrete edge (left, right, bottom, top); ``None`` means no edge.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from openconex.core.checks import CheckResult
from openconex.kernel.design import Calc, Method, Resistance
from openconex.units import Kind, from_internal, to_internal

__all__ = [
    "SEISMIC_FACTOR",
    "Edges",
    "anchor_reinforcement",
    "breakout_shear",
    "breakout_tension",
    "futa",
    "heavy_hex_bearing_area",
    "projected_area_tension",
    "pryout",
    "pullout",
    "pullout_hook",
    "shear_lug_bearing",
    "shear_lug_breakout",
    "side_face_blowout",
    "steel_shear",
    "steel_tension",
    "tensile_stress_area",
    "tension_shear_interaction",
    "threads_per_inch",
]

ACI = "ACI 318-19"
SEISMIC_FACTOR = 0.75
"""Reduction of concrete-governed tension strength in SDC C-F (§17.10.5.4)."""

# φ factors, ACI 318-19 Table 17.5.3 (cast-in anchors, ductile steel).
STEEL_TENSION = Resistance(0.75, 2.0)
STEEL_SHEAR = Resistance(0.65, 2.0)
CONCRETE_B = Resistance(0.70, 2.0)  # Condition B: no supplementary reinforcement
CONCRETE_A = Resistance(0.75, 2.0)  # Condition A: supplementary reinforcement
PULLOUT = Resistance(0.70, 2.0)
SHEAR_LUG = Resistance(0.65, 2.0)
ANCHOR_REINFORCEMENT = Resistance(0.75, 2.0)

# UNC threads per inch by nominal diameter [in.].
_TPI = {0.5: 13, 0.625: 11, 0.75: 10, 0.875: 9, 1.0: 8, 1.125: 7, 1.25: 7, 1.375: 6, 1.5: 6,
        1.75: 5, 2.0: 4.5, 2.25: 4.5, 2.5: 4, 2.75: 4, 3.0: 4, 3.25: 4, 3.5: 4, 3.75: 4, 4.0: 4}


def _in(v: float) -> float:
    return from_internal(v, Kind.LENGTH, "in")


def _psi(v: float) -> float:
    return from_internal(v, Kind.STRESS, "psi")


def _lbf(v: float) -> float:
    return to_internal(v, "lbf", Kind.FORCE)


def _require_lrfd(method: Method) -> None:
    if method is not Method.LRFD:
        raise ValueError("ACI 318 Chapter 17 is a strength design method: use LRFD loads")


def threads_per_inch(d: float) -> float:
    d_in = round(_in(d), 4)
    if d_in not in _TPI:
        raise ValueError(f"no UNC thread data for a {d_in} in. rod")
    return _TPI[d_in]


def tensile_stress_area(d: float) -> float:
    """Ase = π/4 (d - 0.9743/nt)² [mm²] (ASME B1.1)."""
    d_in = _in(d)
    a = math.pi / 4 * (d_in - 0.9743 / threads_per_inch(d)) ** 2
    return to_internal(a, "in**2", Kind.AREA)


def heavy_hex_bearing_area(d: float) -> float:
    """Net bearing area of a heavy hex nut, hexagon (F = 1.5d + 1/8 in.) minus rod [mm²]."""
    d_in = _in(d)
    f = 1.5 * d_in + 0.125
    return to_internal(math.sqrt(3) / 2 * f * f - math.pi * d_in**2 / 4, "in**2", Kind.AREA)


def futa(Fu: float, Fy: float) -> float:
    """futa ≤ min(1.9 fya, 125 ksi) (§17.6.1.2)."""
    return min(Fu, 1.9 * Fy, to_internal(125, "ksi", Kind.STRESS))


@dataclass(frozen=True)
class Edges:
    """Distances from the outermost anchors to the concrete edges [mm]; None = far."""

    left: float | None = None
    right: float | None = None
    bottom: float | None = None
    top: float | None = None

    def values(self) -> list[float]:
        return [c for c in (self.left, self.right, self.bottom, self.top) if c is not None]


NO_EDGES = Edges()


def _effective_hef(hef: float, edges: Edges, span_x: float, span_y: float) -> float:
    """hef' when three or more edges are within 1.5 hef (§17.6.2.1.2)."""
    near = [c for c in edges.values() if c < 1.5 * hef]
    if len(near) >= 3:
        return min(hef, max(max(near) / 1.5, max(span_x, span_y) / 3))
    return hef


def projected_area_tension(hef: float, span_x: float, span_y: float,
                           edges: Edges = NO_EDGES) -> float:
    """A_Nc of a rectangular anchor group (§17.6.2.1.1)."""
    r = 1.5 * hef

    def side(c: float | None) -> float:
        return r if c is None else min(c, r)

    return ((span_x + side(edges.left) + side(edges.right))
            * (span_y + side(edges.bottom) + side(edges.top)))


def steel_tension(d: float, Fu: float, Fy: float, demand: float, method: Method,
                  combo: str = "") -> CheckResult:
    """Nsa = Ase,N futa of one anchor (§17.6.1, Eq. 17.6.1.2)."""
    clause = f"{ACI} §17.6.1.2"
    _require_lrfd(method)
    c = Calc(method, combo)
    ase = c.step("A_{se,N}", r"\frac{\pi}{4}\left(d_a - \frac{0.9743}{n_t}\right)^2",
                 tensile_stress_area(d), Kind.AREA, clause)
    fu = c.step("f_{uta}", r"\min(f_{uta}, 1.9 f_{ya}, 125\ ksi)", futa(Fu, Fy), Kind.STRESS,
                clause)
    rn = c.step("N_{sa}", "A_{se,N} f_{uta}", ase * fu, Kind.FORCE, clause)
    cap = c.available(rn, STEEL_TENSION, Kind.FORCE, clause, "N_{sa}")
    return c.result("anchor.steel_tension", clause, demand, cap, Kind.FORCE)


def breakout_tension(hef: float, fc: float, demand: float, method: Method, span_x: float = 0.0,
                     span_y: float = 0.0, edges: Edges = NO_EDGES, eccentricity: float = 0.0,
                     cracked: bool = True, lightweight: float = 1.0,
                     supplementary: bool = False, seismic: bool = False,
                     combo: str = "") -> CheckResult:
    """Concrete breakout of a cast-in anchor group in tension (§17.6.2)."""
    clause = f"{ACI} §17.6.2"
    _require_lrfd(method)
    c = Calc(method, combo)
    h = c.step("h_{ef}", "h_{ef}' (17.6.2.1.2)", _effective_hef(hef, edges, span_x, span_y),
               Kind.LENGTH, clause)
    anc = c.step("A_{Nc}", r"(s_x + 2c)(s_y + 2c),\ c \le 1.5h_{ef}",
                 projected_area_tension(h, span_x, span_y, edges), Kind.AREA,
                 f"{ACI} §17.6.2.1.1")
    anco = c.step("A_{Nco}", "9 h_{ef}^2", 9 * h * h, Kind.AREA, f"{ACI} Eq. 17.6.2.1.4")
    h_in, fc_psi = _in(h), _psi(fc)
    if 11 <= h_in <= 25:
        nb = 16 * lightweight * math.sqrt(fc_psi) * h_in ** (5 / 3)
        expr, eq = r"16 \lambda_a \sqrt{f'_c} h_{ef}^{5/3}", "17.6.2.2.3"
    else:
        nb = 24 * lightweight * math.sqrt(fc_psi) * h_in**1.5
        expr, eq = r"24 \lambda_a \sqrt{f'_c} h_{ef}^{1.5}", "17.6.2.2.1"
    nb = c.step("N_b", expr, _lbf(nb), Kind.FORCE, f"{ACI} Eq. {eq}")
    psi_ec = c.step(r"\psi_{ec,N}", r"\frac{1}{1 + e'_N/(1.5h_{ef})}",
                    1 / (1 + eccentricity / (1.5 * h)), clause=f"{ACI} §17.6.2.3")
    ca_min = min(edges.values(), default=math.inf)
    psi_ed = c.step(r"\psi_{ed,N}", r"0.7 + 0.3\frac{c_{a,min}}{1.5h_{ef}} \le 1",
                    1.0 if ca_min >= 1.5 * h else 0.7 + 0.3 * ca_min / (1.5 * h),
                    clause=f"{ACI} §17.6.2.4")
    psi_c = c.step(r"\psi_{c,N}", "1.0 cracked / 1.25 uncracked", 1.0 if cracked else 1.25,
                   clause=f"{ACI} §17.6.2.5")
    rn = c.step("N_{cbg}", r"\frac{A_{Nc}}{A_{Nco}}\psi_{ec,N}\psi_{ed,N}\psi_{c,N}\psi_{cp,N}N_b",
                anc / anco * psi_ec * psi_ed * psi_c * nb, Kind.FORCE, f"{ACI} Eq. 17.6.2.1b")
    if seismic:
        rn = c.step("N_{cbg}", "0.75 N_{cbg}", SEISMIC_FACTOR * rn, Kind.FORCE,
                    f"{ACI} §17.10.5.4")
    cap = c.available(rn, CONCRETE_A if supplementary else CONCRETE_B, Kind.FORCE, clause,
                      "N_{cbg}")
    return c.result("anchor.concrete_breakout_tension", clause, demand, cap, Kind.FORCE)


def pullout(bearing_area: float, fc: float, demand: float, method: Method,
            cracked: bool = True, seismic: bool = False, combo: str = "") -> CheckResult:
    """Pullout of a headed anchor or nut, Np = 8 Abrg f'c (§17.6.3.2.2a), one anchor."""
    clause = f"{ACI} §17.6.3"
    _require_lrfd(method)
    c = Calc(method, combo)
    np_ = c.step("N_p", "8 A_{brg} f'_c", 8 * bearing_area * fc, Kind.FORCE,
                 f"{ACI} Eq. 17.6.3.2.2a", A_brg=(bearing_area, Kind.AREA))
    psi = 1.0 if cracked else 1.4
    rn = c.step("N_{pn}", r"\psi_{c,P} N_p", psi * np_, Kind.FORCE, f"{ACI} Eq. 17.6.3.1")
    if seismic:
        rn = c.step("N_{pn}", "0.75 N_{pn}", SEISMIC_FACTOR * rn, Kind.FORCE, f"{ACI} §17.10.5.4")
    cap = c.available(rn, PULLOUT, Kind.FORCE, clause, "N_{pn}")
    return c.result("anchor.pullout", clause, demand, cap, Kind.FORCE)


def pullout_hook(d: float, eh: float, fc: float, demand: float, method: Method,
                 cracked: bool = True, combo: str = "") -> CheckResult:
    """Pullout of a hooked anchor, Np = 0.9 f'c eh da with 3da ≤ eh ≤ 4.5da (§17.6.3.2.2b)."""
    clause = f"{ACI} §17.6.3"
    _require_lrfd(method)
    c = Calc(method, combo)
    eh_eff = c.step("e_h", r"3d_a \le e_h \le 4.5d_a", min(max(eh, 3 * d), 4.5 * d), Kind.LENGTH)
    if eh < 3 * d:
        eh_eff = 0.0  # hook too short: no pullout strength
    np_ = c.step("N_p", "0.9 f'_c e_h d_a", 0.9 * fc * eh_eff * d, Kind.FORCE,
                 f"{ACI} Eq. 17.6.3.2.2b")
    rn = c.step("N_{pn}", r"\psi_{c,P} N_p", (1.0 if cracked else 1.4) * np_, Kind.FORCE)
    cap = c.available(rn, PULLOUT, Kind.FORCE, clause, "N_{pn}")
    return c.result("anchor.pullout", clause, demand, cap, Kind.FORCE)


def side_face_blowout(ca1: float, bearing_area: float, fc: float, demand: float,
                      method: Method, hef: float, ca2: float | None = None,
                      spacing: float = 0.0, lightweight: float = 1.0,
                      combo: str = "") -> CheckResult:
    """Side-face blowout of a headed anchor near an edge (§17.6.4); applies if hef > 2.5 ca1."""
    clause = f"{ACI} §17.6.4"
    _require_lrfd(method)
    c = Calc(method, combo)
    applicable = hef > 2.5 * ca1
    abrg_in2 = from_internal(bearing_area, Kind.AREA, "in**2")
    nsb = 160 * _in(ca1) * math.sqrt(abrg_in2) * lightweight * math.sqrt(_psi(fc))
    nsb = c.step("N_{sb}", r"160 c_{a1} \sqrt{A_{brg}} \lambda_a \sqrt{f'_c}", _lbf(nsb),
                 Kind.FORCE, f"{ACI} Eq. 17.6.4.1")
    if ca2 is not None and ca2 < 3 * ca1:
        nsb = c.step("N_{sb}", r"\frac{1 + c_{a2}/c_{a1}}{4} N_{sb}",
                     (1 + ca2 / ca1) / 4 * nsb, Kind.FORCE, f"{ACI} §17.6.4.1.1")
    if spacing:
        nsb = c.step("N_{sbg}", r"\left(1 + \frac{s}{6c_{a1}}\right) N_{sb}",
                     (1 + spacing / (6 * ca1)) * nsb, Kind.FORCE, f"{ACI} Eq. 17.6.4.2")
    cap = c.available(nsb, CONCRETE_B, Kind.FORCE, clause, "N_{sb}")
    return c.result("anchor.side_face_blowout", clause, demand, cap, Kind.FORCE,
                    applicable=applicable)


def steel_shear(d: float, Fu: float, Fy: float, demand: float, method: Method,
                grout_pad: bool = False, combo: str = "") -> CheckResult:
    """Vsa = 0.6 Ase,V futa of one cast-in anchor (§17.7.1.2b); 0.80 with a grout pad."""
    clause = f"{ACI} §17.7.1"
    _require_lrfd(method)
    c = Calc(method, combo)
    ase = tensile_stress_area(d)
    rn = c.step("V_{sa}", "0.6 A_{se,V} f_{uta}", 0.6 * ase * futa(Fu, Fy), Kind.FORCE,
                f"{ACI} Eq. 17.7.1.2b")
    if grout_pad:
        rn = c.step("V_{sa}", "0.80 V_{sa}", 0.80 * rn, Kind.FORCE, f"{ACI} §17.7.1.2.1")
    cap = c.available(rn, STEEL_SHEAR, Kind.FORCE, clause, "V_{sa}")
    return c.result("anchor.steel_shear", clause, demand, cap, Kind.FORCE)


def _vb(c: Calc, d: float, le: float, ca1: float, fc: float, lightweight: float) -> float:
    root = lightweight * math.sqrt(_psi(fc)) * _in(ca1) ** 1.5
    v1 = 7 * (_in(le) / _in(d)) ** 0.2 * math.sqrt(_in(d)) * root
    v2 = 9 * root
    return c.step("V_b", r"\min\left[7\left(\frac{l_e}{d_a}\right)^{0.2}\sqrt{d_a},\ 9\right]"
                  r"\lambda_a\sqrt{f'_c}c_{a1}^{1.5}", _lbf(min(v1, v2)), Kind.FORCE,
                  f"{ACI} Eq. 17.7.2.2.1")


def breakout_shear(d: float, hef: float, ca1: float, fc: float, demand: float, method: Method,
                   spacing: float = 0.0, ca2: tuple[float | None, float | None] = (None, None),
                   ha: float | None = None, eccentricity: float = 0.0, cracked: bool = True,
                   supplementary: bool = False, lightweight: float = 1.0,
                   combo: str = "") -> CheckResult:
    """Concrete breakout in shear toward an edge at ca1 (§17.7.2).

    ``spacing`` is the extent of the anchors parallel to the edge, ``ca2`` the
    side distances (None = far), ``ha`` the member thickness (None = deep).
    """
    clause = f"{ACI} §17.7.2"
    _require_lrfd(method)
    c = Calc(method, combo)
    r = 1.5 * ca1
    width = spacing + sum(r if s is None else min(s, r) for s in ca2)
    height = r if ha is None else min(ha, r)
    avc = c.step("A_{Vc}", "", width * height, Kind.AREA, f"{ACI} §17.7.2.1.1")
    avco = c.step("A_{Vco}", "4.5 c_{a1}^2", 4.5 * ca1 * ca1, Kind.AREA, f"{ACI} Eq. 17.7.2.1.3")
    vb = _vb(c, d, min(hef, 8 * d), ca1, fc, lightweight)
    psi_ec = 1 / (1 + eccentricity / (1.5 * ca1))
    ca2_min = min((s for s in ca2 if s is not None), default=math.inf)
    psi_ed = c.step(r"\psi_{ed,V}", r"0.7 + 0.3\frac{c_{a2}}{1.5c_{a1}} \le 1",
                    1.0 if ca2_min >= r else 0.7 + 0.3 * ca2_min / r, clause=f"{ACI} §17.7.2.4")
    psi_c = 1.0 if cracked else 1.4
    psi_h = c.step(r"\psi_{h,V}", r"\sqrt{1.5c_{a1}/h_a} \ge 1",
                   1.0 if ha is None else max(1.0, math.sqrt(r / ha)), clause=f"{ACI} §17.7.2.6")
    rn = c.step("V_{cbg}", r"\frac{A_{Vc}}{A_{Vco}}\psi_{ec,V}\psi_{ed,V}\psi_{c,V}\psi_{h,V}V_b",
                avc / avco * psi_ec * psi_ed * psi_c * psi_h * vb, Kind.FORCE,
                f"{ACI} Eq. 17.7.2.1b")
    cap = c.available(rn, CONCRETE_A if supplementary else CONCRETE_B, Kind.FORCE, clause,
                      "V_{cbg}")
    return c.result("anchor.concrete_breakout_shear", clause, demand, cap, Kind.FORCE)


def pryout(Ncbg: float, hef: float, demand: float, method: Method,
           combo: str = "") -> CheckResult:
    """Vcpg = kcp Ncpg with Ncpg = Ncbg for cast-in anchors (§17.7.3)."""
    clause = f"{ACI} §17.7.3"
    _require_lrfd(method)
    c = Calc(method, combo)
    kcp = c.step("k_{cp}", "1.0 (h_{ef} < 2.5 in.) / 2.0",
                 1.0 if _in(hef) < 2.5 else 2.0, clause=clause)
    rn = c.step("V_{cpg}", "k_{cp} N_{cpg}", kcp * Ncbg, Kind.FORCE, f"{ACI} Eq. 17.7.3.1b")
    cap = c.available(rn, PULLOUT, Kind.FORCE, clause, "V_{cpg}")
    return c.result("anchor.pryout", clause, demand, cap, Kind.FORCE)


def tension_shear_interaction(Nua: float, phiNn: float, Vua: float, phiVn: float,
                              method: Method = Method.LRFD, combo: str = "") -> CheckResult:
    """N/φNn + V/φVn ≤ 1.2, unless either ratio ≤ 0.2 (§17.8)."""
    clause = f"{ACI} §17.8"
    _require_lrfd(method)
    c = Calc(method, combo)
    rn_ = c.step(r"N_{ua}/\phi N_n", "", Nua / phiNn if phiNn else math.inf, clause=clause)
    rv = c.step(r"V_{ua}/\phi V_n", "", Vua / phiVn if phiVn else math.inf, clause=clause)
    if rn_ <= 0.2 or rv <= 0.2:
        value = c.step("", r"\max(N/\phi N_n, V/\phi V_n)", max(rn_, rv), clause=clause)
        return c.result("anchor.interaction", clause, value, 1.0, Kind.DIMENSIONLESS)
    value = c.step("", r"\frac{N_{ua}}{\phi N_n} + \frac{V_{ua}}{\phi V_n}", rn_ + rv,
                   clause=f"{ACI} Eq. 17.8.3")
    return c.result("anchor.interaction", clause, value, 1.2, Kind.DIMENSIONLESS)


def shear_lug_bearing(width: float, embedment: float, fc: float, demand: float, method: Method,
                      psi_brg: float = 1.0, combo: str = "") -> CheckResult:
    """Vbrg,sl = 1.7 f'c Aef,sl ψbrg,sl (§17.11.2), φ = 0.65.

    Only the embedded depth (up to 2 × lug thickness below the grout is ignored
    by the caller when it applies) bears.
    """
    clause = f"{ACI} §17.11.2"
    _require_lrfd(method)
    c = Calc(method, combo)
    aef = c.step("A_{ef,sl}", "b_{sl} h_{ef,sl}", width * embedment, Kind.AREA, clause)
    rn = c.step("V_{brg,sl}", r"1.7 f'_c A_{ef,sl} \psi_{brg,sl}", 1.7 * fc * aef * psi_brg,
                Kind.FORCE, f"{ACI} Eq. 17.11.2.1")
    cap = c.available(rn, SHEAR_LUG, Kind.FORCE, clause, "V_{brg,sl}")
    return c.result("anchor.shear_lug_bearing", clause, demand, cap, Kind.FORCE)


def shear_lug_breakout(width: float, embedment: float, ca1: float, fc: float, demand: float,
                       method: Method, ca2: tuple[float | None, float | None] = (None, None),
                       lightweight: float = 1.0, combo: str = "") -> CheckResult:
    """Concrete breakout of a shear lug toward an edge (§17.11.3), φ = 0.65.

    A_Vc = (h_sl + 1.5ca1)(b_sl + 2·1.5ca1) - h_sl b_sl; Vb with the 9λ√f'c ca1^1.5 form.
    """
    clause = f"{ACI} §17.11.3"
    _require_lrfd(method)
    c = Calc(method, combo)
    r = 1.5 * ca1
    side = sum(r if s is None else min(s, r) for s in ca2)
    avc = c.step("A_{Vc}", r"(h_{sl} + 1.5c_{a1})(b_{sl} + 3c_{a1}) - h_{sl} b_{sl}",
                 (embedment + r) * (width + side) - embedment * width, Kind.AREA, clause)
    avco = c.step("A_{Vco}", "4.5 c_{a1}^2", 4.5 * ca1 * ca1, Kind.AREA, f"{ACI} Eq. 17.7.2.1.3")
    vb = c.step("V_b", r"9\lambda_a\sqrt{f'_c}c_{a1}^{1.5}",
                _lbf(9 * lightweight * math.sqrt(_psi(fc)) * _in(ca1) ** 1.5), Kind.FORCE,
                f"{ACI} Eq. 17.7.2.2.1b")
    ca2_min = min((s for s in ca2 if s is not None), default=math.inf)
    psi_ed = 1.0 if ca2_min >= r else 0.7 + 0.3 * ca2_min / r
    rn = c.step("V_{cb}", r"\frac{A_{Vc}}{A_{Vco}}\psi_{ed,V}V_b", avc / avco * psi_ed * vb,
                Kind.FORCE, f"{ACI} Eq. 17.7.2.1a")
    cap = c.available(rn, SHEAR_LUG, Kind.FORCE, clause, "V_{cb}")
    return c.result("anchor.shear_lug_breakout", clause, demand, cap, Kind.FORCE)


def anchor_reinforcement(demand: float, fy: float, area: float, method: Method,
                         combo: str = "") -> CheckResult:
    """Anchor reinforcement developed on both sides of the breakout: φ As fy (§17.5.2.1), φ=0.75."""
    clause = f"{ACI} §17.5.2.1"
    _require_lrfd(method)
    c = Calc(method, combo)
    rn = c.step("N_n", "A_s f_y", area * fy, Kind.FORCE, clause, A_s=(area, Kind.AREA))
    cap = c.available(rn, ANCHOR_REINFORCEMENT, Kind.FORCE, clause, "N_n")
    return c.result("anchor.reinforcement", clause, demand, cap, Kind.FORCE)
