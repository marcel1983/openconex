# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Connecting element checks (AISC 360-22 §J4) against DG1 examples and Manual values."""

import pytest

from openconex.core.loads import Method
from openconex.kernel.elements import (
    block_shear,
    compression,
    effective_net_area,
    flexural_rupture,
    flexural_yielding,
    net_area,
    shear_rupture,
    shear_yielding,
    tension_rupture,
    tension_yielding,
)
from openconex.units import Kind, from_internal, to_internal

LRFD, ASD = Method.LRFD, Method.ASD


def inch(v, power=1):
    unit = "in" if power == 1 else f"in**{power}"
    kind = {1: Kind.LENGTH, 2: Kind.AREA, 3: Kind.SECTION_MODULUS}[power]
    return to_internal(v, unit, kind)


def ksi(v):
    return to_internal(v, "ksi", Kind.STRESS)


def kips(v):
    return from_internal(v, Kind.FORCE, "kip")


def kip_in(v):
    return from_internal(v, Kind.MOMENT, "kip*in")


FY, FU = ksi(50), ksi(65)


def test_shear_lug_dg1_4_7_5():
    """DG1 4.7-5: 8 in. x 1 in. Gr. 50 shear lug."""
    a = inch(8.0, 2)
    assert kips(shear_yielding(a, FY, 0.0, LRFD).capacity) == pytest.approx(240, rel=0.005)
    assert kips(shear_yielding(a, FY, 0.0, ASD).capacity) == pytest.approx(160, rel=0.005)
    assert kips(shear_rupture(a, FU, 0.0, LRFD).capacity) == pytest.approx(234, rel=0.005)
    assert kips(shear_rupture(a, FU, 0.0, ASD).capacity) == pytest.approx(156, rel=0.005)
    z = inch(2.0, 3)  # 8 x 1^2 / 4
    assert kip_in(flexural_yielding(z, FY, 0.0, LRFD).capacity) == pytest.approx(90.0, rel=0.005)
    assert kip_in(flexural_yielding(z, FY, 0.0, ASD).capacity) == pytest.approx(59.9, rel=0.005)
    assert kip_in(flexural_rupture(z, FU, 0.0, LRFD).capacity) == pytest.approx(97.5, rel=0.005)
    assert kip_in(flexural_rupture(z, FU, 0.0, ASD).capacity) == pytest.approx(65.0, rel=0.005)


def test_web_shear_rupture_dg1_4_7_8():
    """DG1 4.7-8: 0.60(65)(0.500)(20.0) = 390 kips; 293 / 195 kips."""
    a = inch(10.0, 2)
    r = shear_rupture(a, FU, to_internal(127, "kip", Kind.FORCE), LRFD)
    assert kips(r.steps[0].value) == pytest.approx(390, rel=0.005)
    assert kips(r.capacity) == pytest.approx(293, rel=0.005)
    assert r.status == "ok"


def test_plate_flexure_dg1_4_7_7():
    """DG1 4.7-7: b_e = 6 in., t = 1.75 in.: Mn = 230 kip-in."""
    z = inch(6.0 * 1.75**2 / 4, 3)
    assert kip_in(flexural_yielding(z, FY, 0.0, LRFD).capacity) == pytest.approx(207, rel=0.005)
    assert kip_in(flexural_yielding(z, FY, 0.0, ASD).capacity) == pytest.approx(138, rel=0.005)


def test_tension_plate():
    ag = inch(3.0, 2)  # PL 1/2 x 6, A36
    assert kips(tension_yielding(ag, ksi(36), 0.0, LRFD).capacity) == pytest.approx(97.2)
    an = net_area(ag, inch(0.5), holes=2, hole_width=inch(13 / 16))
    assert from_internal(an, Kind.AREA, "in**2") == pytest.approx(3.0 - 2 * 0.875 * 0.5)
    ae = effective_net_area(an, Ag=ag, bolted_splice_plate=True)
    assert ae == pytest.approx(min(an, 0.85 * ag))
    assert kips(tension_rupture(ae, ksi(58), 0.0, LRFD).capacity) == \
        pytest.approx(0.75 * 58 * 2.125)


def test_stagger_adds_s2_over_4g():
    base = net_area(inch(4, 2), inch(0.5), 2, inch(13 / 16))
    staggered = net_area(inch(4, 2), inch(0.5), 2, inch(13 / 16), stagger=[(inch(2), inch(3))])
    assert from_internal(staggered - base, Kind.AREA, "in**2") == pytest.approx(4 / 12 * 0.5)


def test_block_shear_takes_lower_value():
    agv, anv, ant = inch(4.5, 2), inch(3.0, 2), inch(0.7, 2)
    r = block_shear(agv, anv, ant, ksi(36), ksi(58), 0.0, LRFD)
    rupture = 0.6 * 58 * 3.0 + 58 * 0.7
    yielding = 0.6 * 36 * 4.5 + 58 * 0.7
    assert kips(r.capacity) == pytest.approx(0.75 * min(rupture, yielding))
    half = block_shear(agv, anv, ant, ksi(36), ksi(58), 0.0, LRFD, Ubs=0.5)
    assert half.capacity < r.capacity


def test_compression():
    ag = inch(4.0, 2)
    short = compression(ag, FY, 20, 0.0, LRFD)
    assert kips(short.capacity) == pytest.approx(0.9 * 50 * 4.0)
    # Manual Table 4-14: phi Fcr = 37.5 ksi for Lc/r = 50, Fy = 50 ksi
    slender = compression(ag, FY, 50, 0.0, LRFD)
    assert kips(slender.capacity) / 4.0 == pytest.approx(37.5, rel=0.002)
    elastic = compression(ag, FY, 150, 0.0, LRFD)
    assert kips(elastic.capacity) / 4.0 == pytest.approx(10.0, rel=0.01)  # Table 4-14
