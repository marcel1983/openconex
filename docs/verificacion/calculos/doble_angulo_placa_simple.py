# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Independent check of the double-angle and single-plate formulas.

This script does not import ``openconex``.  It recomputes the governing values
of Examples II.A-1A (all-bolted double angle) and II.A-17A (conventional
single plate) from the AISC 360-22 equations and the instantaneous-centre
method of Manual Part 7.  The ICR solver is a simple bisection on the centre
of rotation for a vertical bolt line; it is deliberately different from the
damped Newton iteration used by the program.

Run with::

    python docs/verificacion/calculos/doble_angulo_placa_simple.py
    python docs/verificacion/calculos/doble_angulo_placa_simple.py --check

Units are inches and kips throughout.
"""

from __future__ import annotations

import math
import sys

PHI_BOLT = 0.75
OMEGA_BOLT = 2.00
PHI_SHEAR_YIELD = 1.00
OMEGA_SHEAR_YIELD = 1.50
PHI_SHEAR_RUPTURE = 0.75
OMEGA_SHEAR_RUPTURE = 2.00
PHI_BLOCK = 0.75
OMEGA_BLOCK = 2.00

DELTA_MAX = 0.34  # in., Crawford and Kulak
BOLT_D = 0.75
BOLT_FNV = 54.0
HOLE = 0.8125  # standard hole for a 3/4 in. bolt
NET_HOLE = HOLE + 1.0 / 16.0


def available(nominal: float, phi: float, omega: float, lrfd: bool) -> float:
    return phi * nominal if lrfd else nominal / omega


def bolt_shear(d: float, Fnv: float, planes: int, lrfd: bool) -> float:
    """AISC 360-22 Eq. J3-1."""
    area = math.pi * d**2 / 4.0
    return available(planes * Fnv * area, PHI_BOLT, OMEGA_BOLT, lrfd)


def bearing_tearout(d: float, t: float, Fu: float, lc: float, lrfd: bool) -> float:
    """AISC 360-22 §J3.11(a)/(b), deformation considered."""
    bearing = 2.4 * d * t * Fu
    tearout = 1.2 * lc * t * Fu
    return available(min(bearing, tearout), PHI_BOLT, OMEGA_BOLT, lrfd)


def shear_yielding(area: float, Fy: float, lrfd: bool) -> float:
    """AISC 360-22 Eq. J4-3."""
    return available(0.60 * Fy * area, PHI_SHEAR_YIELD, OMEGA_SHEAR_YIELD, lrfd)


def shear_rupture(area: float, Fu: float, lrfd: bool) -> float:
    """AISC 360-22 Eq. J4-4."""
    return available(0.60 * Fu * area, PHI_SHEAR_RUPTURE, OMEGA_SHEAR_RUPTURE, lrfd)


def block_shear(Agv: float, Anv: float, Ant: float, Fy: float, Fu: float,
                lrfd: bool, Ubs: float = 1.0) -> float:
    """AISC 360-22 Eq. J4-5."""
    rupture = 0.60 * Fu * Anv + Ubs * Fu * Ant
    yielding = 0.60 * Fy * Agv + Ubs * Fu * Ant
    return available(min(rupture, yielding), PHI_BLOCK, OMEGA_BLOCK, lrfd)


def _bolt_response(distance: float, dmax: float) -> float:
    """Richard's equation, R/R_ult, as used by the AISC ICR method."""
    delta = DELTA_MAX * distance / dmax
    return (1.0 - math.exp(-10.0 * delta)) ** 0.55


def _residual(x0: float, bolts: list[tuple[float, float]],
              load_x: float) -> tuple[float, float]:
    """Vertical equilibrium residual for an IC on the centroid line."""
    y0 = sum(y for _x, y in bolts) / len(bolts)
    radii = [(x - x0, y - y0) for x, y in bolts]
    distances = [math.hypot(rx, ry) for rx, ry in radii]
    dmax = max(distances)
    lever = x0 - load_x
    sense = -1.0 if lever > 0 else 1.0
    fy = moment = 0.0
    for (rx, _ry), distance in zip(radii, distances, strict=True):
        if distance == 0:
            continue
        force = _bolt_response(distance, dmax)
        fy += sense * force * (rx / distance)
        moment += force * distance
    load = moment / abs(lever)
    return fy - load, load


def icr_coefficient(bolts: list[tuple[float, float]], load_x: float) -> float:
    """C by bisection on the instantaneous centre of rotation."""
    span = max(abs(x) for x, _y in bolts) + max(abs(y) for _x, y in bolts)
    for sign in (-1.0, 1.0):
        low = load_x + sign * 1e-6
        high = load_x + sign * 5.0 * span
        f_low = _residual(low, bolts, load_x)[0]
        f_high = _residual(high, bolts, load_x)[0]
        if f_low * f_high > 0:
            continue
        for _ in range(200):
            middle = (low + high) / 2.0
            f_middle = _residual(middle, bolts, load_x)[0]
            if abs(f_middle) < 1e-12:
                break
            if f_low * f_middle <= 0:
                high, f_high = middle, f_middle
            else:
                low, f_low = middle, f_middle
        return _residual((low + high) / 2.0, bolts, load_x)[1]
    raise ArithmeticError("ICR bracket not found")


def double_angle_ii_a_1a() -> dict[str, dict[str, float]]:
    """II.A-1A: 2L5x3-1/2x5/16, 8 x 3/4 in. A325-N, l = 23-1/2 in."""
    t, rows, spacing, length = 5.0 / 16.0, 8, 3.0, 23.5
    lev, leh_beam, leh_support = 1.25, 1.375, 1.75
    Fy, Fu = 50.0, 65.0
    beam_tw, beam_Fu = 0.760, 65.0
    support_t, support_Fu = 0.710, 65.0
    out = {}
    for lrfd in (True, False):
        two = bolt_shear(BOLT_D, BOLT_FNV, 2, lrfd)
        edge = bearing_tearout(BOLT_D, t, Fu, lev - HOLE / 2.0, lrfd)
        inner = bearing_tearout(BOLT_D, t, Fu, spacing - HOLE, lrfd)
        web = bearing_tearout(BOLT_D, beam_tw, beam_Fu, spacing - HOLE, lrfd)
        support = bearing_tearout(BOLT_D, support_t, support_Fu, spacing - HOLE, lrfd)
        beam = (rows - 1) * min(two, 2 * inner, web) + min(two, 2 * edge, web)
        sup = (rows - 1) * min(two, 2 * inner, 2 * support) + min(two, 2 * edge, 2 * support)
        Agv = 2 * (length - lev) * t
        Anv = Agv - 2 * (rows - 0.5) * NET_HOLE * t
        Ant_beam = 2 * (leh_beam - 0.5 * NET_HOLE) * t
        Ant_support = 2 * (leh_support - 0.5 * NET_HOLE) * t
        out["LRFD" if lrfd else "ASD"] = {
            "bolts_beam": beam,
            "bolts_support": sup,
            "angle_shear_yielding": shear_yielding(2 * length * t, Fy, lrfd),
            "angle_shear_rupture": shear_rupture(2 * (length - rows * NET_HOLE) * t, Fu,
                                                 lrfd),
            "block_shear_beam": block_shear(Agv, Anv, Ant_beam, Fy, Fu, lrfd),
            "block_shear_support": block_shear(Agv, Anv, Ant_support, Fy, Fu, lrfd),
        }
    return out


def single_plate_ii_a_17a() -> dict[str, dict[str, float]]:
    """II.A-17A: PL 1/4 x 11-1/2, 4 x 3/4 in. A325-N, a = 3 in."""
    t, rows, spacing, length = 0.25, 4, 3.0, 11.5
    lev, leh, a = 1.25, 1.5, 3.0
    Fy, Fu = 50.0, 65.0
    beam_tw, beam_Fu = 0.380, 65.0
    bolts = [(0.0, spacing * i) for i in range(rows)]
    coefficient = icr_coefficient(bolts, a / 2.0)
    out = {}
    for lrfd in (True, False):
        shear = bolt_shear(BOLT_D, BOLT_FNV, 1, lrfd)
        edge = bearing_tearout(BOLT_D, t, Fu, lev - HOLE / 2.0, lrfd)
        inner = bearing_tearout(BOLT_D, t, Fu, spacing - HOLE, lrfd)
        web = bearing_tearout(BOLT_D, beam_tw, beam_Fu, spacing - HOLE, lrfd)
        total = (rows - 1) * min(shear, inner, web) + min(shear, edge, web)
        Agv = (length - lev) * t
        Anv = Agv - (rows - 0.5) * NET_HOLE * t
        Ant = (leh - 0.5 * NET_HOLE) * t
        out["LRFD" if lrfd else "ASD"] = {
            "C": coefficient,
            "bolts": coefficient / rows * total,
            "shear_yielding": shear_yielding(length * t, Fy, lrfd),
            "shear_rupture": shear_rupture((length - rows * NET_HOLE) * t, Fu, lrfd),
            "block_shear": block_shear(Agv, Anv, Ant, Fy, Fu, lrfd),
        }
    return out


PUBLISHED = {
    "II.A-1A": {
        "LRFD": {"bolts_beam": 282.0, "bolts_support": 282.0,
                 "angle_shear_yielding": 441.0, "angle_shear_rupture": 302.0,
                 "block_shear_beam": 315.0},
        "ASD": {"bolts_beam": 187.0, "bolts_support": 187.0,
                "angle_shear_yielding": 294.0, "angle_shear_rupture": 201.0,
                "block_shear_beam": 210.0},
    },
    "II.A-17A": {
        "LRFD": {"bolts": 58.5, "shear_yielding": 86.4, "shear_rupture": 58.5,
                 "block_shear": 65.3},
        "ASD": {"bolts": 38.9, "shear_yielding": 57.6, "shear_rupture": 39.0,
                "block_shear": 43.6},
    },
}


def main() -> int:
    print("II.A-1A  2L5x3-1/2x5/16, 8 x 3/4 in. A325-N, l = 23-1/2 in.")
    for method, values in double_angle_ii_a_1a().items():
        print(f"  {method}: " + ", ".join(f"{key} = {value:6.2f}"
                                         for key, value in values.items()))
    print("\nII.A-17A  PL 1/4 x 11-1/2, 4 x 3/4 in. A325-N, a = 3 in.")
    for method, values in single_plate_ii_a_17a().items():
        print(f"  {method}: " + ", ".join(f"{key} = {value:6.3f}"
                                         for key, value in values.items()))
    return 0


def check() -> int:
    failures = []
    cases = (
        ("II.A-1A", double_angle_ii_a_1a()),
        ("II.A-17A", single_plate_ii_a_17a()),
    )
    for example, computed in cases:
        for method, published in PUBLISHED[example].items():
            for key, target in published.items():
                value = computed[method][key]
                if abs(value - target) / target > 0.01:
                    failures.append(f"{example} {method} {key}: {value:.2f} vs {target:.2f}")
    if failures:
        print("FAIL")
        for failure in failures:
            print(f"  {failure}")
        return 1
    print("OK: 18 independent values within 1 % of the published examples.")
    return 0


if __name__ == "__main__":
    raise SystemExit(check() if "--check" in sys.argv else main())
