# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Independent check of the AISC seated-connection formulas.

This script deliberately does not import ``openconex``.  It recomputes the
published values of Examples II.A-12A, II.A-13 and II.A-14 from the equations
of the AISC Manual Part 10, so the matrix can point to a calculation that is
independent of the program under test.

Run with::

    python docs/verificacion/calculos/asientos.py

Units are inches and kips throughout.
"""

from __future__ import annotations

import math

PHI_FLEXURE = 0.90
OMEGA_FLEXURE = 1.67
PHI_SHEAR_YIELD = 1.00
OMEGA_SHEAR_YIELD = 1.50
PHI_BOLT_SHEAR = 0.75
OMEGA_BOLT_SHEAR = 2.00
PHI_WEB_YIELD = 1.00
OMEGA_WEB_YIELD = 1.50
PHI_WEB_CRIPPLE = 0.75
OMEGA_WEB_CRIPPLE = 2.00
E = 29_000.0


def available(nominal: float, phi: float, omega: float, lrfd: bool) -> float:
    """Available strength from a nominal strength."""
    return phi * nominal if lrfd else nominal / omega


def bearing_length(beam: dict[str, float], R: float, lrfd: bool) -> dict[str, float]:
    """Manual Eqs. 10-1 to 10-3 (Table 9-4 constants)."""
    tw, tf, d, kdes, Fy = (beam["tw"], beam["tf"], beam["d"], beam["kdes"],
                           beam["Fy"])
    factor = 1.0 / PHI_WEB_YIELD if lrfd else OMEGA_WEB_YIELD
    required = R * factor
    yielding = required / (Fy * tw) - 2.5 * kdes
    root = 0.40 * tw**2 * math.sqrt(E * Fy * tf / tw)
    ratio = required / root - 1.0
    slender = (tf / tw) ** 1.5
    if beam["available"] / d <= 0.2:
        crippling = d / 3.0 * ratio * slender
    else:
        crippling = d / 4.0 * (ratio * slender + 0.2)
    return {"yielding": yielding, "crippling": crippling,
            "minimum": max(yielding, crippling, kdes)}


def seat_flexure(L: float, t: float, Fy: float, setback: float, lb: float,
                 lrfd: bool) -> tuple[float, float]:
    """Manual Part 10: R_n = F_y L t^2 / (4 e_c)."""
    ec = setback + lb / 2.0 - t - 0.375
    mn = Fy * L * t**2 / 4.0
    rn = mn / ec
    return ec, available(rn, PHI_FLEXURE, OMEGA_FLEXURE, lrfd)


def weld_unstiffened(L: float, leg: float, setback: float, D: int,
                     lrfd: bool) -> tuple[float, float]:
    """Manual Eq. 10-2a/10-2b (Table 10-6)."""
    e = setback + (leg - setback) / 2.0
    rw = 1.392 * D if lrfd else 0.928 * D
    rn = 2.0 * rw * L**2 / math.sqrt(L**2 + 20.25 * e**2)
    return e, rn


def weld_stiffened(L: float, W: float, D: int, lrfd: bool) -> tuple[float, float]:
    """Elastic method of Manual Table 10-8."""
    e = 0.8 * W
    rw = 1.392 * D if lrfd else 0.928 * D
    rn = 2.0 * rw * 1.2 * L**2 / math.sqrt(L**2 + 16.0 * e**2)
    return e, rn


def bolt_shear(d: float, Fnv: float, n: int, lrfd: bool) -> float:
    """AISC 360-22 Eq. J3-1, threads included (N)."""
    ab = math.pi * d**2 / 4.0
    rn = Fnv * ab
    return n * available(rn, PHI_BOLT_SHEAR, OMEGA_BOLT_SHEAR, lrfd)


def check() -> int:
    """Compare the independent values with the published tables (1 %)."""
    cases = (
        ("II.A-12A flexure, l_b = 1-1/16 in., LRFD",
         seat_flexure(8.0, 0.625, 36.0, 0.75, 1.0625, True)[1], 90.0),
        ("II.A-12A flexure, l_b = 1-1/16 in., ASD",
         seat_flexure(8.0, 0.625, 36.0, 0.75, 1.0625, False)[1], 59.9),
        ("II.A-13 weld, LRFD", weld_unstiffened(8.0, 4.0, 0.75, 5, True)[1], 66.7),
        ("II.A-13 weld, ASD", weld_unstiffened(8.0, 4.0, 0.75, 5, False)[1], 44.5),
        ("II.A-14 weld, LRFD", weld_stiffened(15.0, 7.0, 5, True)[1], 139.0),
        ("II.A-14 weld, ASD", weld_stiffened(15.0, 7.0, 5, False)[1], 93.0),
    )
    failures = []
    for name, got, expected in cases:
        if abs(got - expected) / expected > 0.01:
            failures.append(f"{name}: {got:.2f} vs {expected:.2f}")
    if failures:
        print("FAIL")
        for failure in failures:
            print(f"  {failure}")
        return 1
    print(f"OK: {len(cases)} independent values within 1 % of the published tables.")
    return 0


def main() -> int:
    beam = {"tw": 0.380, "tf": 0.630, "d": 16.3, "kdes": 1.03, "Fy": 50.0,
            "available": 4.0 - 0.75}
    print("II.A-12A  W16x50 beam, L6x4x5/8 A36 seat, 8 in. long, 4 x 3/4 in. A325-N")
    for lrfd, R, label in ((True, 54.8, "LRFD"), (False, 36.5, "ASD ")):
        bl = bearing_length(beam, R, lrfd)
        print(f"  {label}: R = {R:5.1f} kip, l_b,yield = {bl['yielding']:.3f} in., "
              f"l_b,crip = {bl['crippling']:.3f} in., l_b,min = {bl['minimum']:.3f} in.")
    for lb in (1.03, 1.0625):
        print(f"  Table entry l_b = {lb:.4f} in.")
        for lrfd in (True, False):
            ec, rn = seat_flexure(8.0, 0.625, 36.0, 0.75, lb, lrfd)
            print(f"    {'LRFD' if lrfd else 'ASD '}: e_c = {ec:.4f} in., "
                  f"flexure = {rn:6.2f} kip")
    for lrfd in (True, False):
        shear = 0.60 * 36.0 * 8.0 * 0.625
        shear = available(shear, PHI_SHEAR_YIELD, OMEGA_SHEAR_YIELD, lrfd)
        bolts = bolt_shear(0.75, 54.0, 4, lrfd)
        print(f"  {'LRFD' if lrfd else 'ASD '}: shear yielding = {shear:6.2f} kip, "
              f"bolt shear = {bolts:6.2f} kip")

    print("\nII.A-13  L8x4x5/8 A36 seat, 8 in. long, 5/16 in. E70 fillet welds")
    for lrfd in (True, False):
        e, rn = weld_unstiffened(8.0, 4.0, 0.75, 5, lrfd)
        print(f"  {'LRFD' if lrfd else 'ASD '}: e = {e:.3f} in., weld = {rn:6.2f} kip")

    print("\nII.A-14/15  PL 5/8 x 7 x 15 stiffener, 5/16 in. E70 fillet welds")
    for lrfd in (True, False):
        e, rn = weld_stiffened(15.0, 7.0, 5, lrfd)
        print(f"  {'LRFD' if lrfd else 'ASD '}: e = {e:.3f} in., weld = {rn:6.2f} kip")

    print("\nPublished values: II.A-12A 90.0/59.9 kip at l_b = 1-1/16 in. "
          "(flexure); II.A-13 66.7/44.5 kip; II.A-14 139/93.0 kip.")
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(check() if "--check" in sys.argv else main())
