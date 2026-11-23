# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Concrete pedestal under a base plate, designed as a short tied column (ACI 318-19).

The pedestal is rectangular (``pedestal_N`` × ``pedestal_B``) or round (diameter
``pedestal_N``), centred on the column. Its longitudinal bars are the
``pedestal_rebars`` of the base plate. The critical section is the bottom of the
pedestal: M = M_top + V h, where h is the pedestal height.

* Axial force and flexure: strain compatibility with ε_cu = 0.003, the
  equivalent rectangular stress block 0.85 f'c over a = β1 c (ACI 318-19 §22.2),
  elastic-perfectly plastic bars, φ from the net tensile strain (Table 21.2.2,
  tied members) and P_n,max = 0.80 P_o (Table 22.4.2.1). With moments about
  both axes the linear load contour M_x/φM_nx + M_y/φM_ny ≤ 1 is used, which is
  conservative with respect to Bresler's load contour (ACI 318-19 R22.4).
* Shear: φ(V_c + V_s) with V_c from Table 22.5.5.1 and V_s from §22.5.8.5.3;
  round sections use b_w = D and d = 0.8 D (§22.5.2.2).
* Detailing: ρ_min ≤ ρ ≤ 0.08 (§10.6.1.1), tie spacing (§25.7.2.1) and the
  pedestal definition h/least lateral dimension ≤ 3 (§2.3).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from openconex.core.checks import CheckResult
from openconex.core.loads import Method
from openconex.kernel.design import Calc
from openconex.units import Kind, from_internal, to_internal

__all__ = [
    "Bar",
    "Pedestal",
    "PedestalShape",
    "Section",
    "beta1",
    "flexural_strength",
    "nominal_strength",
    "pedestal_checks",
    "phi_tied",
    "shear_strength",
]

ACI = "ACI 318-19"
EPS_CU = 0.003
PHI_SHEAR = 0.75
PHI_TENSION = 0.90
PHI_COMPRESSION = 0.65


class PedestalShape:
    RECTANGULAR = "rectangular"
    ROUND = "round"
    ALL = (RECTANGULAR, ROUND)


@dataclass(frozen=True)
class Pedestal:
    """Reinforced concrete pedestal data (the plan size is on the base plate)."""

    height: float
    """From the top of the footing to the top of the pedestal."""
    fy: float = 413.685  # 60 ksi
    shape: str = PedestalShape.RECTANGULAR
    tie_diameter: float = 0.0
    """0: no transverse reinforcement."""
    tie_spacing: float = 0.0
    tie_fy: float = 413.685
    tie_legs: int = 2
    """Legs of each tie crossing the shear plane."""
    min_ratio: float = 0.01
    lightweight: float = 1.0
    Es: float = 199_948.0  # 29 000 ksi, ACI 318-19 §20.2.2.2

    def __post_init__(self) -> None:
        if self.shape not in PedestalShape.ALL:
            raise ValueError(
                f"pedestal shape {self.shape!r} is not supported; use 'rectangular' or "
                "'round' (other shapes must be checked by hand)")
        if self.height <= 0:
            raise ValueError("pedestal height must be positive")


@dataclass(frozen=True)
class Bar:
    u: float
    """Distance from the section centroid, positive toward the compression face."""
    area: float


@dataclass(frozen=True)
class Section:
    """A pedestal section seen along one bending axis."""

    shape: str
    h: float
    """Depth in the bending direction (diameter for a round section)."""
    b: float
    """Width (diameter for a round section)."""
    bars: tuple[Bar, ...]

    @property
    def gross_area(self) -> float:
        if self.shape == PedestalShape.ROUND:
            return math.pi * self.h**2 / 4
        return self.h * self.b

    @property
    def steel_area(self) -> float:
        return sum(bar.area for bar in self.bars)

    def flipped(self) -> Section:
        return Section(self.shape, self.h, self.b,
                       tuple(Bar(-bar.u, bar.area) for bar in self.bars))


def beta1(fc: float) -> float:
    """β1 of the stress block (ACI 318-19 Table 22.2.2.4.3)."""
    psi = from_internal(fc, Kind.STRESS, "psi")
    if psi <= 4000:
        return 0.85
    return max(0.85 - 0.05 * (psi - 4000) / 1000, 0.65)


def phi_tied(eps_t: float, fy: float, Es: float) -> float:
    """φ of a tied member from the net tensile strain (ACI 318-19 Table 21.2.2)."""
    eps_ty = fy / Es
    if eps_t <= eps_ty:
        return PHI_COMPRESSION
    if eps_t >= eps_ty + 0.003:
        return PHI_TENSION
    return PHI_COMPRESSION + 0.25 * (eps_t - eps_ty) / 0.003


def _block(section: Section, a: float) -> tuple[float, float]:
    """Area of the compression block of depth a and its centroid from the section centre."""
    h = section.h
    a = min(max(a, 0.0), h)
    if section.shape == PedestalShape.ROUND:
        r = h / 2
        if a >= h:
            return math.pi * r * r, 0.0
        if a <= 0:
            return 0.0, r
        theta = 2 * math.acos((r - a) / r)
        area = r * r * (theta - math.sin(theta)) / 2
        centroid = 4 * r * math.sin(theta / 2) ** 3 / (3 * (theta - math.sin(theta)))
        return area, centroid
    return a * section.b, h / 2 - a / 2


@dataclass(frozen=True)
class Nominal:
    Pn: float
    Mn: float
    eps_t: float
    """Net tensile strain at the extreme tension bar (tension positive)."""
    Cc: float


def nominal_strength(section: Section, c: float, fc: float, fy: float,
                     Es: float = 199_948.0) -> Nominal:
    """P_n and M_n for a neutral axis depth c from the compression face (ACI 318-19 §22.2)."""
    b1 = beta1(fc)
    a = b1 * c
    area, centroid = _block(section, a)
    cc = 0.85 * fc * area
    pn, mn = cc, cc * centroid
    dt = 0.0
    for bar in section.bars:
        depth = section.h / 2 - bar.u
        dt = max(dt, depth)
        strain = EPS_CU * (c - depth) / c
        stress = max(min(Es * strain, fy), -fy)
        if stress > 0 and depth < min(a, section.h):
            stress -= 0.85 * fc  # concrete displaced by the bar
        pn += stress * bar.area
        mn += stress * bar.area * bar.u
    eps_t = EPS_CU * (dt - c) / c
    return Nominal(pn, mn, eps_t, cc)


def axial_limits(section: Section, fc: float, fy: float) -> tuple[float, float, float]:
    """(P_o, φP_n,max, φP_nt): ACI 318-19 §22.4.2 and Table 22.4.2.1 (tied)."""
    ast = section.steel_area
    po = 0.85 * fc * (section.gross_area - ast) + fy * ast
    return po, PHI_COMPRESSION * 0.80 * po, -PHI_TENSION * fy * ast


def flexural_strength(section: Section, Pu: float, fc: float, fy: float,
                      Es: float = 199_948.0) -> tuple[float, float, float]:
    """(φM_n, φ, c) at the factored axial load Pu (compression positive), both senses.

    Returns zero strength when Pu lies outside [φP_nt, φP_n,max].
    """
    _, pmax, pnt = axial_limits(section, fc, fy)
    if Pu > pmax or Pu < pnt:
        return 0.0, PHI_COMPRESSION, 0.0
    best = (math.inf, PHI_COMPRESSION, 0.0)
    for sense in (section, section.flipped()):
        def g(c: float, s: Section = sense) -> float:
            n = nominal_strength(s, c, fc, fy, Es)
            return phi_tied(n.eps_t, fy, Es) * n.Pn - Pu

        lo, hi = 1e-6 * sense.h, 50.0 * sense.h
        if g(lo) > 0:
            lo = 1e-9 * sense.h
        for _ in range(200):
            mid = (lo + hi) / 2
            if g(mid) > 0:
                hi = mid
            else:
                lo = mid
            if hi - lo < 1e-9 * sense.h:
                break
        c = (lo + hi) / 2
        n = nominal_strength(sense, c, fc, fy, Es)
        phi = phi_tied(n.eps_t, fy, Es)
        moment = max(phi * n.Mn, 0.0)
        if moment < best[0]:
            best = (moment, phi, c)
    return best


def _psi(value: float) -> float:
    return from_internal(value, Kind.STRESS, "psi")


def _in(value: float) -> float:
    return from_internal(value, Kind.LENGTH, "in")


def shear_strength(section: Section, Nu: float, fc: float, ped: Pedestal,
                   method: Method, combo: str, demand: float,
                   check_id: str) -> CheckResult:
    """φ(V_c + V_s) of the pedestal (ACI 318-19 §22.5)."""
    c = Calc(method, combo)
    lam = ped.lightweight
    if section.shape == PedestalShape.ROUND:
        bw = c.step("b_w", "D", section.h, Kind.LENGTH, f"{ACI} §22.5.2.2")
        d = c.step("d", "0.8 D", 0.8 * section.h, Kind.LENGTH, f"{ACI} §22.5.2.2")
    else:
        bw = c.step("b_w", "", section.b, Kind.LENGTH, f"{ACI} §22.5.2.1")
        far = max((-bar.u for bar in section.bars), default=0.0)
        d = c.step("d", r"\frac{h}{2} + u_{max}", section.h / 2 + far, Kind.LENGTH,
                   f"{ACI} §22.5.2.1")
    ag = section.gross_area
    fc_psi = _psi(fc)
    sqrt_fc = math.sqrt(fc_psi)
    bwd = _in(bw) * _in(d)  # in²
    axial_psi = _psi(Nu / (6 * ag))
    axial_psi = c.step(r"\frac{N_u}{6A_g}", r"\le 0.05 f'_c",
                       to_internal(min(axial_psi, 0.05 * fc_psi), "psi", Kind.STRESS),
                       Kind.STRESS, f"{ACI} Table 22.5.5.1")
    axial_psi = _psi(axial_psi)
    av = ped.tie_legs * math.pi * ped.tie_diameter**2 / 4 if ped.tie_diameter else 0.0
    fyt = min(ped.tie_fy, to_internal(60, "ksi", Kind.STRESS))
    av_min = 0.0
    if ped.tie_spacing > 0:
        av_min = c.step("A_{v,min}", r"\max(0.75\sqrt{f'_c},\ 50)\frac{b_w s}{f_{yt}}",
                        to_internal(max(0.75 * sqrt_fc, 50) * _in(bw) * _in(ped.tie_spacing)
                                    / _psi(fyt), "in**2", Kind.AREA),
                        Kind.AREA, f"{ACI} §10.6.2.2, Table 9.6.3.4")
        c.step("A_v", "n_{legs} A_{b,tie}", av, Kind.AREA, f"{ACI} §22.5.8.5.3")
    if av > 0 and av >= av_min:
        vc_lb = (2 * lam * sqrt_fc + axial_psi) * bwd
        c.step("V_c", r"\left(2\lambda\sqrt{f'_c} + \frac{N_u}{6A_g}\right)b_w d",
               to_internal(max(vc_lb, 0.0), "lbf", Kind.FORCE), Kind.FORCE,
               f"{ACI} Table 22.5.5.1(a)")
    else:
        tension = sum(bar.area for bar in section.bars if bar.u < 0)
        rho = c.step(r"\rho_w", r"\frac{A_s}{b_w d}", tension / (bw * d), clause=f"{ACI} §22.5.5.1")
        lam_s = c.step(r"\lambda_s", r"\sqrt{\frac{2}{1 + d/10}} \le 1",
                       min(math.sqrt(2 / (1 + _in(d) / 10)), 1.0), clause=f"{ACI} Eq. 22.5.5.1.3")
        vc_lb = (8 * lam_s * lam * rho ** (1 / 3) * sqrt_fc + axial_psi) * bwd
        c.step("V_c", r"\left(8\lambda_s\lambda\rho_w^{1/3}\sqrt{f'_c} + "
               r"\frac{N_u}{6A_g}\right)b_w d",
               to_internal(max(vc_lb, 0.0), "lbf", Kind.FORCE), Kind.FORCE,
               f"{ACI} Table 22.5.5.1(c)")
    vc_lb = min(max(vc_lb, 0.0), 5 * lam * sqrt_fc * bwd)
    vc = c.step("V_c", r"\le 5\lambda\sqrt{f'_c} b_w d", to_internal(vc_lb, "lbf", Kind.FORCE),
                Kind.FORCE, f"{ACI} §22.5.5.1.1")
    vs = 0.0
    if av > 0 and ped.tie_spacing > 0:
        vs = c.step("V_s", r"\frac{A_v f_{yt} d}{s} \le 8\sqrt{f'_c}b_w d",
                    min(av * fyt * d / ped.tie_spacing,
                        to_internal(8 * sqrt_fc * bwd, "lbf", Kind.FORCE)),
                    Kind.FORCE, f"{ACI} §22.5.8.5.3, §22.5.1.2")
    cap = c.step(r"\phi V_n", r"0.75(V_c + V_s)", PHI_SHEAR * (vc + vs), Kind.FORCE,
                 f"{ACI} §22.5.1.1")
    return c.result(check_id, f"{ACI} §22.5", demand, cap, Kind.FORCE)


def sections(shape: str, N: float, B: float,
             rebars: Sequence[tuple[float, float, float]]) -> tuple[Section, Section]:
    """Sections for the strong-axis moment (depth N, bars by x) and the weak axis (depth B)."""
    areas = [(x, y, math.pi * d * d / 4) for x, y, d in rebars]
    if shape == PedestalShape.ROUND:
        B = N
    strong = Section(shape, N, B, tuple(Bar(x, a) for x, _, a in areas))
    weak = Section(shape, B, N, tuple(Bar(y, a) for _, y, a in areas))
    return strong, weak


def pedestal_checks(ped: Pedestal, N: float, B: float,
                    rebars: Sequence[tuple[float, float, float]], fc: float, P: float,
                    V2: float, V3: float, M3: float, M2: float, method: Method,
                    combo: str = "") -> list[CheckResult]:
    """All pedestal checks for one combination (LRFD only)."""
    if method is not Method.LRFD:
        return []
    if not rebars:
        raise ValueError("pedestal design needs the longitudinal bars in pedestal_rebars")
    strong, weak = sections(ped.shape, N, B, rebars)
    out: list[CheckResult] = []
    least = N if ped.shape == PedestalShape.ROUND else min(N, B)

    c = Calc(method, combo)
    ratio = c.step(r"\frac{h_{ped}}{b_{min}}", "", ped.height / least, clause=f"{ACI} §2.3")
    out.append(c.result("base_plate.pedestal_slenderness", f"{ACI} §2.3", ratio, 3.0,
                        Kind.DIMENSIONLESS))

    ag, ast = strong.gross_area, strong.steel_area
    c = Calc(method, combo)
    c.step("A_g", "", ag, Kind.AREA)
    c.step("A_{st}", "", ast, Kind.AREA)
    rho = c.step(r"\rho_g", r"\frac{A_{st}}{A_g}", ast / ag, clause=f"{ACI} §10.6.1.1")
    out.append(c.result("base_plate.pedestal_reinforcement_min", f"{ACI} §10.6.1.1",
                        ped.min_ratio, rho, Kind.DIMENSIONLESS))
    c = Calc(method, combo)
    c.step(r"\rho_g", r"\frac{A_{st}}{A_g}", rho, clause=f"{ACI} §10.6.1.1")
    out.append(c.result("base_plate.pedestal_reinforcement_max", f"{ACI} §10.6.1.1",
                        rho, 0.08, Kind.DIMENSIONLESS))

    po, pmax, pnt = axial_limits(strong, fc, ped.fy)
    c = Calc(method, combo)
    c.step("P_o", r"0.85f'_c(A_g - A_{st}) + f_y A_{st}", po, Kind.FORCE, f"{ACI} §22.4.2.2")
    if P >= 0:
        cap = c.step(r"\phi P_{n,max}", r"0.65(0.80 P_o)", pmax, Kind.FORCE,
                     f"{ACI} Table 22.4.2.1")
        out.append(c.result("base_plate.pedestal_axial", f"{ACI} §22.4.2", P, cap, Kind.FORCE))
    else:
        cap = c.step(r"\phi P_{nt}", r"0.90 f_y A_{st}", -pnt, Kind.FORCE, f"{ACI} §22.4.3")
        out.append(c.result("base_plate.pedestal_axial", f"{ACI} §22.4.3", -P, cap, Kind.FORCE))

    mx = abs(M3) + abs(V2) * ped.height
    my = abs(M2) + abs(V3) * ped.height
    if mx > 0 or my > 0:
        c = Calc(method, combo)
        c.step("h_{ped}", "", ped.height, Kind.LENGTH)
        c.step(r"\beta_1", "", beta1(fc), clause=f"{ACI} Table 22.2.2.4.3")
        caps = []
        for label, moment, section in (("x", mx, strong), ("y", my, weak)):
            if moment <= 0:
                continue
            c.step(f"M_{{u{label}}}", r"M + V h_{ped}", moment, Kind.MOMENT)
            phi_mn, phi, depth = flexural_strength(section, P, fc, ped.fy, ped.Es)
            c.step("c", "", depth, Kind.LENGTH, f"{ACI} §22.2")
            c.step(r"\phi", "", phi, clause=f"{ACI} Table 21.2.2")
            caps.append((moment, c.step(rf"\phi M_{{n{label}}}", "", phi_mn, Kind.MOMENT,
                                        f"{ACI} §22.2, §22.4")))
        if len(caps) == 1:
            moment, cap = caps[0]
            out.append(c.result("base_plate.pedestal_flexure", f"{ACI} §22.4", moment, cap,
                                Kind.MOMENT))
        else:
            total = (sum(m / cap for m, cap in caps) if all(cap > 0 for _, cap in caps)
                     else math.inf)
            c.step(r"\frac{M_{ux}}{\phi M_{nx}} + \frac{M_{uy}}{\phi M_{ny}}", "", total,
                   clause=f"{ACI} R22.4")
            out.append(c.result("base_plate.pedestal_flexure", f"{ACI} R22.4", total, 1.0,
                                Kind.DIMENSIONLESS))

    long_bar = max(d for _, _, d in rebars)
    for v, section, key in ((abs(V2), strong, "pedestal_shear"),
                            (abs(V3), weak, "pedestal_shear_weak")):
        if v > 0:
            out.append(shear_strength(section, P, fc, ped, method, combo, v,
                                      f"base_plate.{key}"))
    if ped.tie_diameter and ped.tie_spacing:
        c = Calc(method, combo)
        limit = c.step("s_{max}", r"\min(16d_b,\ 48d_{tie},\ b_{min})",
                       min(16 * long_bar, 48 * ped.tie_diameter, least), Kind.LENGTH,
                       f"{ACI} §25.7.2.1")
        out.append(c.result("base_plate.pedestal_tie_spacing", f"{ACI} §25.7.2.1",
                            ped.tie_spacing, limit, Kind.LENGTH))
    return out


def round_edges(radius: float, f: float, half_spacing: float) -> float:
    """Equal edge distance e of the rectangle inscribed in a round pedestal.

    The rectangle has half sizes (f + e, s/2 + e) and its corners on the circle:
    (f + e)² + (s/2 + e)² = R². Its projected breakout areas lie inside the
    concrete, so it is a conservative equivalent of the round edge.
    """
    a, b = f, half_spacing
    # e² + (a + b) e + (a² + b² - R²)/2 = 0
    disc = (a + b) ** 2 - 2 * (a * a + b * b - radius * radius)
    if disc < 0:
        return 0.0
    return max((-(a + b) + math.sqrt(disc)) / 2, 0.0)
