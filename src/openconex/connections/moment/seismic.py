# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Prequalified seismic moment connections (AISC 358-22, with AISC 341-22).

Capacity design of the beam-to-column connection of special (SMF) and
intermediate (IMF) moment frames for the probable maximum moment at the
plastic hinge, M_pr = C_pr R_y F_y Z_e (§2.4.3), with C_pr = (F_y + F_u)/(2F_y)
≤ 1.2. The hinge is at S_h from the column face; the shear at the hinge is
V_u = 2M_pr/L_h + V_gravity with L_h = L_cf − 2S_h, and the moment at the
column face is M_f = M_pr + V_u S_h. Resistance factors: φ_d = 1.00 for
ductile limit states and φ_n = 0.90 for non-ductile ones (§2.4.1). Only LRFD
is used, as in AISC 358.

Prequalified connections (the flange detail of the moment connection must
match):

* ``rbs`` — reduced beam section (Chapter 5) on a ``welded_flange`` connection:
  limits on a, b and c, Z_RBS = Z_x − 2c t_bf (d − t_bf), S_h = a + b/2,
  M_f ≤ φ_d M_pe with M_pe = R_y F_y Z_x;
* ``wuf_w`` — welded unreinforced flange–welded web (Chapter 8) on a
  ``welded_flange`` connection: hinge at the column face (S_h = 0, Z_e = Z_x);
* ``bfp`` — bolted flange plate (Chapter 7) on a ``bolted_flange_plate``
  connection: maximum bolt diameter, bolts, plate yielding and rupture, block
  shear and plate compression for F_pr = M_f/(d + t_p), S_h = S_1 + s(n/2 − 1);
* ``bueep`` / ``bseep`` — bolted unstiffened (4E) and stiffened (4ES, 8ES)
  extended end plates (Chapter 6) on an ``end_plate`` connection: Table 6.1
  limits, bolt rupture without prying, plate yielding (yield lines of AISC
  Design Guides 4 and 16), extension shear (4E), stiffener, compression bolts
  and bearing, and the column flange.

Common checks: beam and column limits of each chapter, width-to-thickness
ratios (AISC 341-22 Table D1.1: highly ductile for SMF, moderately ductile for
IMF), beam shear (AISC 360-22 §G2.1), the column-beam moment ratio (AISC 341
§E3.4a, SMF), the panel-zone thickness (§E3.6e.2, SMF) and the continuity plates
(§E3.6f). The column-side limit states of AISC 360 §J10 and the panel zone are
evaluated again for the flange force from M_f (combination ``AISC 358``).

The limits and equations here come from the published text of AISC 358-22 and
AISC 341-22 as summarized in the technical documentation; they must still be
checked against the standards and the AISC Seismic Design Manual (see
docs/tecnico/04-verificaciones.md).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from openconex.core.checks import CheckResult
from openconex.core.loads import Method
from openconex.core.materials import E_STEEL
from openconex.kernel.bolts import clear_distance
from openconex.kernel.design import Calc
from openconex.units import Kind, to_internal

if TYPE_CHECKING:
    from openconex.core.model import IShape

    from .fr_moment import MomentConnection

__all__ = ["EXPECTED", "PHI_D", "PHI_N", "Prequalified", "Seismic", "SeismicSystem",
           "expected_ratios", "seismic_checks"]

A358 = "AISC 358-22"
A341 = "AISC 341-22"
SPEC = "AISC 360-22"
COMBO = "AISC 358"
PHI_D = 1.00
PHI_N = 0.90
INCH = to_internal(1.0, "in", Kind.LENGTH)
L, T, F, M = Kind.LENGTH, Kind.THICKNESS, Kind.FORCE, Kind.MOMENT
W = Kind.FORCE_PER_LENGTH
D = Kind.DIMENSIONLESS


def _in(value: float) -> float:
    return value * INCH


def _plf(value: float) -> float:
    """Beam weight limit in lb/ft as a force per length."""
    return to_internal(value, "lbf/ft", W)


class SeismicSystem(StrEnum):
    SMF = "smf"
    """Special moment frame (AISC 341 §E3)."""
    IMF = "imf"
    """Intermediate moment frame (AISC 341 §E2)."""


class Prequalified(StrEnum):
    RBS = "rbs"
    WUF_W = "wuf_w"
    BFP = "bfp"
    BUEEP = "bueep"
    BSEEP = "bseep"


EXPECTED: dict[str, tuple[float, float, float, float]] = {
    # grade: (R_y shapes, R_t shapes, R_y plates, R_t plates); AISC 341-22 Table A3.2
    "ASTM A36": (1.5, 1.2, 1.3, 1.2),
    "ASTM A709 Gr. 36": (1.5, 1.2, 1.3, 1.2),
    "ASTM A1043 Gr. 36": (1.3, 1.1, 1.3, 1.1),
    "ASTM A1043 Gr. 50": (1.2, 1.1, 1.2, 1.1),
    "ASTM A529 Gr. 50": (1.2, 1.2, 1.2, 1.2),
    "ASTM A529 Gr. 55": (1.1, 1.2, 1.1, 1.2),
    "ASTM A572 Gr. 42": (1.3, 1.1, 1.3, 1.0),
    "ASTM A572 Gr. 50": (1.1, 1.1, 1.1, 1.2),
    "ASTM A572 Gr. 55": (1.1, 1.1, 1.1, 1.2),
    "ASTM A588": (1.1, 1.1, 1.1, 1.2),
    "ASTM A709 Gr. 50": (1.1, 1.1, 1.1, 1.2),
    "ASTM A913 Gr. 50": (1.1, 1.1, 1.1, 1.1),
    "ASTM A913 Gr. 60": (1.1, 1.1, 1.1, 1.1),
    "ASTM A913 Gr. 65": (1.1, 1.1, 1.1, 1.1),
    "ASTM A913 Gr. 70": (1.1, 1.1, 1.1, 1.1),
    "ASTM A992": (1.1, 1.1, 1.1, 1.1),
}
"""Expected-to-specified strength ratios R_y and R_t (verify against AISC 341-22 Table A3.2)."""


def expected_ratios(grade: str, plate: bool = False) -> tuple[float, float] | None:
    """(R_y, R_t) of a steel grade, or ``None`` if the grade is not tabulated."""
    row = EXPECTED.get(grade)
    if row is None:
        return None
    return (row[2], row[3]) if plate else (row[0], row[1])


@dataclass(frozen=True)
class Seismic:
    """AISC 358 data of a moment connection (internal units)."""

    connection: Prequalified
    system: SeismicSystem
    span: float
    """Clear span L_cf of the beam between column faces."""
    beam_Zx: float
    beam_A: float
    beam_weight: float
    """Beam weight per length, as a force per length."""
    column_Zx: float
    column_A: float
    Ry_beam: float
    Ry_column: float
    Ry_plate: float = 1.0
    Rt_beam: float = 1.0
    Rt_plate: float = 1.0
    gravity_load: float = 0.0
    """Uniform factored gravity load on the beam (1.2D + f1 L + 0.2S)."""
    gravity_shear: float = 0.0
    """Factored gravity shear at the plastic hinge, added to that of ``gravity_load``."""
    column_axial: float = 0.0
    """Required axial compression of the columns at the joint (column-beam ratio)."""
    column_above: bool = True
    """A column continues above the joint (two column moments in the ratio)."""
    beam_depth_label: float | None = None
    """Nominal depth of a catalog beam (in), from its designation."""
    column_depth_label: float | None = None
    rbs_a: float = 0.0
    rbs_b: float = 0.0
    rbs_c: float = 0.0
    bfp_s1: float = 0.0
    """BFP: column face to the nearest bolt row."""
    stiffener_thickness: float = 0.0
    """BSEEP: thickness of the end-plate stiffener."""
    stiffener_Fy: float = 0.0


def nominal_depth(label: str) -> float | None:
    """Nominal depth in inches of a ``W36X150``-style designation."""
    m = re.match(r"^W(\d+(?:\.\d+)?)X", label.upper())
    return float(m.group(1)) if m else None


def _range(c: Calc, check_id: str, clause: str, value: float, lo: float | None,
           hi: float | None, kind: Kind) -> CheckResult:
    """A prequalification range lo ≤ value ≤ hi as a check (ratio > 1 outside)."""
    if lo is not None:
        c.step(r"\min", "", lo, kind, clause)
    if hi is not None:
        c.step(r"\max", "", hi, kind, clause)
    low = lo / value if lo is not None and value > 0 else 0.0
    high = value / hi if hi is not None and hi > 0 else 0.0
    if lo is not None and (hi is None or low > high):
        return c.result(check_id, clause, lo, value, kind)
    return c.result(check_id, clause, value, hi, kind)


# -- prequalification limits ---------------------------------------------------------
_BEAM = {
    # connection: (max nominal depth in, max weight lb/ft, max t_bf in, min L/d SMF, IMF)
    Prequalified.RBS: (36.0, 302.0, 1.75, 7.0, 5.0, "§5.3.1"),
    Prequalified.WUF_W: (36.0, 150.0, 1.0, 7.0, 5.0, "§8.3.1"),
    Prequalified.BFP: (36.0, 150.0, 1.0, 9.0, 7.0, "§7.3.1"),
    Prequalified.BUEEP: (None, None, None, 7.0, 5.0, "§6.3.1"),
    Prequalified.BSEEP: (None, None, None, 7.0, 5.0, "§6.3.1"),
}
_COLUMN = {Prequalified.RBS: "§5.3.2", Prequalified.WUF_W: "§8.3.2",
           Prequalified.BFP: "§7.3.2", Prequalified.BUEEP: "§6.3.2",
           Prequalified.BSEEP: "§6.3.2"}
END_PLATE_LIMITS = {
    # layout: {parameter: (min in, max in)}; AISC 358-22 Table 6.1
    "extended_4": {"tbf": (0.375, 0.75), "bbf": (6.0, 9.25), "d": (13.75, 55.0),
                   "tp": (0.5, 2.25), "bp": (7.0, 10.75), "g": (4.0, 6.0),
                   "pf": (1.5, 4.5)},
    "extended_4_stiffened": {"tbf": (0.375, 0.75), "bbf": (6.0, 9.0), "d": (13.75, 24.0),
                             "tp": (0.5, 1.5), "bp": (7.0, 10.75), "g": (3.25, 6.0),
                             "pf": (1.75, 5.5)},
    "extended_8_stiffened": {"tbf": (0.5625, 1.0), "bbf": (7.5, 12.25), "d": (18.5, 36.0),
                             "tp": (0.75, 2.5), "bp": (9.0, 15.0), "g": (5.0, 6.0),
                             "pf": (1.625, 2.0), "pb": (3.5, 3.75)},
}
"""Parametric limits of the prequalified end plates (verify against AISC 358-22 Table 6.1)."""


def _hinge(mc: MomentConnection, s: Seismic, c: Calc) -> tuple[float, float, float, float]:
    """(M_pr, S_h, V_u, M_f) with their trace in ``c``."""
    beam = mc.beam
    Fy, Fu = beam.material.Fy, beam.material.Fu
    clause = f"{A358} §2.4.3"
    cpr = c.step("C_{pr}", r"\min\left(\frac{F_y + F_u}{2F_y},\ 1.2\right)",
                 min((Fy + Fu) / (2 * Fy), 1.2), D, clause, F_y=(Fy, Kind.STRESS),
                 F_u=(Fu, Kind.STRESS))
    conn = s.connection
    if conn is Prequalified.RBS:
        ze = c.step("Z_{RBS}", r"Z_x - 2c\,t_{bf}(d - t_{bf})",
                    s.beam_Zx - 2 * s.rbs_c * beam.tf * (beam.d - beam.tf),
                    Kind.SECTION_MODULUS, f"{A358} §5.8, Eq. 5.8-4",
                    Z_x=(s.beam_Zx, Kind.SECTION_MODULUS), c=(s.rbs_c, L))
        sh = c.step("S_h", "a + b/2", s.rbs_a + s.rbs_b / 2, L, f"{A358} §5.8")
    else:
        ze = c.step("Z_e", "Z_x", s.beam_Zx, Kind.SECTION_MODULUS, clause)
        if conn is Prequalified.WUF_W:
            sh = c.step("S_h", "0", 0.0, L, f"{A358} §8.7")
        elif conn is Prequalified.BFP:
            sh = c.step("S_h", "S_1 + s(n/2 - 1)", s.bfp_s1 + mc.spacing * (mc.rows - 1), L,
                        f"{A358} §7.6, Eq. 7.6-5", S_1=(s.bfp_s1, L), s=(mc.spacing, L))
        elif conn is Prequalified.BUEEP:
            sh = c.step("S_h", r"\min(d/2,\ 3b_{bf})", min(beam.d / 2, 3 * beam.bf), L,
                        f"{A358} §6.8.1")
        else:
            ep = mc.end_plate
            lst = c.step("L_{st}", r"h_{st}/\tan 30°", ep.pext / math.tan(math.radians(30)),
                         L, f"{A358} §6.6.4", h_st=(ep.pext, L))
            sh = c.step("S_h", "L_{st} + t_p", lst + ep.thickness, L, f"{A358} §6.8.1")
    mpr = c.step("M_{pr}", "C_{pr} R_y F_y Z_e", cpr * s.Ry_beam * Fy * ze, M, clause,
                 R_y=(s.Ry_beam, D))
    lh = c.step("L_h", "L_{cf} - 2S_h", s.span - 2 * sh, L, f"{A358} §2.3",
                L_cf=(s.span, L))
    vg = c.step("V_{gravity}", r"w_u L_h/2 + V_{g}", s.gravity_load * lh / 2 + s.gravity_shear,
                F, f"{A358} §2.4.3", w_u=(s.gravity_load, W))
    vu = c.step("V_u", "2M_{pr}/L_h + V_{gravity}", 2 * mpr / lh + vg, F, f"{A358} §2.4.3")
    mf = c.step("M_f", "M_{pr} + V_u S_h", mpr + vu * sh, M, f"{A358} §2.4.3")
    return mpr, sh, vu, mf


def _limits(mc: MomentConnection, s: Seismic) -> list[CheckResult]:
    beam, col = mc.beam, mc.column
    depth, weight, tf_max, smf, imf, sec = _BEAM[s.connection]
    clause = f"{A358} {sec}"
    out = []
    if depth is not None:
        c = Calc(Method.LRFD, COMBO)
        value = s.beam_depth_label if s.beam_depth_label is not None \
            else beam.d / INCH
        out.append(_range(c, "seismic.beam_depth", clause, _in(value), None, _in(depth), L))
    if weight is not None:
        c = Calc(Method.LRFD, COMBO)
        out.append(_range(c, "seismic.beam_weight", clause, s.beam_weight, None,
                          _plf(weight), W))
    if tf_max is not None:
        c = Calc(Method.LRFD, COMBO)
        out.append(_range(c, "seismic.beam_flange_thickness", clause, beam.tf, None,
                          _in(tf_max), T))
    c = Calc(Method.LRFD, COMBO)
    ratio = c.step("L_{cf}/d", "", s.span / beam.d, D, clause, L_cf=(s.span, L), d=(beam.d, L))
    out.append(_range(c, "seismic.span_depth", clause, ratio,
                      smf if s.system is SeismicSystem.SMF else imf, None, D))
    c = Calc(Method.LRFD, COMBO)
    value = s.column_depth_label if s.column_depth_label is not None else col.d / INCH
    out.append(_range(c, "seismic.column_depth", f"{A358} {_COLUMN[s.connection]}",
                      _in(value), None, _in(36.0), L))
    return out


def _slenderness(mc: MomentConnection, s: Seismic) -> list[CheckResult]:
    """Width-to-thickness ratios of AISC 341-22 Table D1.1."""
    highly = s.system is SeismicSystem.SMF
    level = "highly ductile" if highly else "moderately ductile"
    clause = f"{A341} §D1.1, Table D1.1 ({level})"
    out = []
    beam = mc.beam
    bf = beam.bf
    if s.connection is Prequalified.RBS:
        # flange width at the ends of the center two-thirds of the reduced section (§5.3.1)
        R = (4 * s.rbs_c**2 + s.rbs_b**2) / (8 * s.rbs_c)
        x = s.rbs_b / 3
        cut = s.rbs_c - (R - math.sqrt(max(R * R - x * x, 0.0)))
        bf = beam.bf - 2 * cut
    for member, shape, Ry, Pu, A, width in (
            ("beam", beam, s.Ry_beam, 0.0, s.beam_A, bf),
            ("column", mc.column, s.Ry_column, s.column_axial, s.column_A, mc.column.bf)):
        Fy = shape.material.Fy
        root = math.sqrt(E_STEEL / (Ry * Fy))
        c = Calc(Method.LRFD, COMBO)
        lam = c.step(r"b_f/2t_f", "", width / (2 * shape.tf), D, clause, b_f=(width, L),
                     t_f=(shape.tf, T))
        k = 0.32 if highly else 0.40
        lim = c.step(r"\lambda_{lim}", rf"{k}\sqrt{{E/(R_yF_y)}}", k * root, D, clause,
                     R_y=(Ry, D))
        out.append(c.result(f"seismic.{member}_flange_slenderness", clause, lam, lim, D))
        c = Calc(Method.LRFD, COMBO)
        h = shape.d - 2 * shape.k_des if shape.k_des > 0 else shape.d - 2 * shape.tf
        lam = c.step(r"h/t_w", "", h / shape.tw, D, clause, h=(h, L), t_w=(shape.tw, T))
        ca = c.step("C_a", r"P_u/(\phi_c R_y F_y A_g)", Pu / (0.9 * Ry * Fy * A), D, clause)
        if highly:
            if ca <= 0.114:
                lim, expr = 2.57 * root * (1 - 1.04 * ca), r"2.57\sqrt{E/R_yF_y}(1-1.04C_a)"
            else:
                lim = max(0.88 * root * (2.68 - ca), 1.57 * root)
                expr = r"0.88\sqrt{E/R_yF_y}(2.68-C_a) \ge 1.57\sqrt{E/R_yF_y}"
        else:
            if ca <= 0.114:
                lim, expr = 3.96 * root * (1 - 3.04 * ca), r"3.96\sqrt{E/R_yF_y}(1-3.04C_a)"
            else:
                lim = max(1.29 * root * (2.12 - ca), 1.57 * root)
                expr = r"1.29\sqrt{E/R_yF_y}(2.12-C_a) \ge 1.57\sqrt{E/R_yF_y}"
        lim = c.step(r"\lambda_{lim}", expr, lim, D, clause)
        out.append(c.result(f"seismic.{member}_web_slenderness", clause, lam, lim, D))
    return out


def _beam_shear(mc: MomentConnection, vu: float, c: Calc) -> CheckResult:
    beam = mc.beam
    Fy = beam.material.Fy
    clause = f"{SPEC} §G2.1; {A358} §2.4.3"
    h = beam.d - 2 * beam.k_des if beam.k_des > 0 else beam.d - 2 * beam.tf
    rolled = h / beam.tw <= 2.24 * math.sqrt(E_STEEL / Fy)
    phi = c.step(r"\phi_v", r"1.00\ (h/t_w \le 2.24\sqrt{E/F_y}),\ 0.90",
                 1.0 if rolled else 0.9, D, clause)
    kv = 5.34
    lim = 1.10 * math.sqrt(kv * E_STEEL / Fy)
    cv = 1.0 if rolled or h / beam.tw <= lim else lim / (h / beam.tw)
    cv = c.step("C_{v1}", "", cv, D, f"{SPEC} §G2.1")
    vn = c.step("V_n", "0.6 F_y d t_w C_{v1}", 0.6 * Fy * beam.d * beam.tw * cv, F, clause)
    cap = c.step(r"\phi_v V_n", "", phi * vn, F, clause)
    return c.result("seismic.beam_shear", clause, vu, cap, F)


def _column_beam_ratio(mc: MomentConnection, s: Seismic, mpr: float, sh: float,
                       vu: float) -> CheckResult:
    col = mc.column
    c = Calc(Method.LRFD, COMBO)
    clause = f"{A341} §E3.4a, Eq. E3-1"
    n_col = 2 if s.column_above else 1
    n_beam = 2 if mc.two_sided else 1
    mpc = c.step(r"\sum M^*_{pc}", r"n_c Z_c (F_{yc} - P_{uc}/A_g)",
                 n_col * s.column_Zx * max(col.material.Fy - s.column_axial / s.column_A, 0.0),
                 M, clause, n_c=(n_col, D), Z_c=(s.column_Zx, Kind.SECTION_MODULUS),
                 P_uc=(s.column_axial, F))
    mpb = c.step(r"\sum M^*_{pb}", r"n_b [M_{pr} + V_u (S_h + d_c/2)]",
                 n_beam * (mpr + vu * (sh + col.d / 2)), M, clause, n_b=(n_beam, D))
    c.step(r"\sum M^*_{pc}/\sum M^*_{pb}", r"> 1.0", mpc / mpb if mpb else math.inf, D, clause)
    return c.result("seismic.column_beam_ratio", clause, mpb, mpc, M)


def _panel_zone_thickness(mc: MomentConnection) -> list[CheckResult]:
    beam, col = mc.beam, mc.column
    clause = f"{A341} §E3.6e.2, Eq. E3-7"
    out = []
    for key, t in (("seismic.panel_zone_thickness", col.tw),
                   ("seismic.doubler_thickness", mc.doubler_plate)):
        if t <= 0:
            continue
        c = Calc(Method.LRFD, COMBO)
        dz = c.step("d_z", "d - 2t_f", beam.d - 2 * beam.tf, L, clause)
        wz = c.step("w_z", "d_c - 2t_{cf}", col.d - 2 * col.tf, L, clause)
        need = c.step("t_{min}", "(d_z + w_z)/90", (dz + wz) / 90, T, clause)
        out.append(c.result(key, clause, need, t, T))
    return out


def _continuity(mc: MomentConnection, s: Seismic, b: float, t: float) -> list[CheckResult]:
    """Continuity plates for flange width ``b`` and thickness ``t`` (beam flange or plate)."""
    beam, col = mc.beam, mc.column
    out = []
    if mc.continuity_plate <= 0:
        c = Calc(Method.LRFD, COMBO)
        clause = f"{A341} §E3.6f.1, Eq. E3-8, E3-9"
        Ryb = s.Ry_plate if s.connection is Prequalified.BFP else s.Ry_beam
        Fyb = mc.plate_Fy if s.connection is Prequalified.BFP else beam.material.Fy
        need = c.step("t_{cf,min}",
                      r"\max\left(0.4\sqrt{1.8 b_{bf} t_{bf}\frac{R_{yb}F_{yb}}{R_{yc}F_{yc}}},"
                      r"\ b_{bf}/6\right)",
                      max(0.4 * math.sqrt(1.8 * b * t * Ryb * Fyb / (s.Ry_column
                                                                     * col.material.Fy)),
                          b / 6), T, clause, b_bf=(b, L), t_bf=(t, T))
        out.append(c.result("seismic.continuity_plates", clause, need, col.tf, T))
    else:
        c = Calc(Method.LRFD, COMBO)
        clause = f"{A341} §E3.6f.2"
        if mc.two_sided:
            need = c.step("t_{cp,min}", "t_{bf}", t, T, clause)
        else:
            need = c.step("t_{cp,min}", r"t_{bf}/2", t / 2, T, clause)
        out.append(c.result("seismic.continuity_plate_thickness", clause, need,
                            mc.continuity_plate, T))
    return out


# -- connection-specific -----------------------------------------------------------------
def _rbs(mc: MomentConnection, s: Seismic, mf: float) -> list[CheckResult]:
    beam = mc.beam
    clause = f"{A358} §5.8, Eq. 5.8-1 to 5.8-3"
    out = []
    for key, value, klo, khi, ref, sym in (
            ("rbs_a", s.rbs_a, 0.5, 0.75, beam.bf, "b_f"),
            ("rbs_b", s.rbs_b, 0.65, 0.85, beam.d, "d"),
            ("rbs_c", s.rbs_c, 0.1, 0.25, beam.bf, "b_f")):
        c = Calc(Method.LRFD, COMBO)
        name = key[-1]
        c.step(name, rf"{klo:g}{sym} \le {name} \le {khi:g}{sym}", value, L, clause)
        out.append(_range(c, f"seismic.{key}", clause, value, klo * ref, khi * ref, L))
    c = Calc(Method.LRFD, COMBO)
    clause = f"{A358} §5.8, Step 6"
    Fy = beam.material.Fy
    mpe = c.step("M_{pe}", "R_y F_y Z_x", s.Ry_beam * Fy * s.beam_Zx, M, clause)
    c.step("M_f", "", mf, M, clause)
    out.append(c.result("seismic.rbs_moment_at_face", clause, mf,
                        c.step(r"\phi_d M_{pe}", "", PHI_D * mpe, M, clause), M))
    return out


def _bfp(mc: MomentConnection, s: Seismic, mpr: float, mf: float) -> list[CheckResult]:
    beam, b, plate = mc.beam, mc.bolt, mc.top
    tp, bp = plate.thickness, plate.width
    Fy, Fu = beam.material.Fy, beam.material.Fu
    out = []
    c = Calc(Method.LRFD, COMBO)
    clause = f"{A358} §7.6, Step 2"
    dmax = c.step("d_{b,max}", r"\frac{b_{bf}}{2}\left(1 - \frac{R_yF_y}{R_tF_u}\right) - 1/8\,in",
                  beam.bf / 2 * (1 - s.Ry_beam * Fy / (s.Rt_beam * Fu)) - _in(0.125), L,
                  clause)
    out.append(c.result("seismic.bfp_bolt_diameter", clause, b.diameter, dmax, L))

    c = Calc(Method.LRFD, COMBO)
    clause = f"{A358} §7.6, Steps 3 to 9"
    Fnv = b.material.Fnv_N if b.threads.value == "N" else b.material.Fnv_X
    rn = c.step("r_n", r"\min(F_{nv}A_b,\ 2.4F_{ub}d_bt_f,\ 2.4F_{up}d_bt_p)",
                min(Fnv * b.area, 2.4 * Fu * b.diameter * beam.tf,
                    2.4 * mc.plate_Fu * b.diameter * tp), F, clause)
    fpr = c.step("F_{pr}", "M_f/(d + t_p)", mf / (beam.d + tp), F, f"{A358} §7.6, Step 8",
                 M_f=(mf, M))
    n = 2 * mc.rows
    cap = c.step(r"n\phi_n r_n", "", n * PHI_N * rn, F, clause, n=(n, D))
    out.append(c.result("seismic.bfp_bolts", clause, fpr, cap, F))

    c = Calc(Method.LRFD, COMBO)
    clause = f"{A358} §7.6, Step 10"
    cap = c.step(r"\phi_d F_{yp} A_p", "", PHI_D * mc.plate_Fy * bp * tp, F, clause)
    out.append(c.result("seismic.bfp_plate_yielding", clause, fpr, cap, F))

    hole = b.hole_dimensions[0] + _in(1 / 16)
    c = Calc(Method.LRFD, COMBO)
    clause = f"{A358} §7.6, Step 11; {SPEC} §J4.1(b)"
    an = c.step("A_n", r"\min[(b_p - 2(d_h + 1/16))t_p,\ 0.85A_g]",
                min((bp - 2 * hole) * tp, 0.85 * bp * tp), Kind.AREA, clause)
    cap = c.step(r"\phi_n F_{up} A_n", "", PHI_N * mc.plate_Fu * an, F, clause)
    out.append(c.result("seismic.bfp_plate_rupture", clause, fpr, cap, F))

    c = Calc(Method.LRFD, COMBO)
    clause = f"{A358} §7.6, Step 12; {SPEC} §J4.3"
    length = (mc.rows - 1) * mc.spacing + mc.beam_lev - mc.underrun
    leh = (beam.bf - mc.gage) / 2
    t = beam.tf
    agv = 2 * length * t
    anv = agv - 2 * (mc.rows - 0.5) * hole * t
    ant = 2 * (leh - 0.5 * hole) * t
    rn_beam = min(0.6 * Fu * anv, 0.6 * Fy * agv) + Fu * ant
    plength = (mc.rows - 1) * mc.spacing + mc.plate_lev
    pleh = (bp - mc.gage) / 2
    pagv = 2 * plength * tp
    panv = pagv - 2 * (mc.rows - 0.5) * hole * tp
    rn_plate = min(min(0.6 * mc.plate_Fu * panv, 0.6 * mc.plate_Fy * pagv)
                   + mc.plate_Fu * 2 * (pleh - 0.5 * hole) * tp,
                   min(0.6 * mc.plate_Fu * panv, 0.6 * mc.plate_Fy * pagv)
                   + mc.plate_Fu * (mc.gage - hole) * tp)
    c.step("R_{n,beam}", r"0.6F_uA_{nv} + U_{bs}F_uA_{nt} \le 0.6F_yA_{gv} + U_{bs}F_uA_{nt}",
           rn_beam, F, clause)
    c.step("R_{n,plate}", "", rn_plate, F, clause)
    cap = c.step(r"\phi_n R_n", "", PHI_N * min(rn_beam, rn_plate), F, clause)
    out.append(c.result("seismic.bfp_block_shear", clause, fpr, cap, F))

    c = Calc(Method.LRFD, COMBO)
    clause = f"{A358} §7.6, Step 13; {SPEC} §J4.4 (K = 0.65, L = S_1)"
    r = tp / math.sqrt(12)
    kl = c.step(r"L_c/r", r"0.65 S_1/r", 0.65 * s.bfp_s1 / r, D, clause)
    Fyp = mc.plate_Fy
    if kl <= 25:
        pn = Fyp * bp * tp
    else:
        fe = math.pi**2 * E_STEEL / kl**2
        fcr = 0.658 ** (Fyp / fe) * Fyp if Fyp / fe <= 2.25 else 0.877 * fe
        pn = fcr * bp * tp
    pn = c.step("P_n", r"F_{cr} A_g", pn, F, clause)
    cap = c.step(r"\phi_n P_n", "", PHI_N * pn, F, clause)
    out.append(c.result("seismic.bfp_plate_compression", clause, fpr, cap, F))
    return out


def _end_plate(mc: MomentConnection, s: Seismic, vu: float, mf: float) -> list[CheckResult]:
    from .end_plate import EndPlateLayout, _rows, _yield_parameter
    ep, beam, col, b = mc.end_plate, mc.beam, mc.column, mc.end_plate.bolt
    out = []
    limits = END_PLATE_LIMITS[ep.layout.value]
    values = {"tbf": [beam.tf], "bbf": [beam.bf], "d": [beam.d], "tp": [ep.thickness],
              "bp": [ep.width], "g": [ep.gage], "pf": [ep.pf, ep.pf_o], "pb": [ep.pb]}
    clause = f"{A358} §6.3, Table 6.1"
    for key, (lo, hi) in limits.items():
        kind = T if key in ("tbf", "tp") else L
        checks = [_range(Calc(Method.LRFD, COMBO), f"seismic.end_plate_{key}", clause, v,
                         _in(lo), _in(hi), kind) for v in values[key]]
        out.append(max(checks, key=lambda r: r.ratio))

    c = Calc(Method.LRFD, COMBO)
    clause = f"{A358} §6.8, Step 3"
    rows = _rows(mc, c)
    Pt = c.step("P_t", "F_{nt}A_b", b.material.Fnt * b.area, F, clause)
    mnp = c.step("M_{np}", r"2P_t\sum h_i", 2 * Pt * rows.total, M, clause)
    cap = c.step(r"\phi_n M_{np}", "", PHI_N * mnp, M, clause)
    out.append(c.result("seismic.end_plate_bolt_rupture", clause, mf, cap, M))

    c = Calc(Method.LRFD, COMBO)
    clause = f"{A358} §6.8, Step 4"
    rows = _rows(mc, c)
    Y = _yield_parameter(mc, rows, c)
    cap = c.step(r"\phi_d F_{yp} t_p^2 Y_p / 1.11", "",
                 PHI_D * ep.Fy * ep.thickness**2 * Y / 1.11, M, clause)
    out.append(c.result("seismic.end_plate_yielding", clause, mf, cap, M))

    c = Calc(Method.LRFD, COMBO)
    ffu = c.step("F_{fu}", "M_f/(d - t_{bf})", mf / (beam.d - beam.tf), F,
                 f"{A358} §6.8, Step 6")
    if ep.layout is EndPlateLayout.EXTENDED_4:
        clause = f"{A358} §6.8, Step 7"
        cap = c.step(r"\phi_d 0.6 F_{yp} b_p t_p", "",
                     PHI_D * 0.6 * ep.Fy * ep.width * ep.thickness, F, clause)
        out.append(c.result("seismic.end_plate_shear_yielding", clause, ffu / 2, cap, F))
        c = Calc(Method.LRFD, COMBO)
        clause = f"{A358} §6.8, Step 8"
        an = c.step("A_n", r"[b_p - 2(d_b + 1/8\,in)]t_p",
                    (ep.width - 2 * (b.diameter + _in(0.125))) * ep.thickness, Kind.AREA,
                    clause)
        cap = c.step(r"\phi_n 0.6 F_{up} A_n", "", PHI_N * 0.6 * ep.Fu * an, F, clause)
        out.append(c.result("seismic.end_plate_shear_rupture", clause, ffu / 2, cap, F))
    else:
        clause = f"{A358} §6.8, Step 9"
        ts = s.stiffener_thickness
        Fys = s.stiffener_Fy or ep.Fy
        need = c.step("t_{s,min}", r"t_{bw} F_{yb}/F_{ys}", beam.tw * beam.material.Fy / Fys,
                      T, clause)
        out.append(c.result("seismic.end_plate_stiffener_thickness", clause, need, ts, T))
        c = Calc(Method.LRFD, COMBO)
        lam = c.step(r"h_{st}/t_s", "", ep.pext / ts if ts > 0 else math.inf, D, clause)
        lim = c.step(r"0.56\sqrt{E/F_{ys}}", "", 0.56 * math.sqrt(E_STEEL / Fys), D, clause)
        out.append(c.result("seismic.end_plate_stiffener_slenderness", clause, lam, lim, D))

    nb = 8 if ep.layout is EndPlateLayout.EXTENDED_8_STIFFENED else 4
    c = Calc(Method.LRFD, COMBO)
    clause = f"{A358} §6.8, Step 10"
    Fnv = b.material.Fnv_N if b.threads.value == "N" else b.material.Fnv_X
    cap = c.step(r"\phi_n n_b F_{nv} A_b", "", PHI_N * nb * Fnv * b.area, F, clause,
                 n_b=(nb, D))
    out.append(c.result("seismic.end_plate_compression_bolts", clause, vu, cap, F))

    c = Calc(Method.LRFD, COMBO)
    clause = f"{A358} §6.8, Step 11; {SPEC} §J3.11"
    rn = 0.0
    lc_inner = clear_distance(b, ep.pf + beam.tf + ep.pf_o, to_edge=False)
    for i in range(nb // 2):
        per = []
        for t, Fu_ in ((ep.thickness, ep.Fu), (col.tf, col.material.Fu)):
            bearing = 2.4 * b.diameter * t * Fu_
            per.append(min(1.2 * lc_inner * t * Fu_, bearing) if i == 0 else bearing)
        rn += 2 * min(per)
    rn = c.step("R_n", r"n_i r_{ni} + n_o r_{no}", rn, F, clause)
    cap = c.step(r"\phi_n R_n", "", PHI_N * rn, F, clause)
    out.append(c.result("seismic.end_plate_bearing", clause, vu, cap, F))
    return out


def _end_plate_column(mc: MomentConnection, s: Seismic, mf: float) -> list[CheckResult]:
    from .end_plate import _column_yield_parameter
    col = mc.column
    c = Calc(Method.LRFD, COMBO)
    clause = f"{A358} §6.8, Step 13 (column flange flexural yielding)"
    Yc = _column_yield_parameter(mc, c, mc.continuity_plate > 0)
    need = c.step("t_{cf,req}", r"\sqrt{\frac{1.11 M_f}{\phi_d F_{yc} Y_c}}",
                  math.sqrt(1.11 * mf / (PHI_D * col.material.Fy * Yc)), T, clause)
    return [c.result("seismic.end_plate_column_flange", clause, need, col.tf, T)]


def seismic_checks(mc: MomentConnection) -> list[CheckResult]:
    """AISC 358 / AISC 341 checks of ``mc.seismic`` (capacity design, LRFD)."""
    from .end_plate import end_plate_column_checks
    from .fr_moment import _column_checks

    s = mc.seismic
    assert s is not None
    c = Calc(Method.LRFD, COMBO)
    mpr, sh, vu, mf = _hinge(mc, s, c)
    out = _limits(mc, s) + _slenderness(mc, s)
    out.append(_beam_shear(mc, vu, c))
    smf = s.system is SeismicSystem.SMF
    if smf:
        out.append(_column_beam_ratio(mc, s, mpr, sh, vu))
        out += _panel_zone_thickness(mc)
    pz_shear = 0.0 if (smf or mc.panel_zone) else None
    if s.connection is Prequalified.RBS:
        out += _rbs(mc, s, mf)
    if s.connection is Prequalified.BFP:
        out += _bfp(mc, s, mpr, mf)
        out += _continuity(mc, s, mc.top.width, mc.top.thickness)
        pf = mf / (mc.beam.d + mc.top.thickness)
        column = _column_checks(mc, pf, mc.top.thickness, Method.LRFD, COMBO, pz_shear,
                                s.column_axial)
    elif s.connection in (Prequalified.BUEEP, Prequalified.BSEEP):
        out += _end_plate(mc, s, vu, mf) + _end_plate_column(mc, s, mf)
        ffu = mf / (mc.beam.d - mc.beam.tf)
        N = mc.beam.tf + 2 * (mc.end_plate.weld_reinforcement or 0.0)
        column = end_plate_column_checks(mc, ffu, N, Method.LRFD, COMBO, pz_shear,
                                         s.column_axial)
    else:
        out += _continuity(mc, s, mc.beam.bf, mc.beam.tf)
        pf = mf / (mc.beam.d - mc.beam.tf)
        column = _column_checks(mc, pf, mc.beam.tf, Method.LRFD, COMBO, pz_shear,
                                s.column_axial)
    return out + column


def section_properties(shape: IShape) -> tuple[float, float]:
    """(Z_x, A) of an I-shape from its plate dimensions (fillets neglected)."""
    d, bf, tf, tw = shape.d, shape.bf, shape.tf, shape.tw
    zx = bf * tf * (d - tf) + tw * (d - 2 * tf) ** 2 / 4
    return zx, 2 * bf * tf + (d - 2 * tf) * tw
