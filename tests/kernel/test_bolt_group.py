# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
import math

import pytest

from openconex.core.loads import Method
from openconex.kernel.bolt_group import (
    _bolt_response,
    _residual,
    bolt_group_eccentric,
    elastic_coefficient,
    icr_coefficient,
)


def grid(rows, cols=1, s=3.0, g=3.0):
    return [(c * g, r * s) for r in range(rows) for c in range(cols)]


@pytest.mark.parametrize(("rows", "cols"), [(3, 1), (4, 2), (6, 2), (2, 3)])
@pytest.mark.parametrize("e", [1.0, 3.0, 6.0, 12.0])
def test_icr_bounds_and_equilibrium(rows, cols, e):
    bolts = grid(rows, cols)
    cx = sum(x for x, _ in bolts) / len(bolts)
    load = (cx + e, 0.0)
    res = icr_coefficient(bolts, load)
    f1, f2, _ = _residual(res.icr, bolts, load, (0.0, -1.0))
    assert math.hypot(f1, f2) < 1e-8
    # The elastic method is normally the lower value. In the ICR method the critical
    # bolt only reaches (1 - e^-3.4)^0.55 = 0.98 Rult at Delta_max, so for a few bolts
    # with a large eccentricity the elastic value can be up to ~2 % higher.
    assert elastic_coefficient(bolts, load) <= res.C / 0.98
    assert res.C < len(bolts)


def test_concentric_load_uses_all_bolts():
    bolts = grid(4, 2)
    assert icr_coefficient(bolts, (1.5, 0.0)).C == 4 * 2
    assert elastic_coefficient(bolts, (1.5, 0.0)) == pytest.approx(8.0)


def test_coefficient_decreases_with_eccentricity():
    bolts = grid(4, 2)
    values = [icr_coefficient(bolts, (1.5 + e, 0.0)).C for e in (2, 4, 8, 16, 32)]
    assert values == sorted(values, reverse=True)


def test_large_eccentricity_tends_to_pure_moment():
    """For e -> infinity the ICR tends to the centroid: C e -> sum(R_i d_i)."""
    bolts = grid(4, 2)
    cx, cy = 1.5, 4.5
    dist = [math.hypot(x - cx, y - cy) for x, y in bolts]
    mp = sum(_bolt_response(d, max(dist)) * d for d in dist)
    e = 5000.0
    assert icr_coefficient(bolts, (cx + e, 0.0)).C * e == pytest.approx(mp, rel=0.01)


def test_symmetry_of_load_direction():
    bolts = grid(3, 2)
    up = icr_coefficient(bolts, (1.5 + 5, 0.0), angle=180).C
    down = icr_coefficient(bolts, (1.5 + 5, 0.0), angle=0).C
    left = icr_coefficient(bolts, (1.5 + 5, 0.0), angle=0).C
    assert up == pytest.approx(down, rel=1e-6)
    assert left == pytest.approx(down)


def test_inclined_load_converges():
    bolts = grid(4, 2)
    for angle in (15, 45, 75):
        res = icr_coefficient(bolts, (1.5 + 6, 4.5), angle=angle)
        assert 0 < res.C < 8


def test_elastic_two_bolts_hand_calc():
    """Two bolts 6 in. apart, vertical load at e = 3 in.: forces from direct shear and torsion."""
    bolts = [(0.0, 0.0), (0.0, 6.0)]
    # Ip = 2 * 3^2 = 18; M = 3; horizontal component M*y/Ip = 3*3/18 = 0.5; direct 0.5
    expected = 1 / math.hypot(0.5, 0.5)
    assert elastic_coefficient(bolts, (3.0, 3.0)) == pytest.approx(expected)


def test_group_check():
    bolts = grid(3, 1)
    r = bolt_group_eccentric(bolts, (3.0, 0.0), bolt_strength=1000.0, demand=1500.0,
                             method=Method.LRFD)
    coef = icr_coefficient(bolts, (3.0, 0.0)).C
    assert r.capacity == pytest.approx(1000.0 * coef)
    elastic = bolt_group_eccentric(bolts, (3.0, 0.0), 1000.0, 1500.0, Method.LRFD, use_icr=False)
    assert elastic.capacity <= r.capacity
