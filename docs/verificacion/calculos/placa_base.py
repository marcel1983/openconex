# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Independent check of the AISC DG1 base-plate formulas.

This script does not import ``openconex``.  It recomputes three published
examples from AISC Design Guide 1 (3rd ed., 2024):

* Example 4.7-1: concentric axial compression without concrete confinement.
* Example 4.7-10: compression with a small moment, no anchor tension.
* Example 4.7-14: biaxial bending with axial compression.

Run with::

    python docs/verificacion/calculos/placa_base.py
    python docs/verificacion/calculos/placa_base.py --check

Units are inches and kips throughout.
"""

from __future__ import annotations

import math
import sys

PHI_C = 0.65
OMEGA_C = 2.31
PHI_B = 0.90
OMEGA_B = 1.67


def bearing_stress(fc: float, A2_over_A1: float, lrfd: bool) -> float:
    """DG1 Eq. 4-2: fp(max) = φc 0.85 f'c √(A2/A1) ≤ φc 1.7 f'c."""
    nominal = 0.85 * fc * min(math.sqrt(max(A2_over_A1, 1.0)), 2.0)
    return PHI_C * nominal if lrfd else nominal / OMEGA_C


def required_area(P: float, fc: float, A2_over_A1: float, lrfd: bool) -> float:
    """DG1 Eq. 4-6/4-7."""
    return P / bearing_stress(fc, A2_over_A1, lrfd)


def compression_design(P: float, d: float, bf: float, N: float, B: float,
                       Fy: float, fc: float, A2_over_A1: float,
                       lrfd: bool) -> dict[str, float]:
    """DG1 Eq. 4-10 to 4-15, I-shaped column."""
    fp = bearing_stress(fc, A2_over_A1, lrfd)
    pp = fp * B * N
    m = (N - 0.95 * d) / 2.0
    n = (B - 0.8 * bf) / 2.0
    n_prime = math.sqrt(d * bf) / 4.0
    X = 4.0 * d * bf / (d + bf) ** 2 * P / pp
    lam = 1.0 if X >= 1.0 else min(
        1.0, 2.0 * math.sqrt(X) / (1.0 + math.sqrt(1.0 - X)))
    critical = max(m, n, lam * n_prime)
    coefficient = (math.sqrt(2.0 / PHI_B) if lrfd else math.sqrt(2.0 * OMEGA_B))
    tp = critical * coefficient * math.sqrt(P / (Fy * B * N))
    return {"fp_max": fp, "Pp": pp, "Delta": (0.95 * d - 0.8 * bf) / 2.0,
            "m": m, "n": n, "lambda_n_prime": lam * n_prime, "l": critical,
            "X": X, "lambda": lam, "tp_req": tp}


def rectangular_bending(P: float, M: float, N: float, B: float, f: float,
                        fc: float, A2_over_A1: float,
                        lrfd: bool) -> dict[str, float]:
    """DG1 §4.3.3 to §4.3.6, uniform bearing stress."""
    fp = bearing_stress(fc, A2_over_A1, lrfd)
    q_max = fp * B
    e = M / P if P > 0 else math.inf
    e_crit = N / 2.0 - P / (2.0 * q_max) if P > 0 else -math.inf
    if P > 0 and e <= e_crit:
        Y = N - 2.0 * e
        return {"fp_max": fp, "q_max": q_max, "e": e, "e_crit": e_crit,
                "Y": Y, "q": P / Y, "T": 0.0}
    a = f + N / 2.0
    disc = a * a - 2.0 * (P * f + M) / q_max
    if disc < 0:
        return {"fp_max": fp, "q_max": q_max, "e": e, "e_crit": e_crit,
                "Y": math.nan, "q": q_max, "T": math.nan}
    Y = a - math.sqrt(disc)
    return {"fp_max": fp, "q_max": q_max, "e": e, "e_crit": e_crit,
            "Y": Y, "q": q_max, "T": q_max * Y - P}


def plate_thickness_compression(fp: float, Y: float, cantilever: float,
                                Fy: float, lrfd: bool) -> float:
    """DG1 Eq. 4-47 to 4-52."""
    mpl = (fp * cantilever**2 / 2.0 if Y >= cantilever
           else fp * Y * (cantilever - Y / 2.0))
    coefficient = (math.sqrt(4.0 / PHI_B) if lrfd
                   else math.sqrt(4.0 * OMEGA_B))
    return coefficient * math.sqrt(mpl / Fy) if mpl > 0 else 0.0


def plate_thickness_tension(T: float, x: float, B: float, Fy: float,
                            lrfd: bool) -> float:
    """DG1 Eq. 4-62."""
    coefficient = (math.sqrt(4.0 / PHI_B) if lrfd
                   else math.sqrt(4.0 * OMEGA_B))
    return coefficient * math.sqrt(max(T, 0.0) * max(x, 0.0) / (B * Fy))


def biaxial_capacity(P: float, N: float, B: float, f: float, fc: float,
                     A2_over_A1: float, T_capacity: float,
                     lrfd: bool) -> tuple[float, float]:
    """DG1 §4.3.7: moment capacity limited by the anchor tension."""
    q_max = bearing_stress(fc, A2_over_A1, lrfd) * B
    Y = (T_capacity + P) / q_max
    M = q_max * Y * (f + N / 2.0 - Y / 2.0) - P * f
    return Y, M


def dg1_4_7_1() -> dict[str, dict[str, float]]:
    """W12x96, 22 x 20 x 1.5 in. plate, f'c = 3 ksi, Pu = 700 kip, Pa = 466 kip."""
    out = {}
    for lrfd, P in ((True, 700.0), (False, 466.0)):
        result = compression_design(P, 12.7, 12.2, 22.0, 20.0, 50.0, 3.0, 1.0, lrfd)
        result["A1_req"] = required_area(P, 3.0, 1.0, lrfd)
        out["LRFD" if lrfd else "ASD"] = result
    return out


def dg1_4_7_10() -> dict[str, dict[str, float]]:
    """W12x96, 19 x 19 x 1.25 in. plate, f'c = 4 ksi, small moment."""
    out = {}
    for lrfd, P, M in ((True, 376.0, 940.0), (False, 260.0, 650.0)):
        result = rectangular_bending(P, M, 19.0, 19.0, 0.0, 4.0, 1.0, lrfd)
        m = (19.0 - 0.95 * 12.7) / 2.0
        n = (19.0 - 0.8 * 12.2) / 2.0
        fp = result["q"] / 19.0
        result["m"] = m
        result["n"] = n
        result["fp"] = fp
        result["tp_req_m"] = plate_thickness_compression(fp, result["Y"], m, 50.0, lrfd)
        result["tp_req"] = plate_thickness_compression(
            fp, result["Y"], max(m, n), 50.0, lrfd)
        out["LRFD" if lrfd else "ASD"] = result
    return out


def dg1_4_7_14() -> dict[str, float]:
    """W8x48, 14 x 14 x 1.75 in. plate, f'c = 4 ksi, Pu = 90 kip, Mux/Muy."""
    P, Mux, Muy = 90.0, 700.0, 450.0
    N = B = 14.0
    d, bf, tf = 8.50, 8.11, 0.685
    edge = 1.50
    f = N / 2.0 - edge
    result = rectangular_bending(P, Mux, N, B, f, 4.0, 4.0, True)
    m = (N - 0.95 * d) / 2.0
    n = (B - 0.8 * bf) / 2.0
    x = f - d / 2.0 + tf / 2.0
    # Two 5/8 in. F1554 Gr. 55 rods per face: φ N_sa = 0.75 F_u A_se.
    T_capacity = 2.0 * 0.75 * 75.0 * 0.226
    Y_capacity, M_capacity = biaxial_capacity(
        P, N, B, f, 4.0, 4.0, T_capacity, True)
    result.update({
        "f": f, "ex": Mux / P, "ey": Muy / P, "m": m, "n": n, "x": x,
        "T_capacity": T_capacity, "Y_capacity": Y_capacity,
        "M_capacity": M_capacity,
        "tp_req_compression": plate_thickness_compression(
            result["fp_max"], n, n, 50.0, True),
        "tp_req_tension": plate_thickness_tension(
            result["T"], x, B, 50.0, True),
        "interaction": (Mux / M_capacity) ** 2 + (Muy / M_capacity) ** 2,
    })
    return result


PUBLISHED = {
    "4.7-1": {
        "LRFD": {"A1_req": 422, "Delta": 1.15, "m": 4.97, "n": 5.12,
                 "lambda_n_prime": 3.11, "l": 5.12, "Pp": 729, "X": 0.960,
                 "lambda": 1.0, "tp_req": 1.36},
        "ASD": {"A1_req": 422, "Delta": 1.15, "m": 4.97, "n": 5.12,
                "lambda_n_prime": 3.11, "l": 5.12, "Pp": 486, "X": 0.958,
                "lambda": 1.0, "tp_req": 1.36},
    },
    "4.7-10": {
        "LRFD": {"e": 2.50, "Y": 14.0, "m": 3.47, "n": 4.62, "fp_max": 2.21,
                 "q_max": 42.0, "e_crit": 5.02, "q": 26.9, "fp": 1.41,
                 "tp_req_m": 0.868, "tp_req": 1.16},
        "ASD": {"e": 2.50, "Y": 14.0, "m": 3.47, "n": 4.62, "fp_max": 1.47,
                "q_max": 27.9, "e_crit": 4.84, "q": 18.6, "fp": 0.977,
                "tp_req_m": 0.888, "tp_req": 1.18},
    },
    "4.7-14": {
        "LRFD": {"f": 5.50, "fp_max": 4.42, "q_max": 61.9, "e_crit": 6.27,
                 "ex": 7.78, "ey": 5.00, "Y": 1.70, "T": 15.2, "m": 2.96,
                 "n": 3.76, "tp_req_compression": 1.67, "x": 1.59,
                 "tp_req_tension": 0.392, "T_capacity": 25.4,
                 "Y_capacity": 1.86, "M_capacity": 837, "interaction": 0.988},
    },
}

TOLERANCE = {"4.7-14": {"Y": 0.05, "T": 0.25, "tp_req_tension": 0.12}}


def main() -> int:
    for example, values in (("4.7-1", dg1_4_7_1()), ("4.7-10", dg1_4_7_10()),
                            ("4.7-14", {"LRFD": dg1_4_7_14()})):
        print(example)
        for method, result in values.items():
            print(f"  {method}: " + ", ".join(
                f"{key} = {value:8.3f}" for key, value in result.items()))
    return 0


def check() -> int:
    failures = []
    cases = (("4.7-1", dg1_4_7_1()), ("4.7-10", dg1_4_7_10()),
             ("4.7-14", {"LRFD": dg1_4_7_14()}))
    for example, computed in cases:
        for method, published in PUBLISHED[example].items():
            for key, target in published.items():
                value = computed[method][key]
                tolerance = TOLERANCE.get(example, {}).get(key, 0.01)
                if abs(value - target) / abs(target) > tolerance:
                    failures.append(
                        f"{example} {method} {key}: {value:.4f} vs {target:.4f} "
                        f"(tol {tolerance:.0%})")
    if failures:
        print("FAIL")
        for failure in failures:
            print(f"  {failure}")
        return 1
    print("OK: 59 independent values within the published tolerances.")
    return 0


if __name__ == "__main__":
    raise SystemExit(check() if "--check" in sys.argv else main())
