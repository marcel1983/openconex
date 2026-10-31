# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Weld group coefficients C against AISC Manual 16th ed., Tables 8-4 and 8-5.

Rn = C C1 D l with D in sixteenths of an inch and l in inches, so C is the
nominal strength per sixteenth and per inch of characteristic length (E70XX,
C1 = 1). Values transcribed from the tables provided by the user; the tables
round to three significant figures. For k = 0 the two lines coincide.
"""

import math

import pytest

from openconex.kernel.weld_group import WeldLine, icr_strength

K = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0]
L = 10.0  # in.; C does not depend on l

# Table 8-4, two vertical lines of length l, kl apart: {angle: {a: [C for k]}}
TABLE_8_4 = {
    0: {
        0.0: [3.71] * 16,
        0.1: [3.72, 3.72, 3.72, 3.71, 3.70, 3.69, 3.67, 3.65, 3.63, 3.61, 3.59, 3.55, 3.52, 3.48,
              3.44, 3.43],
        0.2: [3.51, 3.51, 3.50, 3.49, 3.47, 3.46, 3.44, 3.42, 3.41, 3.39, 3.38, 3.35, 3.32, 3.30,
              3.27, 3.25],
        0.3: [3.09, 3.09, 3.10, 3.10, 3.10, 3.10, 3.11, 3.11, 3.11, 3.11, 3.11, 3.11, 3.10, 3.09,
              3.08, 3.07],
        0.5: [2.30, 2.30, 2.32, 2.36, 2.40, 2.44, 2.48, 2.52, 2.55, 2.58, 2.60, 2.65, 2.68, 2.70,
              2.72, 2.73],
        1.0: [1.28, 1.29, 1.32, 1.37, 1.43, 1.49, 1.56, 1.62, 1.67, 1.72, 1.77, 1.86, 1.93, 2.00,
              2.05, 2.10],
        2.0: [0.655, 0.663, 0.688, 0.724, 0.768, 0.817, 0.867, 0.916, 0.964, 1.01, 1.06, 1.14,
              1.22, 1.28, 1.35, 1.40],
        3.0: [0.439, 0.445, 0.463, 0.489, 0.521, 0.557, 0.594, 0.632, 0.670, 0.708, 0.745, 0.815,
              0.880, 0.940, 0.996, 1.05],
    },
    45: {
        0.0: [4.82] * 16,
        0.2: [3.92, 3.92, 3.94, 3.96, 3.99, 4.03, 4.08, 4.13, 4.18, 4.22, 4.26, 4.33, 4.38, 4.43,
              4.47, 4.50],
        0.5: [2.75, 2.76, 2.79, 2.83, 2.89, 2.96, 3.03, 3.10, 3.17, 3.24, 3.29, 3.39, 3.48, 3.56,
              3.64, 3.72],
        1.0: [1.68, 1.69, 1.73, 1.79, 1.87, 1.95, 2.04, 2.12, 2.20, 2.28, 2.36, 2.49, 2.61, 2.72,
              2.81, 2.89],
        2.0: [0.902, 0.911, 0.944, 0.993, 1.05, 1.12, 1.19, 1.26, 1.32, 1.39, 1.46, 1.58, 1.69,
              1.80, 1.90, 1.99],
        3.0: [0.611, 0.619, 0.644, 0.680, 0.723, 0.772, 0.825, 0.879, 0.932, 0.986, 1.04, 1.14,
              1.24, 1.33, 1.42, 1.50],
    },
    75: {
        0.0: [5.47] * 16,
        0.5: [4.09, 4.11, 4.17, 4.27, 4.43, 4.60, 4.76, 4.89, 5.00, 5.09, 5.16, 5.25, 5.32, 5.35,
              5.38, 5.40],
        1.0: [3.18, 3.20, 3.27, 3.37, 3.50, 3.65, 3.83, 4.01, 4.19, 4.35, 4.49, 4.73, 4.90, 5.02,
              5.11, 5.18],
        2.0: [2.09, 2.11, 2.18, 2.27, 2.39, 2.52, 2.66, 2.80, 2.95, 3.10, 3.26, 3.57, 3.86, 4.10,
              4.31, 4.48],
        3.0: [1.52, 1.54, 1.60, 1.68, 1.77, 1.88, 2.00, 2.12, 2.24, 2.37, 2.49, 2.75, 3.01, 3.26,
              3.49, 3.71],
    },
}

# Table 8-5, two horizontal lines of length l, kl apart
TABLE_8_5 = {
    0: {
        0.0: [5.57] * 16,
        0.1: [4.32, 4.36, 4.48, 4.65, 4.82, 4.97, 5.11, 5.21, 5.29, 5.35, 5.39, 5.45, 5.48, 5.50,
              5.52, 5.53],
        0.2: [3.54, 3.57, 3.67, 3.81, 3.99, 4.20, 4.40, 4.57, 4.73, 4.86, 4.97, 5.13, 5.24, 5.32,
              5.37, 5.41],
        0.5: [2.14, 2.17, 2.24, 2.34, 2.47, 2.62, 2.78, 2.95, 3.15, 3.35, 3.54, 3.88, 4.16, 4.39,
              4.58, 4.73],
        1.0: [1.22, 1.24, 1.29, 1.36, 1.44, 1.54, 1.64, 1.75, 1.87, 1.99, 2.12, 2.39, 2.69, 2.97,
              3.22, 3.45],
        2.0: [0.643, 0.653, 0.680, 0.719, 0.767, 0.822, 0.881, 0.945, 1.01, 1.08, 1.15, 1.30,
              1.45, 1.61, 1.77, 1.95],
        3.0: [0.434, 0.441, 0.459, 0.486, 0.519, 0.557, 0.598, 0.642, 0.688, 0.736, 0.785, 0.886,
              0.990, 1.10, 1.21, 1.32],
    },
    60: {
        0.0: [4.37] * 16,
        0.5: [3.26, 3.26, 3.27, 3.29, 3.31, 3.34, 3.36, 3.38, 3.40, 3.42, 3.44, 3.48, 3.50, 3.53,
              3.55, 3.57],
        1.0: [2.23, 2.23, 2.26, 2.31, 2.36, 2.43, 2.49, 2.56, 2.61, 2.67, 2.71, 2.80, 2.87, 2.93,
              2.98, 3.03],
        2.0: [1.25, 1.26, 1.30, 1.35, 1.42, 1.49, 1.56, 1.63, 1.70, 1.77, 1.83, 1.94, 2.04, 2.13,
              2.21, 2.28],
        3.0: [0.858, 0.866, 0.897, 0.942, 0.996, 1.06, 1.12, 1.18, 1.24, 1.30, 1.36, 1.46, 1.56,
              1.65, 1.73, 1.81],
    },
}


def _vertical(k, a):
    kl = k * L
    return [WeldLine(0, 0, 0, L), WeldLine(kl, 0, kl, L)], (kl / 2 + a * L, L / 2)


def _horizontal(k, a):
    kl = k * L
    return [WeldLine(0, 0, L, 0), WeldLine(0, kl, L, kl)], (L / 2 + a * L, kl / 2)


def _coefficient(geometry, k, a, angle):
    lines, load_point = geometry(k, a)
    return icr_strength(lines, 1 / 16, 70.0, load_point, angle).Rn / L


def _check(table, geometry, angle):
    failures = []
    for a, row in table[angle].items():
        for k, expected in zip(K, row, strict=True):
            c = _coefficient(geometry, k, a, angle)
            if not math.isclose(c, expected, rel_tol=0.01, abs_tol=0.005):
                failures.append(f"angle={angle} a={a} k={k}: {c:.3f} vs {expected}")
    assert not failures, "\n".join(failures)


@pytest.mark.parametrize("angle", sorted(TABLE_8_4))
def test_table_8_4(angle):
    _check(TABLE_8_4, _vertical, angle)


@pytest.mark.parametrize("angle", sorted(TABLE_8_5))
def test_table_8_5(angle):
    _check(TABLE_8_5, _horizontal, angle)


def test_concentric_parallel_lines_use_directional_increase():
    # §J2.4(b): elements in line or parallel take Fnw = 0.60 FEXX (1 + 0.50 sin^1.5 θ)
    lines, load_point = _vertical(0.5, 0.0)
    rn = icr_strength(lines, 1 / 16, 70.0, load_point, 45).Rn
    throat_area = 2 * L * (1 / 16) / math.sqrt(2)
    assert rn == pytest.approx(0.60 * 70.0 * (1 + 0.5 * math.sin(math.pi / 4) ** 1.5)
                               * throat_area)
