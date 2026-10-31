# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Bolt group coefficients C against AISC Manual 16th ed., Table 7-6 (one vertical row).

Values transcribed from the table provided by the user. Tolerance: the table
rounds to three significant figures (two decimals for small values).
"""

import math

import pytest

from openconex.kernel.bolt_group import _bolt_response, icr_coefficient

N = range(2, 13)

# Angle = 0°, s = 3 in.: {ex: [C for n = 2..12]}
ANGLE_0_S3 = {
    1: [1.63, 2.71, 3.75, 4.77, 5.77, 6.77, 7.76, 8.75, 9.74, 10.7, 11.7],
    2: [1.18, 2.23, 3.32, 4.39, 5.45, 6.48, 7.51, 8.52, 9.53, 10.5, 11.5],
    3: [0.88, 1.75, 2.81, 3.90, 4.98, 6.06, 7.12, 8.17, 9.21, 10.2, 11.3],
    4: [0.69, 1.40, 2.36, 3.40, 4.47, 5.56, 6.64, 7.72, 8.78, 9.84, 10.9],
    6: [0.48, 0.97, 1.73, 2.59, 3.55, 4.57, 5.63, 6.70, 7.79, 8.87, 9.96],
    8: [0.36, 0.73, 1.34, 2.04, 2.85, 3.75, 4.72, 5.73, 6.78, 7.85, 8.93],
    12: [0.24, 0.49, 0.92, 1.40, 2.00, 2.68, 3.44, 4.27, 5.15, 6.09, 7.06],
    16: [0.18, 0.37, 0.70, 1.06, 1.53, 2.06, 2.67, 3.33, 4.06, 4.85, 5.68],
    24: [0.12, 0.25, 0.47, 0.71, 1.03, 1.40, 1.82, 2.29, 2.81, 3.37, 3.99],
    36: [0.08, 0.16, 0.31, 0.48, 0.69, 0.94, 1.22, 1.54, 1.90, 2.29, 2.72],
}
# Angle = 0°, s = 6 in.
ANGLE_0_S6 = {
    2: [1.63, 2.71, 3.75, 4.77, 5.77, 6.77, 7.76, 8.75, 9.74, 10.7, 11.7],
    6: [0.88, 1.75, 2.81, 3.90, 4.98, 6.06, 7.12, 8.17, 9.21, 10.2, 11.3],
    12: [0.48, 0.97, 1.73, 2.59, 3.55, 4.57, 5.63, 6.70, 7.79, 8.87, 9.96],
    24: [0.24, 0.49, 0.92, 1.40, 2.00, 2.68, 3.44, 4.27, 5.15, 6.09, 7.06],
}
# Inclined loads, s = 3 in.: {(angle, ex): [C for n = 2..12]}
INCLINED_S3 = {
    (15, 2): [1.15, 2.20, 3.28, 4.34, 5.39, 6.42, 7.45, 8.46, 9.47, 10.5, 11.5],
    (15, 12): [0.24, 0.51, 0.93, 1.43, 2.03, 2.71, 3.46, 4.28, 5.15, 6.06, 7.01],
    (30, 2): [1.14, 2.20, 3.25, 4.30, 5.33, 6.36, 7.38, 8.39, 9.40, 10.4, 11.4],
    (30, 12): [0.26, 0.56, 1.01, 1.55, 2.17, 2.87, 3.64, 4.46, 5.33, 6.24, 7.17],
    (45, 2): [1.17, 2.23, 3.26, 4.28, 5.29, 6.30, 7.31, 8.32, 9.32, 10.3, 11.3],
    (45, 12): [0.31, 0.68, 1.17, 1.79, 2.47, 3.22, 4.02, 4.87, 5.74, 6.65, 7.58],
    (60, 2): [1.27, 2.32, 3.32, 4.31, 5.30, 6.30, 7.29, 8.27, 9.27, 10.3, 11.3],
    (60, 12): [0.40, 0.93, 1.52, 2.22, 3.00, 3.82, 4.67, 5.55, 6.45, 7.37, 8.30],
}
# C' (pure moment, in.) for angle 0°
C_PRIME = {3: [2.94, 5.89, 11.3, 17.1, 25.1, 33.8, 44.4, 55.9, 69.2, 83.5, 100],
           6: [5.89, 11.8, 22.5, 34.3, 50.2, 67.6, 88.8, 112, 138, 167, 199]}


def _row(n, s):
    return [(0.0, s * i) for i in range(n)], s * (n - 1) / 2


def _close(value, table):
    return math.isclose(value, table, rel_tol=0.01, abs_tol=0.005)


def _check(table, s, angle_of):
    failures = []
    for key, row in table.items():
        angle, ex = angle_of(key)
        for n, expected in zip(N, row, strict=True):
            bolts, cy = _row(n, s)
            c = icr_coefficient(bolts, (ex, cy), angle=angle).C
            if not _close(c, expected):
                failures.append(f"angle={angle} ex={ex} n={n}: {c:.3f} vs {expected}")
    assert not failures, "\n".join(failures)


def test_angle_0_s3():
    _check(ANGLE_0_S3, 3.0, lambda ex: (0, ex))


def test_angle_0_s6():
    _check(ANGLE_0_S6, 6.0, lambda ex: (0, ex))


@pytest.mark.parametrize("sign", [1, -1])
def test_inclined_loads_s3(sign):
    _check(INCLINED_S3, 3.0, lambda key: (sign * key[0], key[1]))


@pytest.mark.parametrize("s", [3.0, 6.0])
def test_pure_moment_c_prime(s):
    for n, expected in zip(N, C_PRIME[int(s)], strict=True):
        bolts, cy = _row(n, s)
        dist = [abs(y - cy) for _, y in bolts]
        mp = sum(_bolt_response(d, max(dist)) * d for d in dist)
        assert _close(mp, expected), (n, mp, expected)
