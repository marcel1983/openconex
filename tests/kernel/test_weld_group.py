# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
import math

import pytest

from openconex.core.loads import Method
from openconex.kernel.weld_group import (
    WeldLine,
    _elements,
    _residual,
    elastic_strength,
    electrode_coefficient,
    icr_strength,
    weld_group_eccentric,
)
from openconex.units import Kind, to_internal

W, FEXX = 0.25, 70.0  # in., ksi: results in kips
UNIT = 0.60 * FEXX * W / math.sqrt(2)  # nominal kip/in. without directional increase


def vertical(length, x=0.0):
    return WeldLine(x, 0.0, x, length)


def c_shape(b, d):
    """Two horizontal lines of length b and one vertical line of length d (Manual 'C')."""
    return [WeldLine(0, 0, b, 0), WeldLine(0, 0, 0, d), WeldLine(0, d, b, d)]


def test_concentric_longitudinal_line():
    """A line loaded along its axis develops 0.60 FEXX Awe (J2.4(a), kds = 1)."""
    r = icr_strength([vertical(10)], W, FEXX, (0.0, 5.0), angle=0)
    assert r.Rn == pytest.approx(UNIT * 10, rel=0.01)


def test_concentric_transverse_line():
    """A line loaded perpendicular to its axis develops 1.5 x 0.60 FEXX Awe."""
    r = icr_strength([WeldLine(0, 0, 10, 0)], W, FEXX, (5.0, 0.0), angle=0)
    assert r.Rn == pytest.approx(1.5 * UNIT * 10, rel=0.01)


def test_concentric_mixed_group_uses_j2_6():
    """Longitudinal + transverse lines: the greater of §J2.4(c) and Eq. J2-6 (Manual Table 8-8)."""
    lines = [WeldLine(0, 0, 0, 6), WeldLine(10, 0, 10, 6), WeldLine(0, 0, 10, 0)]
    centroid_y = (3 * 6 + 3 * 6) / 22  # sum(y L) / sum(L)
    r = icr_strength(lines, W, FEXX, (5.0, centroid_y), angle=0)
    rl, rt = UNIT * 12, UNIT * 10
    j2_6 = max(rl + rt, 0.85 * rl + 1.5 * rt)
    assert r.Rn == pytest.approx(j2_6)


@pytest.mark.parametrize("ex", [2.0, 4.0, 8.0, 16.0])
def test_eccentric_equilibrium_and_bounds(ex):
    lines = c_shape(4.0, 10.0)
    elems = _elements(lines, 40)
    cx = 2 * 4.0 * 2.0 / 18  # two 4 in. flanges centred at x = 2 in., total length 18 in.
    load = (cx + ex, 5.0)
    res = icr_strength(lines, W, FEXX, load)
    f1, f2, _ = _residual(res.icr, elems, W, FEXX, load, (0.0, -1.0))
    assert math.hypot(f1, f2) < 1e-6 * res.Rn
    total = UNIT * 1.5 * 18
    assert 0 < res.Rn < total
    assert elastic_strength(lines, W, FEXX, load) <= res.Rn * 1.02


def test_strength_decreases_with_eccentricity():
    lines = c_shape(4.0, 10.0)
    values = [icr_strength(lines, W, FEXX, (1.0 + e, 5.0)).Rn for e in (1, 3, 6, 12, 24)]
    assert values == sorted(values, reverse=True)


def test_check_uses_phi():
    lines = [WeldLine(0, 0, 0, 250)]
    fexx = to_internal(70, "ksi", Kind.STRESS)
    r = weld_group_eccentric(lines, 6.0, fexx, (75.0, 125.0), 0.0, Method.LRFD)
    assert r.capacity == pytest.approx(0.75 * icr_strength(lines, 6.0, fexx, (75.0, 125.0)).Rn)


@pytest.mark.parametrize(("ksi", "c1"), [(60, 0.857), (70, 1.00), (80, 1.03), (90, 1.16),
                                         (100, 1.21), (110, 1.34), (85, 1.095)])
def test_electrode_coefficient_table_8_3(ksi, c1):
    assert electrode_coefficient(to_internal(ksi, "ksi", Kind.STRESS)) == pytest.approx(c1)


def test_electrode_coefficient_outside_table():
    with pytest.raises(ValueError):
        electrode_coefficient(to_internal(120, "ksi", Kind.STRESS))


def test_check_applies_c1_for_e80():
    lines = [WeldLine(0, 0, 0, 250)]
    e70, e80 = (to_internal(v, "ksi", Kind.STRESS) for v in (70, 80))
    r70 = weld_group_eccentric(lines, 6.0, e70, (75.0, 125.0), 0.0, Method.LRFD)
    r80 = weld_group_eccentric(lines, 6.0, e80, (75.0, 125.0), 0.0, Method.LRFD)
    assert r80.capacity == pytest.approx(1.03 * r70.capacity)
