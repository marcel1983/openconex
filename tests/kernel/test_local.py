# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""AISC 360-22 §J10 checks on a W14x90 (Fy = 50 ksi), evaluated by hand in kip-in."""

import math

import pytest

from openconex.core.loads import Method
from openconex.core.model import IShape
from openconex.kernel.local import (
    flange_local_bending,
    panel_zone_shear,
    web_compression_buckling,
    web_local_crippling,
    web_local_yielding,
)
from openconex.units import Kind, from_internal, to_internal

LRFD, ASD = Method.LRFD, Method.ASD
D, BF, TF, TW, K = 14.0, 14.5, 0.710, 0.440, 1.31
E, FY = 29000.0, 50.0


def inch(v):
    return to_internal(v, "in", Kind.LENGTH)


def kips(v):
    return from_internal(v, Kind.FORCE, "kip")


W14X90 = IShape(name="W14X90", d=inch(D), bf=inch(BF), tf=inch(TF), tw=inch(TW), k_des=inch(K))


def test_flange_local_bending():
    expected = 0.9 * 6.25 * FY * TF**2
    assert kips(flange_local_bending(W14X90, 0.0, LRFD).capacity) == pytest.approx(expected)
    near = flange_local_bending(W14X90, 0.0, LRFD, near_end=True).capacity
    assert kips(near) == pytest.approx(expected / 2)


@pytest.mark.parametrize(("near_end", "factor"), [(False, 5.0), (True, 2.5)])
def test_web_local_yielding(near_end, factor):
    lb = 6.0
    r = web_local_yielding(W14X90, inch(lb), 0.0, LRFD, near_end=near_end)
    assert kips(r.capacity) == pytest.approx(FY * TW * (factor * K + lb))
    asd = web_local_yielding(W14X90, inch(lb), 0.0, ASD, near_end=near_end)
    assert asd.capacity == pytest.approx(r.capacity / 1.5)


@pytest.mark.parametrize(("lb", "near_end"), [(6.0, False), (2.0, True), (6.0, True)])
def test_web_local_crippling(lb, near_end):
    root = math.sqrt(E * FY * TF / TW)
    ratio = (TW / TF) ** 1.5
    if not near_end:
        rn = 0.80 * TW**2 * (1 + 3 * lb / D * ratio) * root
    elif lb / D <= 0.2:
        rn = 0.40 * TW**2 * (1 + 3 * lb / D * ratio) * root
    else:
        rn = 0.40 * TW**2 * (1 + (4 * lb / D - 0.2) * ratio) * root
    r = web_local_crippling(W14X90, inch(lb), 0.0, LRFD, near_end=near_end)
    assert kips(r.capacity) == pytest.approx(0.75 * rn, rel=1e-6)


def test_web_compression_buckling():
    rn = 24 * TW**3 * math.sqrt(E * FY) / (D - 2 * K)
    assert kips(web_compression_buckling(W14X90, 0.0, LRFD).capacity) == \
        pytest.approx(0.9 * rn, rel=1e-6)
    assert kips(web_compression_buckling(W14X90, 0.0, LRFD, near_end=True).capacity) == \
        pytest.approx(0.45 * rn, rel=1e-6)


def test_panel_zone():
    base = 0.60 * FY * D * TW
    py = FY * (2 * BF * TF + (D - 2 * TF) * TW)
    low = panel_zone_shear(W14X90, 0.0, 0.0, LRFD)
    assert kips(low.capacity) == pytest.approx(0.9 * base)
    pr = 0.6 * py
    high = panel_zone_shear(W14X90, to_internal(pr, "kip", Kind.FORCE), 0.0, LRFD)
    assert kips(high.capacity) == pytest.approx(0.9 * base * (1.4 - 0.6), rel=1e-6)
    inel = panel_zone_shear(W14X90, 0.0, 0.0, LRFD, beam_depth=inch(18.0), inelastic=True)
    extra = 1 + 3 * BF * TF**2 / (18.0 * D * TW)
    assert kips(inel.capacity) == pytest.approx(0.9 * base * extra, rel=1e-6)
    with pytest.raises(ValueError):
        panel_zone_shear(W14X90, 0.0, 0.0, LRFD, inelastic=True)
