# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Bolted beam and column splices with flange and web splice plates.

AISC 360-22 Chapters J and F13, AISC Manual 16th ed. Parts 7, 9 and 14.

Beam splice (``BeamSplice``): two beams of the same section, butt-to-butt with a
gap, joined by an outer plate on each flange (optionally two inner plates as
well, bolts in double shear) and two web plates.

* The flanges carry the moment as a force couple, T, C = M/d -/+ P A_f/A (P is
  compression positive): the axial force is shared by the flanges and the web in
  proportion to their areas. The flange bolts, the flange plates (tension
  yielding, rupture with A_e <= 0.85 A_g, block shear, compression with K = 0.65
  across the gap) and the beam flanges (block shear, §F13.1 flexural rupture at
  the holes) are checked for these forces.
* The web plates carry the shear V and the web share of the axial force,
  P A_w/A, applied at the splice centerline: the bolt group on one side is
  eccentric (instantaneous centre of rotation, Manual Part 7). The web plates are
  checked for shear yielding and rupture, block shear, flexure at the bolt line
  next to the gap (§J4.5) and tension.

Column splice (``ColumnSplice``): upper and lower columns with outer flange
plates; fillers make up half the depth difference. With finished (milled) ends
(``finished_ends``) compression is transferred by bearing (§J7 and §M2.6) and
the plates carry only the tension T = M/d - P A_f/A (or M/d + |P|/2 under net
tension). The weak-axis shear V_weak is carried by the flange bolts and the
strong-axis shear V by optional web plates. Bolts through fillers thicker than
1/4 in. are reduced by 1 - 0.4(t - 0.25) >= 0.85 (§J5.2) unless the fillers are
developed; undeveloped fillers are limited to 3/4 in.

Detailing limits (§J3.3 to §J3.5) are checked for every bolt group.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from openconex.core.checks import CheckResult
from openconex.core.loads import Forces, LoadCombination, Method, combine
from openconex.core.model import BoltSpec, IShape
from openconex.kernel import bolts, elements
from openconex.kernel.bolt_group import bolt_group_eccentric
from openconex.kernel.bolts import clear_distance
from openconex.kernel.design import FLEXURE, Calc, Resistance
from openconex.units import Kind, from_internal, to_internal

__all__ = ["BeamSplice", "ColumnSplice", "FlangeSplice", "WebSplice", "check_beam_splice",
           "check_column_splice", "check_splice_envelope", "filler_factor", "web_bolts"]

SPEC = "AISC 360-22"
MANUAL = "AISC Manual 16th ed."
INCH = to_internal(1.0, "in", Kind.LENGTH)
BEARING = Resistance(0.75, 2.00)
"""Bearing on finished surfaces (§J7)."""


@dataclass(frozen=True)
class FlangeSplice:
    """Flange splice plates and their bolts, on each side of the splice.

    The bolts are in two lines at the gage ``g``, ``rows`` bolts in each line on
    each side. The outer plate is ``width`` × ``thickness``; ``inner_width`` > 0
    adds an inner plate on each side of the web (bolts in double shear).
    """

    bolt: BoltSpec
    rows: int
    spacing: float
    gage: float
    width: float
    thickness: float
    lev_member: float
    """Member end to the nearest bolt row."""
    lev_plate: float
    """Last bolt row to the plate end."""
    Fy: float
    Fu: float
    inner_width: float = 0.0
    inner_thickness: float = 0.0

    @property
    def inner(self) -> bool:
        return self.inner_width > 0 and self.inner_thickness > 0

    @property
    def length(self) -> float:
        """Bolted length on one side, member end to plate end."""
        return self.lev_member + (self.rows - 1) * self.spacing + self.lev_plate


@dataclass(frozen=True)
class WebSplice:
    """Two web splice plates (one on each face of the web), bolts in double shear.

    On each side of the splice: ``columns`` vertical lines of ``rows`` bolts,
    centred on the plate height.
    """

    bolt: BoltSpec
    rows: int
    spacing: float
    height: float
    thickness: float
    lev_member: float
    """Member end to the nearest bolt line."""
    leh_plate: float
    """Last bolt line to the plate end."""
    Fy: float
    Fu: float
    columns: int = 1
    column_spacing: float = 0.0

    @property
    def lev(self) -> float:
        """Plate top and bottom edge to the outer bolt rows."""
        return (self.height - (self.rows - 1) * self.spacing) / 2

    @property
    def length(self) -> float:
        return self.lev_member + (self.columns - 1) * self.column_spacing + self.leh_plate


@dataclass(frozen=True)
class BeamSplice:
    beam: IShape
    beam_Sx: float
    flange: FlangeSplice
    web: WebSplice
    gap: float = INCH / 2
    """Gap between the beam ends."""
    deformation_considered: bool = True


@dataclass(frozen=True)
class ColumnSplice:
    upper: IShape
    lower: IShape
    flange: FlangeSplice
    web: WebSplice | None = None
    """Web plates for the strong-axis shear V (optional)."""
    gap: float = 0.0
    """Gap between the column ends (0 with finished ends)."""
    finished_ends: bool = True
    """Ends finished to bear (§M2.6): compression by bearing, plates take tension only."""
    filler_developed: bool = False
    """Fillers extended and developed (§J5.2(b)(1)): no bolt reduction or size limit."""
    deformation_considered: bool = True

    @property
    def filler(self) -> float:
        """Filler thickness at each flange, half the depth difference."""
        return abs(self.lower.d - self.upper.d) / 2

    @property
    def shallow(self) -> IShape:
        """The column with the fillers (the shallower one)."""
        return self.upper if self.upper.d <= self.lower.d else self.lower


# -- helpers -----------------------------------------------------------------------------
def _rename(check: CheckResult, key: str, **update: object) -> CheckResult:
    return check.model_copy(update={"id": f"splice.{key}", "text_id": f"check.splice.{key}",
                                    **update})


def _hole(bolt: BoltSpec) -> float:
    """Hole width for net areas, d_h + 1/16 in. (§B4.3b)."""
    return bolt.hole_dimensions[0] + elements.HOLE_ALLOWANCE


def _bear(bolt: BoltSpec, t: float, Fu: float, lc: float | None, method: Method,
          deform: bool) -> float:
    """min(bearing, tearout) available strength at one hole; ``lc`` None: bearing only."""
    rn = bolts.bolt_bearing(bolt, t, Fu, 0.0, method, deform).capacity
    if lc is not None:
        rn = min(rn, bolts.bolt_tearout(bolt, t, Fu, max(lc, 0.0), 0.0, method, deform).capacity)
    return rn


def filler_factor(t_filler: float, developed: bool = False) -> float:
    """Bolt shear reduction for fillers (§J5.2): 1 - 0.4(t - 0.25) >= 0.85, t in in."""
    t = from_internal(t_filler, Kind.LENGTH, "in")
    if developed or t <= 0.25:
        return 1.0
    return max(0.85, 1.0 - 0.4 * (t - 0.25))


def _detailing(prefix: str, bolt: BoltSpec, spacings: list[float], edges: list[float],
               t: float) -> list[CheckResult]:
    out = []
    spacing = min(spacings) if spacings else None
    smax = max(spacings) if spacings else None
    lo = bolts.bolt_spacing_checks(bolt, spacing, min(edges), t)
    hi = bolts.bolt_spacing_checks(bolt, smax, max(edges), t)
    for r in lo:
        if r.id in ("bolt.min_spacing", "bolt.min_edge"):
            out.append(_rename(r, f"{prefix}_{r.id.removeprefix('bolt.')}"))
    for r in hi:
        if r.id in ("bolt.max_spacing", "bolt.max_edge"):
            out.append(_rename(r, f"{prefix}_{r.id.removeprefix('bolt.')}"))
    return out


def _flange_forces(c: Calc, M: float, P: float, shape: IShape, net_tension_flanges: bool,
                   ) -> tuple[float, float]:
    """Tension and compression flange forces (P compression positive)."""
    clause = f"{MANUAL}, Eq. 11-1"
    d, A, Af = shape.d, shape.area, shape.bf * shape.tf
    share = c.step(r"\frac{A_f}{A}", r"\frac{b_f t_f}{A}", Af / A, clause=clause)
    if P < 0 and net_tension_flanges:
        T = c.step("T_f", r"\frac{M}{d} + \frac{|P|}{2}", M / d - P / 2, Kind.FORCE, clause,
                   M=(M, Kind.MOMENT), P=(P, Kind.FORCE), d=(d, Kind.LENGTH))
        C = c.step("C_f", r"\frac{M}{d} - \frac{|P|}{2}", M / d + P / 2, Kind.FORCE, clause)
    else:
        T = c.step("T_f", r"\frac{M}{d} - P\frac{A_f}{A}", M / d - P * share, Kind.FORCE,
                   clause, M=(M, Kind.MOMENT), P=(P, Kind.FORCE), d=(d, Kind.LENGTH))
        C = c.step("C_f", r"\frac{M}{d} + P\frac{A_f}{A}", M / d + P * share, Kind.FORCE,
                   clause)
    return T, C


def _flange_bolts(key: str, fl: FlangeSplice, t_member: float, Fu_member: float, T: float,
                  C: float, V: float, gap: float, method: Method, combo: str, deform: bool,
                  factor: float = 1.0, compression: bool = True) -> CheckResult:
    """Flange bolts on one side: 2 Σ min(shear, member, plates) for the flange force.

    Tension: the member bears toward its end and the plates toward their ends.
    Compression: the plates bear toward the splice across the gap. ``V`` is a
    shear across the flange (column weak axis), combined as a resultant.
    """
    b = fl.bolt
    planes = 2 if fl.inner else 1
    t_plates = fl.thickness + (fl.inner_thickness if fl.inner else 0.0)
    n = fl.rows
    inner = clear_distance(b, fl.spacing, to_edge=False)
    member_edge = clear_distance(b, fl.lev_member, to_edge=True)
    plate_edge = clear_distance(b, fl.lev_plate, to_edge=True)
    across = clear_distance(b, gap + 2 * fl.lev_member, to_edge=False)
    c = Calc(method, combo)
    clause = f"{SPEC} §J3.7, §J3.11" + (", §J5.2" if factor < 1 else "")
    shear = c.step("r_{n,v}", r"n_s F_{nv} A_b" + (r"\,(1 - 0.4(t_f - 0.25))"
                                                   if factor < 1 else ""),
                   bolts.bolt_shear(b, 0.0, method, planes).capacity * factor, Kind.FORCE,
                   clause, n_s=(planes, Kind.DIMENSIONLESS))
    if factor < 1:
        c.step(r"\text{filler}", r"1 - 0.4(t - 0.25) \ge 0.85", factor, clause=f"{SPEC} §J5.2")
    ten, com = [], []
    for i in range(n):
        m_t = _bear(b, t_member, Fu_member, member_edge if i == 0 else inner, method, deform)
        p_t = _bear(b, t_plates, fl.Fu, plate_edge if i == n - 1 else inner, method, deform)
        ten.append(min(shear, m_t, p_t))
        m_c = _bear(b, t_member, Fu_member, None if i == n - 1 else inner, method, deform)
        p_c = _bear(b, t_plates, fl.Fu, across if i == 0 else inner, method, deform)
        com.append(min(shear, m_c, p_c))
    rn_t = c.step(r"R_{n,T}", r"2\sum r_{n,i}", 2 * sum(ten), Kind.FORCE, clause,
                  n=(2 * n, Kind.DIMENSIONLESS))
    rn_c = c.step(r"R_{n,C}", r"2\sum r_{n,i}", 2 * sum(com), Kind.FORCE, clause)
    demand_t = math.hypot(max(T, 0.0), V)
    demand_c = math.hypot(max(C, 0.0), V) if compression else 0.0
    if V:
        c.step("V_f", "", V, Kind.FORCE, clause)
    if demand_c / rn_c > demand_t / rn_t:
        return c.result(f"splice.{key}", clause, demand_c, rn_c, Kind.FORCE)
    return c.result(f"splice.{key}", clause, demand_t, rn_t, Kind.FORCE)


def _plate_tension(fl: FlangeSplice, T: float, method: Method, combo: str) -> list[CheckResult]:
    t, h = fl.thickness, _hole(fl.bolt)
    Ag = fl.width * t + (2 * fl.inner_width * fl.inner_thickness if fl.inner else 0.0)
    An = (fl.width - 2 * h) * t + (2 * (fl.inner_width - h) * fl.inner_thickness
                                   if fl.inner else 0.0)
    Ae = elements.effective_net_area(An, Ag=Ag, bolted_splice_plate=True)
    applicable = T > 0
    out = [_rename(elements.tension_yielding(Ag, fl.Fy, max(T, 0.0), method, combo),
                   "flange_plate_tension_yielding", applicable=applicable),
           _rename(elements.tension_rupture(Ae, fl.Fu, max(T, 0.0), method, combo),
                   "flange_plate_tension_rupture", applicable=applicable)]
    # block shear of the outer plate, with its share of the force
    share = fl.width * t / Ag
    P = max(T, 0.0) * share
    n, g, length = fl.rows, fl.gage, (fl.rows - 1) * fl.spacing + fl.lev_plate
    leh = (fl.width - g) / 2
    agv = 2 * length * t
    anv = agv - 2 * (n - 0.5) * h * t
    outside = elements.block_shear(agv, anv, 2 * (leh - 0.5 * h) * t, fl.Fy, fl.Fu, P, method,
                                   1.0, combo)
    between = elements.block_shear(agv, anv, (g - h) * t, fl.Fy, fl.Fu, P, method, 1.0, combo)
    one = elements.block_shear(agv / 2, anv / 2, (g + leh - 1.5 * h) * t, fl.Fy, fl.Fu, P,
                               method, 1.0, combo)
    out.append(_rename(min(outside, between, one, key=lambda r: r.capacity),
                       "flange_plate_block_shear", applicable=applicable))
    if fl.inner:
        ti = fl.inner_thickness
        Pi = max(T, 0.0) * fl.inner_width * ti / Ag
        agv = length * ti
        check = elements.block_shear(agv, agv - (n - 0.5) * h * ti,
                                     (fl.inner_width / 2 - 0.5 * h) * ti, fl.Fy, fl.Fu, Pi,
                                     method, 1.0, combo)
        out.append(_rename(check, "inner_plate_block_shear", applicable=applicable))
    return out


def _plate_compression(fl: FlangeSplice, C: float, gap: float, method: Method, combo: str,
                       applicable: bool = True) -> CheckResult:
    c = Calc(method, combo)
    clause = f"{SPEC} §J4.4; Commentary Table C-A-7.1 (K = 0.65)"
    t_min = min(fl.thickness, fl.inner_thickness) if fl.inner else fl.thickness
    Ag = fl.width * fl.thickness + (2 * fl.inner_width * fl.inner_thickness if fl.inner
                                    else 0.0)
    L = c.step("L", "g_{ap} + 2 l_{e,m}", gap + 2 * fl.lev_member, Kind.LENGTH, clause)
    r = c.step("r", r"t_{min}/\sqrt{12}", t_min / math.sqrt(12), Kind.LENGTH, clause)
    kl = c.step(r"\frac{L_c}{r}", r"\frac{0.65 L}{r}", 0.65 * L / r, clause=clause)
    check = elements.compression(Ag, fl.Fy, kl, max(C, 0.0), method, combo)
    return _rename(check, "flange_plate_compression", clause=clause,
                   steps=tuple(c.steps) + check.steps, applicable=applicable and C > 0)


def _member_flange_block_shear(key: str, fl: FlangeSplice, shape: IShape, T: float,
                               method: Method, combo: str) -> CheckResult:
    h, n, g, tf = _hole(fl.bolt), fl.rows, fl.gage, shape.tf
    length = (n - 1) * fl.spacing + fl.lev_member
    agv = 2 * length * tf
    anv = agv - 2 * (n - 0.5) * h * tf
    Fy, Fu = shape.material.Fy, shape.material.Fu
    outside = elements.block_shear(agv, anv, 2 * ((shape.bf - g) / 2 - 0.5 * h) * tf, Fy, Fu,
                                   max(T, 0.0), method, 1.0, combo)
    between = elements.block_shear(agv, anv, (g - h) * tf, Fy, Fu, max(T, 0.0), method, 1.0,
                                   combo)
    return _rename(min(outside, between, key=lambda r: r.capacity), key, applicable=T > 0)


def _beam_flexural_rupture(bs: BeamSplice, M: float, method: Method, combo: str
                           ) -> CheckResult:
    c = Calc(method, combo)
    clause = f"{SPEC} §F13.1, Eq. F13-1"
    beam = bs.beam
    Fy, Fu = beam.material.Fy, beam.material.Fu
    afg = c.step("A_{fg}", "b_f t_f", beam.bf * beam.tf, Kind.AREA, clause)
    afn = c.step("A_{fn}", "A_{fg} - 2 (d_h + 1/16) t_f",
                 afg - 2 * _hole(bs.flange.bolt) * beam.tf, Kind.AREA, clause)
    yt = c.step("Y_t", r"1.0\ (F_y/F_u \le 0.8),\ 1.1", 1.0 if Fy / Fu <= 0.8 else 1.1,
                clause=clause)
    applies = Fu * afn < yt * Fy * afg
    mn = c.step("M_n", r"\frac{F_u A_{fn}}{A_{fg}} S_x", Fu * afn / afg * bs.beam_Sx,
                Kind.MOMENT, clause, S_x=(bs.beam_Sx, Kind.SECTION_MODULUS))
    return c.result("splice.beam_flexural_rupture", clause, M,
                    c.available(mn, FLEXURE, Kind.MOMENT, clause, "M_n"), Kind.MOMENT,
                    applicable=applies)


def web_bolts(w: WebSplice, gap: float) -> list[tuple[float, float]]:
    """Web bolts on one side, x from the splice centerline, y from mid-height."""
    y0 = -(w.rows - 1) * w.spacing / 2
    return [(gap / 2 + w.lev_member + j * w.column_spacing, y0 + i * w.spacing)
            for j in range(w.columns) for i in range(w.rows)]


def _web_checks(w: WebSplice, web: IShape, gap: float, V: float, Pw: float, method: Method,
                combo: str, deform: bool, factor: float = 1.0) -> list[CheckResult]:
    """Web plates for the shear ``V`` and the web axial force ``Pw`` (compression +)."""
    b, tp, h = w.bolt, w.thickness, _hole(w.bolt)
    out: list[CheckResult] = []
    c = Calc(method, combo)
    clause = f"{MANUAL}, Part 7; {SPEC} §J3.7, §J3.11"
    shear = c.step("r_{n,v}", "2 F_{nv} A_b", bolts.bolt_shear(b, 0.0, method, 2).capacity
                   * factor, Kind.FORCE, clause)
    web_rn = c.step("r_{n,web}", "2.4 d t_w F_u",
                    _bear(b, web.tw, web.material.Fu,
                          clear_distance(b, w.lev_member, True) if Pw < 0 else None,
                          method, deform), Kind.FORCE, clause)
    plate_rn = c.step("r_{n,pl}", r"\min(2.4 d (2t_p) F_u, 1.2 l_c (2t_p) F_u)",
                      _bear(b, 2 * tp, w.Fu, clear_distance(b, w.lev, True), method, deform),
                      Kind.FORCE, clause, l_ev=(w.lev, Kind.LENGTH))
    rn = c.step("r_n", r"\min(r_{n,v}, r_{n,web}, r_{n,pl})", min(shear, web_rn, plate_rn),
                Kind.FORCE, clause)
    R = math.hypot(V, Pw)
    angle = math.degrees(math.atan2(abs(Pw), abs(V))) if R else 0.0
    group = bolt_group_eccentric(web_bolts(w, gap), (0.0, 0.0), rn, R, method, angle,
                                 combo=combo)
    c.step(r"\theta", "", angle, clause=clause)
    out.append(_rename(group, "web_bolts", clause=clause, steps=tuple(c.steps) + group.steps))
    Agv = 2 * w.height * tp
    out.append(_rename(elements.shear_yielding(Agv, w.Fy, V, method, combo),
                       "web_plate_shear_yielding"))
    Anv = 2 * (w.height - w.rows * h) * tp
    out.append(_rename(elements.shear_rupture(Anv, w.Fu, V, method, combo),
                       "web_plate_shear_rupture"))
    # block shear of the plates: vertical plane through the line of bolts farthest from
    # the splice, horizontal tension plane to the plate end
    agv = 2 * (w.height - w.lev) * tp
    anv = agv - 2 * (w.rows - 0.5) * h * tp
    ant = 2 * (w.leh_plate + (w.columns - 1) * w.column_spacing
               - (w.columns - 0.5) * h) * tp
    out.append(_rename(elements.block_shear(agv, anv, ant, w.Fy, w.Fu, V, method,
                                            1.0 if w.columns == 1 else 0.5, combo),
                       "web_plate_block_shear"))
    c = Calc(method, combo)
    clause = f"{SPEC} §J4.5; {MANUAL}, Part 9"
    e = c.step("e", "g_{ap}/2 + l_{e,m}", gap / 2 + w.lev_member, Kind.LENGTH, clause)
    Mr = c.step("M_r", "V e", V * e, Kind.MOMENT, clause, V=(V, Kind.FORCE))
    Z = c.step("Z", r"2\frac{t_p h^2}{4}", 2 * tp * w.height**2 / 4, Kind.SECTION_MODULUS,
               clause)
    zy = elements.flexural_yielding(Z, w.Fy, Mr, method, combo)
    out.append(_rename(zy, "web_plate_flexural_yielding", clause=clause,
                       steps=tuple(c.steps) + zy.steps))
    ys = [abs(-(w.rows - 1) * w.spacing / 2 + i * w.spacing) for i in range(w.rows)]
    c2 = Calc(method, combo)
    Znet = c2.step("Z_{net}", r"Z - 2 t_p (d_h + 1/16) \sum |y_i|", Z - 2 * tp * h * sum(ys),
                   Kind.SECTION_MODULUS, clause)
    zr = elements.flexural_rupture(Znet, w.Fu, Mr, method, combo)
    out.append(_rename(zr, "web_plate_flexural_rupture", clause=clause,
                       steps=tuple(c.steps) + tuple(c2.steps) + zr.steps))
    tension = max(-Pw, 0.0)
    Ag = 2 * w.height * tp
    An = 2 * (w.height - w.rows * h) * tp
    out.append(_rename(elements.tension_yielding(Ag, w.Fy, tension, method, combo),
                       "web_plate_tension_yielding", applicable=tension > 0))
    out.append(_rename(elements.tension_rupture(
        elements.effective_net_area(An, Ag=Ag, bolted_splice_plate=True), w.Fu, tension,
        method, combo), "web_plate_tension_rupture", applicable=tension > 0))
    c = Calc(method, combo)
    clause = f"{MANUAL}, Part 9 (T distance)"
    T_dist = c.step("T", "d - 2k_{des}", web.d - 2 * web.k_des, Kind.LENGTH, clause)
    out.append(c.result("splice.web_plate_fit", clause, w.height, T_dist, Kind.LENGTH,
                        applicable=web.k_des > 0))
    spacings = [w.spacing] if w.rows > 1 else []
    if w.columns > 1:
        spacings.append(w.column_spacing)
    out += _detailing("web", b, spacings, [w.lev, w.lev_member, w.leh_plate],
                      min(tp, web.tw))
    return out


# -- beam splice --------------------------------------------------------------------------
def check_beam_splice(bs: BeamSplice, V: float, M: float, P: float, method: Method,
                      combo: str = "") -> list[CheckResult]:
    """Limit states of a bolted beam splice for V, M and P (P compression positive)."""
    beam, fl = bs.beam, bs.flange
    V, M = abs(V), abs(M)
    deform = bs.deformation_considered
    c = Calc(method, combo)
    T, C = _flange_forces(c, M, P, beam, net_tension_flanges=False)
    out = [_flange_bolts("flange_bolts", fl, beam.tf, beam.material.Fu, T, C, 0.0, bs.gap,
                         method, combo, deform)]
    out[0] = out[0].model_copy(update={"steps": tuple(c.steps) + out[0].steps})
    out += _plate_tension(fl, T, method, combo)
    out.append(_plate_compression(fl, C, bs.gap, method, combo))
    out.append(_member_flange_block_shear("beam_flange_block_shear", fl, beam, T, method,
                                          combo))
    out.append(_beam_flexural_rupture(bs, M, method, combo))
    edges = [fl.lev_member, fl.lev_plate, (fl.width - fl.gage) / 2, (beam.bf - fl.gage) / 2]
    out += _detailing("flange", fl.bolt, [fl.spacing] if fl.rows > 1 else [], edges,
                      min(fl.thickness, beam.tf))
    c = Calc(method, combo)
    Pw = c.step("P_w", r"P\frac{A - 2A_f}{A}", P * (beam.area - 2 * beam.bf * beam.tf)
                / beam.area, Kind.FORCE)
    out += _web_checks(bs.web, beam, bs.gap, V, Pw, method, combo, deform)
    return out


# -- column splice ------------------------------------------------------------------------
def _bearing(cs: ColumnSplice, C: float, Pw: float, method: Method,
             combo: str) -> list[CheckResult]:
    """Bearing of the upper column on the lower one (§J7(a), R_n = 1.8 F_y A_pb)."""
    up, lo = cs.upper, cs.lower
    Fy = min(up.material.Fy, lo.material.Fy)
    clause = f"{SPEC} §J7(a), Eq. J7-1"
    c = Calc(method, combo)
    overlap = c.step("t_c", r"\min(\tfrac{d_u}{2}, \tfrac{d_l}{2}) - \max(\tfrac{d_u}{2} - "
                     r"t_{f,u}, \tfrac{d_l}{2} - t_{f,l})",
                     max(0.0, min(up.d, lo.d) / 2 - max(up.d / 2 - up.tf, lo.d / 2 - lo.tf)),
                     Kind.THICKNESS, clause)
    A = c.step("A_{pb}", r"\min(b_{f,u}, b_{f,l})\,t_c", min(up.bf, lo.bf) * overlap,
               Kind.AREA, clause)
    rn = c.step("R_n", "1.8 F_y A_{pb}", 1.8 * Fy * A, Kind.FORCE, clause,
                F_y=(Fy, Kind.STRESS))
    out = [c.result("splice.column_flange_bearing", clause, max(C, 0.0),
                    c.available(rn, BEARING, Kind.FORCE, clause), Kind.FORCE)]
    c = Calc(method, combo)
    h = c.step("h_c", r"\min(d_u - 2t_{f,u}, d_l - 2t_{f,l})",
               min(up.d - 2 * up.tf, lo.d - 2 * lo.tf), Kind.LENGTH, clause)
    A = c.step("A_{pb}", r"h_c \min(t_{w,u}, t_{w,l})", h * min(up.tw, lo.tw), Kind.AREA,
               clause)
    rn = c.step("R_n", "1.8 F_y A_{pb}", 1.8 * Fy * A, Kind.FORCE, clause)
    out.append(c.result("splice.column_web_bearing", clause, max(Pw, 0.0),
                        c.available(rn, BEARING, Kind.FORCE, clause), Kind.FORCE))
    return out


def check_column_splice(cs: ColumnSplice, V: float, M: float, P: float, method: Method,
                        combo: str = "", V_weak: float = 0.0) -> list[CheckResult]:
    """Limit states of a bolted column splice (P compression positive)."""
    up, lo, fl = cs.upper, cs.lower, cs.flange
    V, M, V_weak = abs(V), abs(M), abs(V_weak)
    deform = cs.deformation_considered
    c = Calc(method, combo)
    T, C = _flange_forces(c, M, P, up, net_tension_flanges=True)
    bears = cs.finished_ends
    Vf = V_weak / 2
    factor = filler_factor(cs.filler, cs.filler_developed)
    out: list[CheckResult] = []
    for key, shape in (("upper", up), ("lower", lo)):
        f = factor if shape is cs.shallow else 1.0
        check = _flange_bolts(f"{key}_flange_bolts", fl, shape.tf, shape.material.Fu, T, C,
                              Vf, cs.gap, method, combo, deform, f, compression=not bears)
        out.append(check.model_copy(update={"steps": tuple(c.steps) + check.steps}))
    out += _plate_tension(fl, T, method, combo)
    out.append(_plate_compression(fl, C, cs.gap, method, combo, applicable=not bears))
    for key, shape in (("upper", up), ("lower", lo)):
        out.append(_member_flange_block_shear(f"{key}_flange_block_shear", fl, shape, T,
                                              method, combo))
    c = Calc(method, combo)
    Pw = c.step("P_w", r"P\frac{A - 2A_f}{A}", P * (up.area - 2 * up.bf * up.tf) / up.area,
                Kind.FORCE)
    if bears:
        out += _bearing(cs, C, Pw, method, combo)
    if cs.filler > to_internal(0.25, "in", Kind.LENGTH) and not cs.filler_developed:
        c = Calc(method, combo)
        clause = f"{SPEC} §J5.2(b)"
        limit = c.step("t_{max}", r"3/4\ in.", to_internal(0.75, "in", Kind.LENGTH),
                       Kind.THICKNESS, clause)
        out.append(c.result("splice.filler_thickness", clause, cs.filler, limit,
                            Kind.THICKNESS))
    edges = [fl.lev_member, fl.lev_plate, (fl.width - fl.gage) / 2,
             (min(up.bf, lo.bf) - fl.gage) / 2]
    out += _detailing("flange", fl.bolt, [fl.spacing] if fl.rows > 1 else [], edges,
                      min(fl.thickness, up.tf, lo.tf))
    if cs.web is not None:
        web = up if up.tw <= lo.tw else lo
        out += _web_checks(cs.web, web, cs.gap, V, 0.0 if bears else Pw, method, combo,
                           deform)
    return out


def check_splice_envelope(splice: BeamSplice | ColumnSplice,
                          combinations: Iterable[LoadCombination],
                          case_forces: Mapping[str, Forces]) -> list[CheckResult]:
    """Every combination: ``V2`` shear, ``M3`` moment, ``P`` axial (compression +) and,
    for column splices, ``V3`` the weak-axis shear."""
    results: list[CheckResult] = []
    for combo in combinations:
        f = combine(combo, case_forces)
        if isinstance(splice, BeamSplice):
            results += check_beam_splice(splice, f.V2, f.M3, f.P, combo.method, combo.name)
        else:
            results += check_column_splice(splice, f.V2, f.M3, f.P, combo.method, combo.name,
                                           V_weak=f.V3)
    return results
