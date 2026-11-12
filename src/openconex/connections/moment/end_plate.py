# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Flush and extended moment end-plate connections (AISC Design Guide 16).

Yield-line analysis of the end plate and bolt forces with prying action after
Murray and Shoemaker, *Flush and Extended Multiple-Row Moment End-Plate
Connections*, AISC Design Guide 16 (2002, revised 2016), following the
analysis flow chart of its Appendix B:

* end-plate yielding: M_pl = F_py t_p² Y (Tables 3-2 to 3-5 and 4-2 to 4-6),
  with γ_r = 1.25 for flush and 1.0 for extended plates (§2.5.3, item 2);
* bolt rupture without prying (thick plate, φM_np ≤ φ_b M_pl / 1.11):
  M_np = 2 P_t Σd_n (Eq. 2-5);
* bolt rupture with prying (thin plate): M_q from the maximum prying forces
  Q_max,i and Q_max,o (Eqs. 2-11 to 2-19).

The connection strength is the smaller of the end-plate yielding and the bolt
rupture strength. An axial force is turned into an equivalent moment
M ± P (h − t_f)/2 (§2.5.3, item 11; Example 4.2.3). The remaining limit states
of §2.6 use AISC 360-22: shear yielding and rupture of the extended part of
the plate (§J4.2) under half the flange force, shear in the bolts at the
compression flange with bearing on the plate and the column flange (§J3.7,
§J3.11), the beam web welds (§2.5.3, items 9 and 10) and an optional fillet
weld at the beam flanges (item 8), and the column web under the flange force
(§J10.2, §J10.3, §J10.5 and §J10.6). Column flange bending at the bolts
(Design Guide 4) is not checked.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from openconex.core.bolting import min_pretension
from openconex.core.checks import CheckResult
from openconex.core.loads import Method
from openconex.core.model import BoltSpec
from openconex.kernel import bolts, elements, local
from openconex.kernel.design import BOLT, FLEXURE, TENSION_YIELD, Calc, Resistance, available
from openconex.kernel.welds import fillet_weld_per_length
from openconex.units import Kind, from_internal, to_internal

if TYPE_CHECKING:
    from .fr_moment import MomentConnection

__all__ = ["EXTENDED", "FLUSH", "EndPlate", "EndPlateLayout", "end_plate_checks",
           "end_plate_strength"]

DG16 = "AISC Design Guide 16"
DG4 = "AISC Design Guide 4, 2nd ed."
SPEC = "AISC 360-22"
INCH = to_internal(1.0, "in", Kind.LENGTH)
PHI_B = 0.90
J10_YIELD = Resistance(1.00, 1.50)
PHI = 0.75


class EndPlateLayout(StrEnum):
    FLUSH_2 = "flush_2"
    """Two-bolt flush unstiffened (Table 3-2)."""
    FLUSH_4 = "flush_4"
    """Four-bolt flush unstiffened (Table 3-3)."""
    FLUSH_4_STIFFENED_BETWEEN = "flush_4_stiffened_between"
    """Four-bolt flush, stiffener between the tension bolt rows (Table 3-4)."""
    FLUSH_4_STIFFENED_INSIDE = "flush_4_stiffened_inside"
    """Four-bolt flush, stiffener inside the tension bolt rows (Table 3-5)."""
    EXTENDED_4 = "extended_4"
    """Four-bolt extended unstiffened, 4E (Table 4-2)."""
    EXTENDED_4_STIFFENED = "extended_4_stiffened"
    """Four-bolt extended stiffened, 4ES (Table 4-3)."""
    EXTENDED_1_2 = "extended_1_2"
    """Multiple row 1/2 extended unstiffened (Table 4-4)."""
    EXTENDED_1_3 = "extended_1_3"
    """Multiple row 1/3 extended unstiffened (Table 4-5)."""
    EXTENDED_1_3_STIFFENED = "extended_1_3_stiffened"
    """Multiple row 1/3 extended stiffened (Table 4-6)."""
    EXTENDED_8_STIFFENED = "extended_8_stiffened"
    """Eight-bolt extended stiffened, 8ES (Design Guide 4, Table 3.3)."""


FLUSH = frozenset({EndPlateLayout.FLUSH_2, EndPlateLayout.FLUSH_4,
                   EndPlateLayout.FLUSH_4_STIFFENED_BETWEEN,
                   EndPlateLayout.FLUSH_4_STIFFENED_INSIDE})
EXTENDED = frozenset(set(EndPlateLayout) - FLUSH)
STIFFENED_EXTENSION = frozenset({EndPlateLayout.EXTENDED_4_STIFFENED,
                                 EndPlateLayout.EXTENDED_1_3_STIFFENED,
                                 EndPlateLayout.EXTENDED_8_STIFFENED})
COLUMN_TABLE = {
    EndPlateLayout.EXTENDED_4: "Table 3.4", EndPlateLayout.EXTENDED_4_STIFFENED: "Table 3.4",
    EndPlateLayout.EXTENDED_8_STIFFENED: "Table 3.5",
}
"""Layouts with a column flange yield-line mechanism in Design Guide 4."""
TABLE = {
    EndPlateLayout.FLUSH_2: f"{DG16}, Table 3-2", EndPlateLayout.FLUSH_4: f"{DG16}, Table 3-3",
    EndPlateLayout.FLUSH_4_STIFFENED_BETWEEN: f"{DG16}, Table 3-4",
    EndPlateLayout.FLUSH_4_STIFFENED_INSIDE: f"{DG16}, Table 3-5",
    EndPlateLayout.EXTENDED_4: f"{DG16}, Table 4-2",
    EndPlateLayout.EXTENDED_4_STIFFENED: f"{DG16}, Table 4-3",
    EndPlateLayout.EXTENDED_1_2: f"{DG16}, Table 4-4",
    EndPlateLayout.EXTENDED_1_3: f"{DG16}, Table 4-5",
    EndPlateLayout.EXTENDED_1_3_STIFFENED: f"{DG16}, Table 4-6",
    EndPlateLayout.EXTENDED_8_STIFFENED: f"{DG4}, Table 3.3",
}
INSIDE_ROWS = {
    EndPlateLayout.FLUSH_2: 1, EndPlateLayout.FLUSH_4: 2,
    EndPlateLayout.FLUSH_4_STIFFENED_BETWEEN: 2, EndPlateLayout.FLUSH_4_STIFFENED_INSIDE: 2,
    EndPlateLayout.EXTENDED_4: 1, EndPlateLayout.EXTENDED_4_STIFFENED: 1,
    EndPlateLayout.EXTENDED_1_2: 2, EndPlateLayout.EXTENDED_1_3: 3,
    EndPlateLayout.EXTENDED_1_3_STIFFENED: 3, EndPlateLayout.EXTENDED_8_STIFFENED: 2,
}
"""Tension bolt rows between the beam flanges."""


@dataclass(frozen=True)
class EndPlate:
    """End plate welded to the beam end and bolted to the column flange.

    Two bolts per row, at gage ``gage``. ``pf`` is the distance from the
    first bolt row inside the flanges to the inner face of the tension flange
    (p_f for flush plates, p_f,i for extended plates).
    """

    layout: EndPlateLayout
    bolt: BoltSpec
    width: float
    thickness: float
    gage: float
    pf: float
    Fy: float
    Fu: float
    pb: float = 0.0
    """Pitch between the bolt rows inside the flanges."""
    pf_o: float = 0.0
    """Extended plates: outer bolt row to the outer face of the tension flange."""
    pext: float = 0.0
    """Extended plates: extension beyond the outer face of the tension flange."""
    ps_o: float = 0.0
    """Table 3-4: outer bolt row to the outer face of the stiffener."""
    stiffener_thickness: float = 0.0
    """Table 3-4: stiffener thickness t_s (p_s,i = p_b − p_s,o − t_s)."""
    ps: float = 0.0
    """Table 3-5: bolt row to the near face of the stiffener."""
    snug_tight: bool = False
    """Snug-tightened bolts: T_b is a fraction of the Table J3.1 pretension."""
    pretension: float | None = None
    """T_b given by the user instead of Table J3.1."""
    web_weld: float = 0.0
    """Fillet weld on each side of the beam web; 0 for a CJP groove weld."""
    flange_weld: float = 0.0
    """Fillet weld at the beam flanges; 0 for a CJP groove weld."""
    weld_reinforcement: float = 0.0
    """CJP flange welds: reinforcing fillet leg, N = t_f + 2w (Design Guide 4, Step 16)."""
    symmetric: bool = True
    """Same bolt pattern at both flanges (moment reversal); otherwise two bolts at
    the compression flange, as in the Design Guide bolt force models."""

    @property
    def flush(self) -> bool:
        return self.layout in FLUSH

    @property
    def inside_rows(self) -> int:
        return INSIDE_ROWS[self.layout]

    @property
    def outside_rows(self) -> int:
        if self.flush:
            return 0
        return 2 if self.layout is EndPlateLayout.EXTENDED_8_STIFFENED else 1

    @property
    def tension_bolts(self) -> int:
        return 2 * (self.inside_rows + self.outside_rows)


def _hole_net(bolt: BoltSpec) -> float:
    return bolt.hole_dimensions[0] + to_internal(1 / 16, "in", Kind.LENGTH)


@dataclass(frozen=True)
class _Rows:
    """Bolt row distances d_n to the center of the compression flange and h_n to
    its outer face (Design Guide 16 notation; 0 for missing rows)."""

    d0: float
    d1: float
    d2: float
    d3: float
    h0: float
    h1: float
    h2: float
    h3: float
    dx: float = 0.0
    """8ES: second outer row, p_b beyond d_0."""

    @property
    def total(self) -> float:
        return self.dx + self.d0 + self.d1 + self.d2 + self.d3


def _rows(mc: MomentConnection, c: Calc) -> _Rows:
    ep, h, tf = mc.end_plate, mc.beam.d, mc.beam.tf
    clause = TABLE[ep.layout]
    L = Kind.LENGTH
    d0 = h0 = dx = 0.0
    if not ep.flush:
        h0 = c.step("h_0", "h + p_{f,o}", h + ep.pf_o, L, clause)
        d0 = c.step("d_0", "h + p_{f,o} - t_f/2", h + ep.pf_o - tf / 2, L, clause)
    if ep.outside_rows == 2:
        dx = c.step("d_x", "d_0 + p_b", d0 + ep.pb, L, clause)
    h1 = c.step("h_1", "h - t_f - p_f", h - tf - ep.pf, L, clause)
    d1 = c.step("d_1", "h_1 - t_f/2", h1 - tf / 2, L, clause)
    h2 = d2 = h3 = d3 = 0.0
    n = ep.inside_rows
    if n >= 2:
        h2 = c.step("h_2", "h_1 - p_b", h1 - ep.pb, L, clause)
        d2 = c.step("d_2", "d_1 - p_b", d1 - ep.pb, L, clause)
    if n >= 3:
        h3 = c.step("h_3", "h_1 - 2p_b", h1 - 2 * ep.pb, L, clause)
        d3 = c.step("d_3", "d_1 - 2p_b", d1 - 2 * ep.pb, L, clause)
    return _Rows(d0, d1, d2, d3, h0, h1, h2, h3, dx)


def _yield_parameter(mc: MomentConnection, r: _Rows, c: Calc) -> float:
    """Yield-line parameter Y of the end plate."""
    ep = mc.end_plate
    layout = ep.layout
    clause = TABLE[layout]
    L = Kind.LENGTH
    bp, g, pb = ep.width, ep.gage, ep.pb
    s = c.step("s", r"\frac{1}{2}\sqrt{b_p g}", 0.5 * math.sqrt(bp * g), L, clause,
               b_p=(bp, L), g=(g, L))
    if layout is EndPlateLayout.FLUSH_4_STIFFENED_INSIDE and s > ep.ps:
        s = c.step("s", r"\min(s, p_s)", ep.ps, L, clause)
    pf = ep.pf
    if pf > s:
        pf = c.step("p_f", r"s\ (p_f > s)", s, L, clause)
    h0, h1, h2, h3 = r.h0, r.h1, r.h2, r.h3
    expr: str
    if layout is EndPlateLayout.EXTENDED_8_STIFFENED:
        # Design Guide 4 measures h_1 to h_4 to the center of the compression flange
        H1, H2, H3, H4 = r.dx, r.d0, r.d1, r.d2
        pfo = ep.pf_o
        de = c.step("d_e", "p_{ext} - p_{f,o} - p_b", ep.pext - pfo - pb, L, clause)
        if de <= s:
            a1, b1 = 1 / (2 * de), de + pb / 4
            e1a, e1b = r"\frac{h_1}{2d_e}", r"h_1\left(d_e+\frac{p_b}{4}\right)"
        else:
            a1, b1 = 1 / s, s + pb / 4
            e1a, e1b = r"\frac{h_1}{s}", r"h_1\left(s+\frac{p_b}{4}\right)"
        expr = (rf"\frac{{b_p}}{{2}}\left[{e1a}+\frac{{h_2}}{{p_{{f,o}}}}+\frac{{h_3}}{{p_{{f,i}}}}"
                rf"+\frac{{h_4}}{{s}}\right]+\frac{{2}}{{g}}\left[{e1b}"
                r"+h_2\left(p_{f,o}+\frac{3p_b}{4}\right)+h_3\left(p_{f,i}+\frac{p_b}{4}\right)"
                r"+h_4\left(s+\frac{3p_b}{4}\right)+p_b^2\right]+g")
        Y = (bp / 2 * (H1 * a1 + H2 / pfo + H3 / pf + H4 / s)
             + 2 / g * (H1 * b1 + H2 * (pfo + 0.75 * pb) + H3 * (pf + pb / 4)
                        + H4 * (s + 0.75 * pb) + pb**2) + g)
    elif layout is EndPlateLayout.FLUSH_2:
        expr = (r"\frac{b_p}{2}\left[h_1\left(\frac{1}{p_f}+\frac{1}{s}\right)\right]"
                r"+\frac{2}{g}\left[h_1(p_f+s)\right]")
        Y = bp / 2 * h1 * (1 / pf + 1 / s) + 2 / g * h1 * (pf + s)
    elif layout in (EndPlateLayout.FLUSH_4, EndPlateLayout.FLUSH_4_STIFFENED_INSIDE):
        expr = (r"\frac{b_p}{2}\left[\frac{h_1}{p_f}+\frac{h_2}{s}\right]"
                r"+\frac{2}{g}\left[h_1(p_f+0.75p_b)+h_2(s+0.25p_b)\right]+\frac{g}{2}")
        Y = (bp / 2 * (h1 / pf + h2 / s)
             + 2 / g * (h1 * (pf + 0.75 * pb) + h2 * (s + 0.25 * pb)) + g / 2)
    elif layout is EndPlateLayout.FLUSH_4_STIFFENED_BETWEEN:
        ps_o = ep.ps_o
        ps_i = c.step("p_{s,i}", "p_b - p_{s,o} - t_s", pb - ps_o - ep.stiffener_thickness,
                      L, clause)
        expr = (r"\frac{b_p}{2}\left[h_1\left(\frac{1}{p_f}+\frac{1}{p_{s,o}}\right)"
                r"+h_2\left(\frac{1}{s}+\frac{1}{p_{s,i}}\right)\right]"
                r"+\frac{2}{g}\left[h_1(p_f+p_{s,o})+h_2(s+p_{s,i})\right]")
        Y = (bp / 2 * (h1 * (1 / pf + 1 / ps_o) + h2 * (1 / s + 1 / ps_i))
             + 2 / g * (h1 * (pf + ps_o) + h2 * (s + ps_i)))
    else:
        pfo = ep.pf_o
        de = ep.pext - pfo
        stiffened = layout in STIFFENED_EXTENSION
        if stiffened:
            de = c.step("d_e", "p_{ext} - p_{f,o}", de, L, clause)
        if stiffened and s < de:
            ext_a, ext_b = h0 * (1 / s + 1 / pfo), h0 * (s + pfo)
            ext_ea = r"h_0\left(\frac{1}{s}+\frac{1}{p_{f,o}}\right)"
            ext_eb = "h_0(s+p_{f,o})"
        elif stiffened:
            ext_a, ext_b = h0 * (1 / pfo + 1 / (2 * s)), h0 * (de + pfo)
            ext_ea = r"h_0\left(\frac{1}{p_{f,o}}+\frac{1}{2s}\right)"
            ext_eb = "h_0(d_e+p_{f,o})"
        else:
            ext_a, ext_b = h0 * (1 / pfo) - 0.5, 0.0
            ext_ea, ext_eb = r"h_0\frac{1}{p_{f,o}}-\frac{1}{2}", ""
        if layout in (EndPlateLayout.EXTENDED_4, EndPlateLayout.EXTENDED_4_STIFFENED):
            ina = h1 * (1 / pf + 1 / s)
            inb = h1 * (pf + s)
            ina_e = r"h_1\left(\frac{1}{p_{f,i}}+\frac{1}{s}\right)"
            inb_e = "h_1(p_{f,i}+s)"
            tail, tail_e = 0.0, ""
        elif layout is EndPlateLayout.EXTENDED_1_2:
            ina = h1 / pf + h2 / s
            inb = h1 * (pf + 0.75 * pb) + h2 * (s + 0.25 * pb)
            ina_e = r"\frac{h_1}{p_{f,i}}+\frac{h_2}{s}"
            inb_e = "h_1(p_{f,i}+0.75p_b)+h_2(s+0.25p_b)"
            tail, tail_e = g / 2, r"+\frac{g}{2}"
        else:
            ina = h1 / pf + h3 / s
            inb = h1 * (pf + 1.5 * pb) + h3 * (s + 0.5 * pb)
            ina_e = r"\frac{h_1}{p_{f,i}}+\frac{h_3}{s}"
            inb_e = "h_1(p_{f,i}+1.5p_b)+h_3(s+0.5p_b)"
            tail, tail_e = g / 2, r"+\frac{g}{2}"
        expr = (rf"\frac{{b_p}}{{2}}\left[{ina_e}+{ext_ea}\right]"
                rf"+\frac{{2}}{{g}}\left[{inb_e}{'+' + ext_eb if ext_eb else ''}\right]{tail_e}")
        Y = bp / 2 * (ina + ext_a) + 2 / g * (inb + ext_b) + tail
    return c.step("Y", expr, Y, L, clause, h_1=(h1, L))


def _tb(ep: EndPlate, c: Calc, Pt: float) -> float:
    clause = f"{SPEC} Table J3.1; {DG16}, Table 2-1"
    if ep.pretension is not None:
        return c.step("T_b", "", ep.pretension, Kind.FORCE, clause)
    d_in = from_internal(ep.bolt.diameter, Kind.LENGTH, "in")
    group = 150 if ep.bolt.material.Fnt > to_internal(100.0, "ksi", Kind.STRESS) else 120
    try:
        full = min_pretension(d_in, group)
        expr = ""
    except ValueError:
        full, expr = 0.7 * Pt, "0.7 P_t"
    if not ep.snug_tight:
        return c.step("T_b", expr, full, Kind.FORCE, clause)
    if d_in <= 5 / 8 + 1e-6:
        f = 0.75
    elif d_in <= 3 / 4 + 1e-6:
        f = 0.50
    elif d_in <= 7 / 8 + 1e-6:
        f = 0.375
    else:
        f = 0.25
    return c.step("T_b", rf"{f:g}\,T_{{b,J3.1}}", f * full, Kind.FORCE,
                  f"{DG16}, §2.5.2 (snug-tight A325)")


def _q_max(c: Calc, symbol: str, ep: EndPlate, wp: float, a: float, F: float) -> float | None:
    """Maximum prying force, or ``None`` when the radicand is negative."""
    t, Fpy = ep.thickness, ep.Fy
    radicand = Fpy**2 - 3 * (F / (wp * t)) ** 2
    if radicand < 0:
        c.step(r"F_{py}^2 - 3\left(\frac{F'}{w't_p}\right)^2", "", radicand,
               clause=f"{DG16}, §3.1.1 (radicand < 0: plate inadequate)")
        return None
    return c.step(symbol, r"\frac{w't_p^2}{4a}\sqrt{F_{py}^2-3\left(\frac{F'}{w't_p}\right)^2}",
                  wp * t * t / (4 * a) * math.sqrt(radicand), Kind.FORCE,
                  f"{DG16}, Eq. 2-11, 2-15")


def end_plate_strength(mc: MomentConnection, method: Method, combo: str = "",
                       ) -> tuple[Calc, float, Calc, float]:
    """(trace, available end-plate yielding strength, trace, bolt rupture strength)."""
    ep = mc.end_plate
    gamma = 1.25 if ep.flush else 1.0
    clause_t = TABLE[ep.layout]
    cy = Calc(method, combo)
    rows = _rows(mc, cy)
    Y = _yield_parameter(mc, rows, cy)
    t, Fpy = ep.thickness, ep.Fy
    mpl = cy.step("M_{pl}", "F_{py} t_p^2 Y", Fpy * t * t * Y, Kind.MOMENT, clause_t,
                  t_p=(t, Kind.THICKNESS), F_py=(Fpy, Kind.STRESS))
    cy.step(r"\gamma_r", "1.25\\ (flush),\\ 1.0\\ (extended)", gamma,
            clause=f"{DG16}, §2.5.3")
    yielding = available(mpl, FLEXURE, method) / gamma
    if method is Method.LRFD:
        cy.step(r"\phi_b M_{pl}/\gamma_r", "", yielding, Kind.MOMENT, clause_t)
    else:
        cy.step(r"M_{pl}/(\Omega\gamma_r)", "", yielding, Kind.MOMENT, clause_t)

    cb = Calc(method, combo)
    _rows(mc, cb)
    b = ep.bolt
    db = b.diameter
    Pt = cb.step("P_t", r"\frac{\pi d_b^2}{4} F_t", b.area * b.material.Fnt, Kind.FORCE,
                 f"{DG16}, Table 3-1, 4-1; {SPEC} Table J3.2", d_b=(db, Kind.LENGTH))
    mnp = cb.step("M_{np}", r"2P_t\sum d_n", 2 * Pt * rows.total, Kind.MOMENT,
                  f"{DG16}, Eq. 2-5", sum_d=(rows.total, Kind.LENGTH))
    thick = PHI * mnp <= PHI_B * mpl / 1.11
    cb.step(r"\phi M_{np} \le \phi_b M_{pl}/1.11", "", 1.0 if thick else 0.0,
            clause=f"{DG16}, Appendix B ({'thick plate' if thick else 'thin plate'})")
    if thick:
        rupture = cb.available(mnp, BOLT, Kind.MOMENT, f"{DG16}, Appendix B", "M_{np}")
        return cy, yielding, cb, rupture
    if ep.layout is EndPlateLayout.EXTENDED_8_STIFFENED:
        cb.step("M_q", "", 0.0, Kind.MOMENT,
                f"{DG4}, §3.3 (thin plate: prying not covered for 8ES)")
        return cy, yielding, cb, 0.0
    clause = f"{DG16}, Table 3-1, 4-1"
    L = Kind.LENGTH
    wp = cb.step("w'", r"b_p/2 - (d_b + 1/16\,in)",
                 ep.width / 2 - (db + to_internal(1 / 16, "in", L)), L, clause)
    ai = cb.step("a_i", r"3.682 (t_p/d_b)^3 - 0.085\,in",
                 (3.682 * (t / db) ** 3 - 0.085) * INCH, L, clause)
    Fi = cb.step("F'_i", r"\frac{t_p^2 F_{py}(0.85 b_p/2 + 0.80 w') + \pi d_b^3 F_t/8}{4 p_{f,i}}",
                 (t * t * Fpy * (0.85 * ep.width / 2 + 0.80 * wp)
                  + math.pi * db**3 * b.material.Fnt / 8) / (4 * ep.pf), Kind.FORCE, clause)
    Qi = _q_max(cb, "Q_{max,i}", ep, wp, ai, Fi)
    Tb = _tb(ep, cb, Pt)
    r = rows
    if ep.flush:
        options = [2 * Tb * (r.d1 + r.d2)]
        if Qi is not None:
            options.append(2 * (Pt - Qi) * (r.d1 + r.d2))
        expr = r"\max[2(P_t-Q_{max})(d_1+d_2),\ 2T_b(d_1+d_2)]"
        mq = max(options) if Qi is not None else 0.0
    else:
        ao = cb.step("a_o", r"\min(a_i,\ p_{ext} - p_{f,o})", min(ai, ep.pext - ep.pf_o), L,
                     clause)
        Fo = cb.step("F'_o", r"F'_i\,p_{f,i}/p_{f,o}", Fi * ep.pf / ep.pf_o, Kind.FORCE,
                     clause)
        Qo = _q_max(cb, "Q_{max,o}", ep, wp, ao, Fo)
        if Qi is None or Qo is None:
            mq = 0.0
        else:
            o, i = Pt - Qo, Pt - Qi
            mq = max(2 * o * r.d0 + 2 * i * (r.d1 + r.d3) + 2 * Tb * r.d2,
                     2 * o * r.d0 + 2 * Tb * (r.d1 + r.d2 + r.d3),
                     2 * i * (r.d1 + r.d3) + 2 * Tb * (r.d0 + r.d2),
                     2 * Tb * r.total)
        expr = (r"\max[2(P_t-Q_{o})d_0+2(P_t-Q_{i})(d_1+d_3)+2T_bd_2,\ "
                r"2(P_t-Q_{o})d_0+2T_b(d_1+d_2+d_3),\ "
                r"2(P_t-Q_{i})(d_1+d_3)+2T_b(d_0+d_2),\ 2T_b\sum d]")
    mq = cb.step("M_q", expr, mq, Kind.MOMENT, f"{DG16}, Eq. 2-18, 2-19")
    rupture = cb.available(mq, BOLT, Kind.MOMENT, f"{DG16}, Appendix B", "M_q")
    return cy, yielding, cb, rupture


def _rename(check: CheckResult, key: str) -> CheckResult:
    return check.model_copy(update={"id": f"moment.{key}", "text_id": f"check.moment.{key}"})


def end_plate_checks(mc: MomentConnection, V: float, M: float, P: float, method: Method,
                     combo: str = "") -> tuple[list[CheckResult], float, float]:
    """End-plate limit states; returns (results, flange force, bearing length at the column).

    ``P`` is the beam axial force, positive in compression.
    """
    ep, beam = mc.end_plate, mc.beam
    out: list[CheckResult] = []
    M = abs(M)
    c = Calc(method, combo)
    if P:
        M = c.step("M_u", r"|M| - P\frac{h - t_f}{2}", max(abs(M) - P * (beam.d - beam.tf) / 2,
                   0.0), Kind.MOMENT, f"{DG16}, §2.5.3 item 11; Example 4.2.3",
                   P=(P, Kind.FORCE))
    cy, yielding, cb, rupture = end_plate_strength(mc, method, combo)
    clause = TABLE[ep.layout]
    pre = list(c.steps)
    cy.steps[:0] = pre
    cb.steps[:0] = pre
    out.append(cy.result("moment.end_plate_yielding", clause, M, yielding, Kind.MOMENT))
    out.append(cb.result("moment.end_plate_bolt_rupture", f"{DG16}, Appendix B", M, rupture,
                         Kind.MOMENT))

    c = Calc(method, combo)
    Ffu = c.step("F_{fu}", "M_u/(d - t_f)", M / (beam.d - beam.tf), Kind.FORCE,
                 f"{DG16}, Example 4.2.3", d=(beam.d, Kind.LENGTH))
    t, hole = ep.thickness, _hole_net(ep.bolt)
    if not ep.flush and ep.layout not in STIFFENED_EXTENSION:
        out.append(_rename(elements.shear_yielding(ep.width * t, ep.Fy, Ffu / 2, method, combo),
                           "end_plate_shear_yielding"))
        out.append(_rename(elements.shear_rupture((ep.width - 2 * hole) * t, ep.Fu, Ffu / 2,
                                                  method, combo), "end_plate_shear_rupture"))

    out.append(_compression_bolts(mc, V, method, combo))

    if ep.web_weld > 0:
        c = Calc(method, combo)
        clause = f"{DG16}, §2.5.3 item 10; {SPEC} §J2.4"
        inner = beam.tf + ep.pf + (ep.inside_rows - 1) * ep.pb + 2 * ep.bolt.diameter
        lw = c.step("l_w", r"\min(d/2 - t_f,\ d - t_f - (t_f + p_f + (n_i-1)p_b + 2d_b))",
                    min(beam.d / 2 - beam.tf, beam.d - beam.tf - inner), Kind.LENGTH, clause)
        rw = fillet_weld_per_length(ep.web_weld, mc.FEXX, 0.0, method).capacity
        rn = c.step("R_n", "2 r_w l_w", 2 * rw * lw, Kind.FORCE, clause,
                    w=(ep.web_weld, Kind.THICKNESS))
        out.append(c.result("moment.end_plate_web_weld_shear", clause, V, rn, Kind.FORCE))
        c = Calc(method, combo)
        clause = f"{DG16}, §2.5.3 item 9; {SPEC} §J2.4, Eq. J2-5"
        need = c.step("r_{u,web}", "F_y t_w",
                      available(beam.material.Fy * beam.tw, TENSION_YIELD, method),
                      Kind.FORCE_PER_LENGTH, clause)
        cap = c.step("r_w", r"2 \times 1.5\,r_{w}", 2 * 1.5 * rw, Kind.FORCE_PER_LENGTH, clause)
        out.append(c.result("moment.end_plate_web_weld_tension", clause, need, cap,
                            Kind.FORCE_PER_LENGTH))

    if ep.flange_weld > 0:
        c = Calc(method, combo)
        clause = f"{DG16}, §2.5.3 item 8; {SPEC} §J2.4, Eq. J2-5"
        demand = c.step("R_u", r"\max(F_{fu},\ 0.6 F_y b_f t_f)",
                        max(Ffu, 0.6 * beam.material.Fy * beam.bf * beam.tf), Kind.FORCE, clause)
        rw = fillet_weld_per_length(ep.flange_weld, mc.FEXX, 0.0, method).capacity
        lw = 2 * beam.bf - beam.tw
        rn = c.step("R_n", r"1.5 r_w (2b_f - t_w)", 1.5 * rw * lw, Kind.FORCE, clause,
                    w=(ep.flange_weld, Kind.THICKNESS))
        out.append(c.result("moment.end_plate_flange_weld", clause, demand, rn, Kind.FORCE))
    N = beam.tf + (0.707 * ep.flange_weld if ep.flange_weld > 0 else 2 * ep.weld_reinforcement)
    return out, Ffu, N


def _compression_rows(ep: EndPlate, beam_tf: float) -> list[tuple[float, float | None]]:
    """(spacing to the adjacent rows, edge distance) of each bolt row at the compression
    flange, from the outermost row inward."""
    if not ep.symmetric:
        return [(math.inf, None)]
    spacing: list[float] = []
    edges: list[float | None] = []
    if not ep.flush:
        outer = [ep.pb] * (ep.outside_rows - 1)
        spacing += [*outer, ep.pf_o + beam_tf + ep.pf]
        edges += [ep.pext - ep.pf_o - (ep.outside_rows - 1) * ep.pb] + [None] * len(outer)
    spacing += [ep.pb] * (ep.inside_rows - 1)
    edges += [None] * ep.inside_rows
    rows = []
    gaps = spacing
    for i in range(len(edges)):
        near = [gaps[j] for j in (i - 1, i) if 0 <= j < len(gaps)]
        rows.append((min(near) if near else math.inf, edges[i]))
    return rows


def _compression_bolts(mc: MomentConnection, V: float, method: Method,
                       combo: str) -> CheckResult:
    """Shear on the bolts at the compression flange (DG16 §2.5.3 item 5; DG4 Eq. 3.17 to
    3.19): per bolt, the least of shear, bearing or tearout on the end plate (clear distance
    to the adjacent hole, or to the plate edge for the outermost row, so that the shear may
    act either way) and bearing on the column flange."""
    ep, col = mc.end_plate, mc.column
    b = ep.bolt
    t = ep.thickness
    c = Calc(method, combo)
    clause = f"{SPEC} §J3.7, §J3.11; {DG16}, §2.5.3 item 5; {DG4}, Eq. 3.17 to 3.19"
    kw = {"deformation_considered": mc.deformation_considered}
    dh = b.hole_dimensions[0]
    rv = c.step("r_{n,bolt}", "", bolts.bolt_shear(b, 0.0, method).capacity, Kind.FORCE, clause)
    bearing = bolts.bolt_bearing(b, t, ep.Fu, 0.0, method, **kw).capacity
    rc = c.step("r_{n,col}", "2.4 d t_{fc} F_{uc}",
                bolts.bolt_bearing(b, col.tf, col.material.Fu, 0.0, method, **kw).capacity,
                Kind.FORCE, clause)
    plate = total = 0.0
    for spacing, edge in _compression_rows(ep, mc.beam.tf):
        lcs = [spacing - dh] if spacing != math.inf else []
        if edge is not None:
            lcs.append(edge - dh / 2)
        rp = bearing
        if lcs:
            lc = min(lcs)
            rp = min(bearing, bolts.bolt_tearout(b, t, ep.Fu, lc, 0.0, method, **kw).capacity)
        plate += 2 * rp
        total += 2 * min(rv, rp, rc)
    n = 2 * len(_compression_rows(ep, mc.beam.tf))
    c.step("n_b", "", n, clause=clause)
    c.step(r"\sum r_{n,plate}", r"\sum \min(1.2 l_c t_p F_u,\ 2.4 d t_p F_u)", plate,
           Kind.FORCE, clause)
    c.step(r"\sum r_{n,col}", "", n * rc, Kind.FORCE, clause)
    rn = c.step(r"\sum \min(r_{n,bolt}, r_{n,plate}, r_{n,col})", "", total, Kind.FORCE,
                clause)
    return c.result("moment.end_plate_bolt_shear", clause, V, rn, Kind.FORCE)


def _column_yield_parameter(mc: MomentConnection, c: Calc, stiffened: bool) -> float:
    """Column flange yield-line parameter Y_c (Design Guide 4, Tables 3.4 and 3.5)."""
    ep, col, beam = mc.end_plate, mc.column, mc.beam
    clause = f"{DG4}, {COLUMN_TABLE[ep.layout]}"
    L = Kind.LENGTH
    r = _rows(mc, Calc(c.method))
    bfc, g, pb = col.bf, ep.gage, ep.pb
    s = c.step("s", r"\frac{1}{2}\sqrt{b_{fc} g}", 0.5 * math.sqrt(bfc * g), L, clause)
    cc = c.step("c", "p_{f,o} + t_{fb} + p_{f,i}", ep.pf_o + beam.tf + ep.pf, L, clause)
    if stiffened:
        ps = c.step("p_{so} = p_{si}", "(c - t_s)/2", (cc - mc.continuity_plate) / 2, L,
                    clause)
        psi = min(ps, s)
    eight = ep.layout is EndPlateLayout.EXTENDED_8_STIFFENED
    if not eight:
        h1, h0 = r.d1, r.d0
        if stiffened:
            expr = (r"\frac{b_{fc}}{2}\left[h_1\left(\frac{1}{s}+\frac{1}{p_{si}}\right)"
                    r"+h_0\left(\frac{1}{s}+\frac{1}{p_{so}}\right)\right]"
                    r"+\frac{2}{g}\left[h_1(s+p_{si})+h_0(s+p_{so})\right]")
            Y = (bfc / 2 * (h1 * (1 / s + 1 / psi) + h0 * (1 / s + 1 / ps))
                 + 2 / g * (h1 * (s + psi) + h0 * (s + ps)))
        else:
            expr = (r"\frac{b_{fc}}{2}\left[\frac{h_1}{s}+\frac{h_0}{s}\right]"
                    r"+\frac{2}{g}\left[h_1\left(s+\frac{3c}{4}\right)"
                    r"+h_0\left(s+\frac{c}{4}\right)+\frac{c^2}{2}\right]+\frac{g}{2}")
            Y = (bfc / 2 * (h1 / s + h0 / s)
                 + 2 / g * (h1 * (s + 0.75 * cc) + h0 * (s + cc / 4) + cc**2 / 2) + g / 2)
    else:
        h1, h2, h3, h4 = r.dx, r.d0, r.d1, r.d2
        if stiffened:
            expr = (r"\frac{b_{fc}}{2}\left[\frac{h_1}{s}+\frac{h_2}{p_{so}}+\frac{h_3}{p_{si}}"
                    r"+\frac{h_4}{s}\right]+\frac{2}{g}\left[h_1\left(s+\frac{p_b}{4}\right)"
                    r"+h_2\left(p_{so}+\frac{3p_b}{4}\right)+h_3\left(p_{si}+\frac{p_b}{4}\right)"
                    r"+h_4\left(s+\frac{3p_b}{4}\right)+p_b^2\right]+g")
            Y = (bfc / 2 * (h1 / s + h2 / ps + h3 / psi + h4 / s)
                 + 2 / g * (h1 * (s + pb / 4) + h2 * (ps + 0.75 * pb) + h3 * (psi + pb / 4)
                            + h4 * (s + 0.75 * pb) + pb**2) + g)
        else:
            expr = (r"\frac{b_{fc}}{2}\left[\frac{h_1}{s}+\frac{h_4}{s}\right]"
                    r"+\frac{2}{g}\left[h_1\left(p_b+\frac{c}{2}+s\right)"
                    r"+h_2\left(\frac{p_b}{2}+\frac{c}{4}\right)"
                    r"+h_3\left(\frac{p_b}{2}+\frac{c}{2}\right)+h_4 s\right]+\frac{g}{2}")
            Y = (bfc / 2 * (h1 / s + h4 / s)
                 + 2 / g * (h1 * (pb + cc / 2 + s) + h2 * (pb / 2 + cc / 4)
                            + h3 * (pb / 2 + cc / 2) + h4 * s) + g / 2)
    return c.step("Y_c", expr, Y, L, clause, b_fc=(bfc, L))


def end_plate_column_checks(mc: MomentConnection, Ffu: float, N: float, method: Method,
                            combo: str, column_shear: float | None,
                            column_axial: float) -> list[CheckResult]:
    """Column side of an end-plate connection (Design Guide 4, Steps 14 to 20).

    Flange bending (Eq. 3.20 to 3.22) for the 4E, 4ES and 8ES layouts; web local
    yielding (Eq. 3.24), web buckling at the compression flange (Eq. 3.26, 3.27) and web
    crippling (Eq. 3.29 to 3.31, §J10.3 with l_b = N). With continuity plates the web
    checks and the unstiffened flange strength set the plate force (Eq. 3.32).
    """
    ep, col, beam = mc.end_plate, mc.column, mc.beam
    near = mc.column_near_end
    plates = mc.continuity_plate > 0
    out: list[CheckResult] = []
    T = Kind.THICKNESS
    strengths: list[float] = []
    if ep.layout in COLUMN_TABLE:
        c = Calc(method, combo)
        clause = f"{DG4}, Eq. 3.20; {COLUMN_TABLE[ep.layout]}"
        Yc = _column_yield_parameter(mc, c, plates)
        b = ep.bolt
        rows = _rows(mc, Calc(method))
        mnp = c.step("M_{np}", r"2P_t\sum h_i", 2 * b.area * b.material.Fnt * rows.total,
                     Kind.MOMENT, f"{DG4}, Eq. 3.7, 3.8")
        Fyc = col.material.Fy
        treq = c.step("t_{fc,req}", r"\sqrt{\frac{1.11\,\phi M_{np}}{\phi_b F_{yc} Y_c}}",
                      math.sqrt(1.11 * PHI * mnp / (PHI_B * Fyc * Yc)), T, clause)
        out.append(c.result("moment.column_flange_bending", clause, treq, col.tf, T))
        c = Calc(method, combo)
        clause = f"{DG4}, Eq. 3.21, 3.22; {COLUMN_TABLE[ep.layout]}"
        Yc = _column_yield_parameter(mc, c, False)
        mcf = c.step("M_{cf}", "F_{yc} Y_c t_{fc}^2", Fyc * Yc * col.tf**2, Kind.MOMENT, clause)
        rn = c.step("R_n", "M_{cf}/(d - t_{fb})", mcf / (beam.d - beam.tf), Kind.FORCE, clause)
        rn = c.available(rn, FLEXURE, Kind.FORCE, clause)
        strengths.append(rn)
        out.append(c.result("moment.column_flange_strength", clause, Ffu, rn, Kind.FORCE,
                            applicable=not plates))

    c = Calc(method, combo)
    clause = f"{DG4}, Eq. 3.24"
    ct = c.step("C_t", r"0.5\ (near\ end),\ 1.0", 0.5 if near else 1.0, clause=clause)
    rn = c.step("R_n", r"[C_t(6k_c + 2t_p) + N] F_{yc} t_{wc}",
                (ct * (6 * col.k_des + 2 * ep.thickness) + N) * col.material.Fy * col.tw,
                Kind.FORCE, clause, N=(N, Kind.LENGTH), k_c=(col.k_des, Kind.LENGTH))
    rn = c.available(rn, J10_YIELD, Kind.FORCE, clause)
    strengths.append(rn)
    out.append(c.result("moment.column_web_local_yielding", clause, Ffu, rn, Kind.FORCE,
                        applicable=not plates))
    buckling = local.web_compression_buckling(col, Ffu, method, near, combo)
    crippling = local.web_local_crippling(col, N, Ffu, method, near, combo)
    for key, check, ref in (("column_web_compression_buckling", buckling, "Eq. 3.26, 3.27"),
                            ("column_web_crippling", crippling, "Eq. 3.29 to 3.31")):
        strengths.append(check.capacity)
        out.append(check.model_copy(update={
            "id": f"moment.{key}", "text_id": f"check.moment.{key}",
            "clause": f"{DG4}, {ref}; {check.clause}", "applicable": not plates}))
    if plates:
        c = Calc(method, combo)
        clause = f"{DG4}, Eq. 3.32; {SPEC} §J10.8, §J4.4"
        fsu = c.step("F_{su}", r"F_{fu} - \min \phi R_n", max(Ffu - min(strengths), 0.0),
                     Kind.FORCE, clause)
        ts = mc.continuity_plate
        bs = c.step("b_s", "(b_{fc} - t_{wc})/2", (col.bf - col.tw) / 2, Kind.LENGTH, clause)
        rn = c.step("R_n", "F_y (2 b_s t_s)", mc.plate_Fy * 2 * bs * ts, Kind.FORCE, clause,
                    t_s=(ts, T))
        out.append(c.result("moment.continuity_plates", clause, fsu,
                            c.available(rn, TENSION_YIELD, Kind.FORCE, clause), Kind.FORCE))
    if column_shear is not None:
        demand = (2 * Ffu if mc.two_sided else Ffu) - column_shear
        out.append(_rename(local.panel_zone_shear(col, column_axial, abs(demand), method,
                                                  combo=combo), "column_panel_zone"))
    return out

