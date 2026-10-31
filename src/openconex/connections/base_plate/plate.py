# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Base plate bearing, compression and bending, AISC Design Guide 1 (3rd ed., 2024).

Sign convention: P > 0 compression, P < 0 tension (uplift); M ≥ 0 about the
axis considered. N is the plate dimension along the moment, B the other one.
``f`` is the distance from the column axis to the tension anchor line.
All values in internal units (N, mm, MPa).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from openconex.core.loads import Method
from openconex.core.model import HSSKind
from openconex.kernel.design import Resistance, available

__all__ = [
    "BEARING",
    "PLATE_FLEXURE",
    "BendingResult",
    "CompressionDesign",
    "TriangularResult",
    "bearing_stress",
    "biaxial_capacity",
    "compression_design",
    "effective_area",
    "optimize_plan",
    "plate_thickness_compression",
    "plate_thickness_from_moment",
    "plate_thickness_tension",
    "rectangular_bending",
    "required_area",
    "triangular_bending",
    "uplift_low_moment",
]

BEARING = Resistance(0.65, 2.31)
"""Concrete bearing, AISC 360-22 §J8."""
PLATE_FLEXURE = Resistance(0.90, 1.67)


def bearing_stress(fc: float, A2_over_A1: float, method: Method) -> float:
    """Available bearing stress fp(max) = φc 0.85 f'c √(A2/A1) ≤ φc 1.7 f'c (DG1 Eq. 4-2)."""
    nominal = 0.85 * fc * min(math.sqrt(max(A2_over_A1, 1.0)), 2.0)
    return available(nominal, BEARING, method)


def required_area(P: float, fc: float, A2_over_A1: float, method: Method) -> float:
    """A1(req) = P / fp(max) (DG1 Eq. 4-6, 4-7)."""
    return P / bearing_stress(fc, A2_over_A1, method)


def optimize_plan(A1_req: float, d: float, bf: float, step: float = 25.4,
                  hss: HSSKind | None = None) -> tuple[float, float]:
    """Plate N × B with m ≈ n (DG1 Eq. 4-16 to 4-18), rounded up to ``step``."""
    if hss is HSSKind.ROUND:
        delta = 0.0
    elif hss is not None:
        delta = 0.95 * (d - bf) / 2
    else:
        delta = (0.95 * d - 0.8 * bf) / 2
    N = math.ceil((math.sqrt(A1_req) + delta) / step - 1e-9) * step
    B = math.ceil(A1_req / N / step - 1e-9) * step
    return N, B


@dataclass(frozen=True)
class CompressionDesign:
    fp_max: float
    Pp_available: float
    m: float
    n: float
    lambda_n_prime: float
    X: float
    lam: float
    l_crit: float
    """Critical cantilever: max(m, n, λn') for I-shapes, max(m, n) for HSS."""
    tp_req: float


def compression_design(P: float, d: float, bf: float, N: float, B: float, Fy: float, fc: float,
                       A2_over_A1: float, method: Method,
                       hss: HSSKind | None = None) -> CompressionDesign:
    """Concentric axial compression (DG1 §4.3.1, Eq. 4-10 to 4-15).

    For HSS columns the yield lines use 0.95 of both outside dimensions
    (rectangular/square) or 0.8 of the diameter (round), and λn' does not
    apply (DG1 §4.3.3).
    """
    fp = bearing_stress(fc, A2_over_A1, method)
    pp = fp * B * N
    if hss is HSSKind.ROUND:
        m = (N - 0.8 * d) / 2
        n = (B - 0.8 * d) / 2
        n_prime = X = 0.0
        lam = 1.0
    elif hss is not None:
        m = (N - 0.95 * d) / 2
        n = (B - 0.95 * bf) / 2
        n_prime = X = 0.0
        lam = 1.0
    else:
        m = (N - 0.95 * d) / 2
        n = (B - 0.8 * bf) / 2
        n_prime = math.sqrt(d * bf) / 4
        X = 4 * d * bf / (d + bf) ** 2 * P / pp
        lam = 1.0 if X >= 1 else min(1.0, 2 * math.sqrt(X) / (1 + math.sqrt(1 - X)))
    l_crit = max(m, n, lam * n_prime)
    if method is Method.LRFD:
        tp = l_crit * math.sqrt(2 * P / (PLATE_FLEXURE.phi * Fy * B * N))
    else:
        tp = l_crit * math.sqrt(2 * PLATE_FLEXURE.omega * P / (Fy * B * N))
    return CompressionDesign(fp, pp, m, n, lam * n_prime, X, lam, l_crit, tp)


def effective_area(d: float, bf: float, tf: float, tw: float, tp: float, N: float,
                   B: float) -> tuple[float, float]:
    """Effective bearing area of an I-shape on a plate, c = 1.5 tp (DG1 App. B.3).

    Returns (c, A_eff): flanges (bf + 2c)(tf + 2c) and web (tw + 2c)(d - 2tf - 2c),
    each clipped to the plate N × B.
    """
    c = 1.5 * tp
    flange = min(bf + 2 * c, B) * (tf + 2 * c)
    web_h = max(d - 2 * tf - 2 * c, 0.0)
    web = min(tw + 2 * c, B) * web_h
    total_h = min(d + 2 * c, N)
    area = 2 * flange + web
    if d + 2 * c > N:  # flanges clipped by the plate edges
        area -= min(bf + 2 * c, B) * (d + 2 * c - total_h)
    return c, area


@dataclass(frozen=True)
class BendingResult:
    case: str
    """'compression_only', 'low_moment', 'large_moment', 'uplift' or 'not_possible'."""
    e: float
    e_crit: float
    q_max: float
    fp_max: float
    Y: float
    q: float
    """Bearing force per unit length actually used (= q_max when anchors are in tension)."""
    T: float
    """Total anchor tension."""
    M_plate: float | None = None
    """Governing plate moment per unit width from the triangular model."""
    M_plate_tension: float | None = None
    """Plate moment per unit width at the tension interface (triangular model)."""
    bearing_stress: float | None = None
    """Peak bearing stress (triangular model; replaces q / q_max)."""
    bearing_capacity: float | None = None
    """Available bearing stress (triangular model)."""


def rectangular_bending(P: float, M: float, N: float, B: float, f: float, fc: float,
                        A2_over_A1: float, method: Method) -> BendingResult:
    """Uniform (rectangular) bearing stress model (DG1 §4.3.3 to §4.3.6).

    Moments about the tension anchors give q Y (f + N/2 - Y/2) = P f + M, so
    Y = (f + N/2) - √((f + N/2)² - 2(P f + M)/q_max) and T = q_max Y - P.
    """
    fp = bearing_stress(fc, A2_over_A1, method)
    q_max = fp * B
    e = M / P if P > 0 else (math.inf if M else 0.0)
    e_crit = N / 2 - P / (2 * q_max) if P > 0 else -math.inf
    if P > 0 and e <= e_crit:
        Y = N - 2 * e
        case = "compression_only" if M == 0 else "low_moment"
        return BendingResult(case, e, e_crit, q_max, fp, Y, P / Y, 0.0)
    if P < 0 and M <= -P * f:
        # anchors resist uplift and moment without bearing (see uplift_low_moment)
        return BendingResult("uplift", M / -P, e_crit, q_max, fp, 0.0, 0.0, -P)
    a = f + N / 2
    disc = a * a - 2 * (P * f + M) / q_max
    if disc < 0:
        return BendingResult("not_possible", e, e_crit, q_max, fp, math.nan, q_max, math.nan)
    Y = a - math.sqrt(disc)
    return BendingResult("large_moment" if P > 0 else "uplift" if P < 0 else "large_moment",
                         e, e_crit, q_max, fp, Y, q_max, q_max * Y - P)


def uplift_low_moment(P: float, M: float, rod_positions: list[float]) -> list[float]:
    """Rod forces when all anchors are in tension (DG1 Example 4.7-13).

    ``P`` < 0 (uplift); ``rod_positions`` are distances from the column axis
    along the moment direction. r_i = |P|/n + |P| e y_i / Σy².
    """
    n = len(rod_positions)
    iy = sum(y * y for y in rod_positions)
    return [-P / n + M * y / iy for y in rod_positions]


def _coef(method: Method) -> float:
    """√(4/φb) = 2.11 (LRFD) or √(4 Ωb) = 2.58 (ASD)."""
    return (math.sqrt(4 / PLATE_FLEXURE.phi) if method is Method.LRFD
            else math.sqrt(4 * PLATE_FLEXURE.omega))


def plate_thickness_compression(fp: float, Y: float, cantilever: float, Fy: float,
                                method: Method) -> float:
    """Required thickness at the bearing interface (DG1 Eq. 4-47 to 4-52).

    Y ≥ cantilever: Mpl = fp l²/2; otherwise Mpl = fp Y (l - Y/2).
    """
    mpl = fp * cantilever**2 / 2 if Y >= cantilever else fp * Y * (cantilever - Y / 2)
    return _coef(method) * math.sqrt(mpl / Fy) if mpl > 0 else 0.0


def plate_thickness_tension(T: float, x: float, B: float, Fy: float, method: Method) -> float:
    """Required thickness at the tension interface, 2.11 √(T x / (B Fy)) (DG1 Eq. 4-62)."""
    return _coef(method) * math.sqrt(max(T, 0.0) * max(x, 0.0) / (B * Fy))


def plate_thickness_from_moment(moment: float, Fy: float, method: Method) -> float:
    """Required thickness from a moment per unit width, √(4 M /(φ Fy))."""
    return _coef(method) * math.sqrt(max(moment, 0.0) / Fy) if moment > 0 else 0.0


@dataclass(frozen=True)
class TriangularResult:
    case: str
    e: float
    e_kern: float
    fp_axial: float
    fp_bending: float
    fp_max: float
    fp_min: float
    fp_available: float
    fp_at_m: float
    bearing_length: float
    T: float
    M_plate: float
    """Governing moment per unit width of plate at the compression interface."""
    M_plate_tension: float = 0.0
    """Plate moment per unit width at the tension interface (large moment)."""


def triangular_bending(P: float, M: float, N: float, B: float, m: float, n: float,
                       fc: float, A2_over_A1: float, method: Method,
                       rod_edge: float = 0.0, rods_in_tension: int = 2) -> TriangularResult:
    """Linear (triangular) bearing stress model (DG1 App. B.2).

    e ≤ N/6: fp = P/(BN) ± 6M/(BN²) (Eq. B-10 to B-14). Otherwise the bearing
    length A comes from Eq. B-21 with N' = N - rod_edge and A' = N/2 - rod_edge,
    and T = fp A B / 2 - P (Eq. B-22).
    """
    fp_av = bearing_stress(fc, A2_over_A1, method)
    e = M / P
    e_kern = N / 6
    if e <= e_kern:
        fa = P / (B * N)
        fb = 6 * M / (B * N * N)
        fmax, fmin = fa + fb, fa - fb
        fm = fmax - 2 * fb * m / N
        m_m = fm * m * m / 2 + (fmax - fm) * m * m / 3
        m_n = fa * n * n / 2
        return TriangularResult("low_moment", e, e_kern, fa, fb, fmax, fmin, fp_av, fm, N, 0.0,
                                max(m_m, m_n))
    n_p, a_p = N - rod_edge, N / 2 - rod_edge
    disc = (3 * n_p) ** 2 - 24 * (P * a_p + M) / (fp_av * B)
    if disc < 0:
        return TriangularResult("not_possible", e, e_kern, 0.0, 0.0, fp_av, 0.0, fp_av, 0.0,
                                0.0, 0.0, 0.0, 0.0)
    A = (3 * n_p - math.sqrt(disc)) / 2
    T = fp_av * A * B / 2 - P
    fm = fp_av * (A - m) / A if A > m else 0.0
    m_m = fm * m * m / 2 + (fp_av - fm) * m * m / 3 if A > m else fp_av * A / 2 * (m - A / 3)
    m_t = T / (2 * rods_in_tension) if T > 0 else 0.0
    return TriangularResult("large_moment", e, e_kern, 0.0, 0.0, fp_av, 0.0, fp_av, fm, A, T,
                            m_m, m_t)


def biaxial_capacity(P: float, N: float, B: float, f: float, fc: float, A2_over_A1: float,
                     T_capacity: float, method: Method) -> tuple[float, float]:
    """Moment strength about one axis limited by the anchors (DG1 §4.3.7, Example 4.7-14).

    With T = T_capacity: Y = (T + P)/q_max and M = q_max Y (f + N/2 - Y/2) - P f.
    Returns (Y, M).
    """
    q_max = bearing_stress(fc, A2_over_A1, method) * B
    Y = (T_capacity + P) / q_max
    return Y, q_max * Y * (f + N / 2 - Y / 2) - P * f
