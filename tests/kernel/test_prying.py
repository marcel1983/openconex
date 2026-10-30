# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
import math

import pytest

from openconex.core.loads import Method
from openconex.kernel.prying import prying_min_thickness, prying_tension
from openconex.units import Kind, to_internal

LRFD, ASD = Method.LRFD, Method.ASD


def inch(v):
    return to_internal(v, "in", Kind.LENGTH)


def kip(v):
    return to_internal(v, "kip", Kind.FORCE)


FU = to_internal(65, "ksi", Kind.STRESS)
GEOM = {"b": inch(1.5), "a": inch(1.5), "p": inch(3.0), "db": inch(0.75), "hole": inch(13 / 16)}


def reference_q(B, t, method):
    """Independent evaluation of Manual Part 9 equations in kip-in units."""
    b, a, p, db, d = 1.5, 1.5, 3.0, 0.75, 13 / 16
    bp, ap = b - db / 2, min(a, 1.25 * b) + db / 2
    rho, delta = bp / ap, 1 - d / p
    k = 1 / 0.9 if method is LRFD else 1.67
    tc = math.sqrt(k * 4 * B * bp / (p * 65))
    alpha = ((tc / t) ** 2 - 1) / (delta * (1 + rho))
    if alpha < 0:
        return 1.0
    return (t / tc) ** 2 * (1 + delta * min(alpha, 1.0))


@pytest.mark.parametrize("method", [LRFD, ASD])
@pytest.mark.parametrize("t", [0.375, 0.5, 0.625, 0.875, 1.5])
def test_matches_manual_equations(method, t):
    B = 29.8 if method is LRFD else 19.9  # 3/4 in. A325 bolt, Table 7-2
    r = prying_tension(kip(B), inch(t), **GEOM, Fu=FU, demand=0.0, method=method)
    q = next(s.value for s in r.steps if s.symbol == "Q")
    assert q == pytest.approx(reference_q(B, t, method), rel=1e-9)
    assert r.capacity == pytest.approx(kip(B) * q)
    assert 0 < q <= 1.0


def test_thick_flange_has_no_prying():
    r = prying_tension(kip(29.8), inch(2.0), **GEOM, Fu=FU, demand=kip(20), method=LRFD)
    assert r.capacity == pytest.approx(kip(29.8))


def test_capacity_grows_with_thickness():
    caps = [prying_tension(kip(29.8), inch(t), **GEOM, Fu=FU, demand=0.0, method=LRFD).capacity
            for t in (0.375, 0.5, 0.625, 0.75)]
    assert caps == sorted(caps)


def test_min_thickness_consistent_with_q():
    """At t = t_min for T = B, the available strength equals B (no prying)."""
    tmin = prying_min_thickness(kip(29.8), inch(1.5), inch(3.0), inch(0.75), FU, inch(1.0), LRFD)
    r = prying_tension(kip(29.8), tmin.demand, **GEOM, Fu=FU, demand=0.0, method=LRFD)
    assert r.capacity == pytest.approx(kip(29.8), rel=1e-6)
    assert tmin.status == "ok"
