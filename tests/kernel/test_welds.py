# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Weld checks against AISC values and AISC Design Guide 1 examples."""

import pytest

from openconex.core.loads import Method
from openconex.core.model import FilletWeld
from openconex.kernel.welds import (
    directional_factor,
    fillet_effective_length,
    fillet_size_checks,
    fillet_weld,
    fillet_weld_group_concentric,
    fillet_weld_per_length,
    pjp_weld,
)
from openconex.units import Kind, from_internal, to_internal

LRFD, ASD = Method.LRFD, Method.ASD
E70 = to_internal(70, "ksi", Kind.STRESS)


def inch(v):
    return to_internal(v, "in", Kind.LENGTH)


def kips(v):
    return from_internal(v, Kind.FORCE, "kip")


def kip_in(v):
    return from_internal(v, Kind.FORCE_PER_LENGTH, "kip/in")


def test_one_sixteenth_e70():
    """The classic 1.392 kip/in. per sixteenth of fillet weld (E70, LRFD, theta = 0)."""
    r = fillet_weld_per_length(inch(1 / 16), E70, 0.0, LRFD)
    assert kip_in(r.capacity) == pytest.approx(1.392, rel=0.001)
    assert kip_in(fillet_weld_per_length(inch(1 / 16), E70, 0.0, ASD).capacity) == \
        pytest.approx(0.928, rel=0.001)


def test_directional_factor():
    assert directional_factor(0) == 1.0
    assert directional_factor(90) == pytest.approx(1.5)
    assert directional_factor(45) == pytest.approx(1 + 0.5 * 0.5**0.75)


@pytest.mark.parametrize(
    ("size", "theta", "rn", "phi_rn", "rn_omega"),
    [
        (3 / 16, 90, 8.35, 6.26, 4.18),  # DG1 4.7-3, web weld for anchor rod tension
        (5 / 16, 90, 13.9, 10.4, 6.95),  # DG1 4.7-5, shear lug weld
        (3 / 16, 0, 5.57, 4.18, 2.79),  # DG1 4.7-5, column web weld for shear
    ],
)
def test_weld_per_length_dg1(size, theta, rn, phi_rn, rn_omega):
    lrfd = fillet_weld_per_length(inch(size), E70, 0.0, LRFD, theta)
    assert kip_in(lrfd.steps[-2].value) == pytest.approx(rn, rel=0.005)
    assert kip_in(lrfd.capacity) == pytest.approx(phi_rn, rel=0.005)
    assert kip_in(fillet_weld_per_length(inch(size), E70, 0.0, ASD, theta).capacity) == \
        pytest.approx(rn_omega, rel=0.005)


def test_weld_total_dg1_4_7_8():
    """DG1 4.7-8: two 3/16 in. welds, 20 in. long, longitudinal: Rn = 223 kips."""
    weld = FilletWeld(size=inch(3 / 16), length=inch(40.0))
    assert kips(fillet_weld(weld, 0.0, LRFD).capacity) == pytest.approx(167, rel=0.005)
    assert kips(fillet_weld(weld, 0.0, ASD).capacity) == pytest.approx(112, rel=0.01)


def test_weld_total_dg1_4_7_7():
    """DG1 4.7-7: 1/4 in. welds, 48 in. effective, transverse: 401 / 268 kips."""
    weld = FilletWeld(size=inch(0.25), length=inch(48.0))
    assert kips(fillet_weld(weld, 0.0, LRFD, theta=90).capacity) == pytest.approx(401, rel=0.005)
    assert kips(fillet_weld(weld, 0.0, ASD, theta=90).capacity) == pytest.approx(268, rel=0.005)


def test_end_loaded_length_reduction():
    w = inch(0.25)
    assert fillet_effective_length(w, 100 * w, end_loaded=True) == pytest.approx(100 * w)
    assert fillet_effective_length(w, 200 * w, end_loaded=True) == pytest.approx(200 * w * 0.8)
    assert fillet_effective_length(w, 400 * w, end_loaded=True) == pytest.approx(180 * w)
    assert fillet_effective_length(w, 400 * w, end_loaded=False) == pytest.approx(400 * w)


def test_concentric_group_j2_4b():
    w = inch(0.25)
    r = fillet_weld_group_concentric(w, E70, inch(10), inch(5), 0.0, LRFD)
    unit = 0.6 * E70 * w / 2**0.5
    rl, rt = unit * inch(10), unit * inch(5)
    assert r.steps[-2].value == pytest.approx(max(rl + rt, 0.85 * rl + 1.5 * rt))


def test_size_checks():
    res = {r.id: r for r in fillet_size_checks(inch(3 / 16), inch(4), inch(0.5), inch(0.5))}
    assert from_internal(res["weld.min_size"].demand, Kind.LENGTH, "in") == pytest.approx(3 / 16)
    assert from_internal(res["weld.max_size"].capacity, Kind.LENGTH, "in") == \
        pytest.approx(7 / 16)
    assert all(r.status == "ok" for r in res.values())
    small = {r.id: r for r in fillet_size_checks(inch(1 / 8), inch(0.4), inch(1.0))}
    assert small["weld.min_size"].status == "ng"  # 5/16 in. required
    assert small["weld.min_length"].status == "ng"


def test_pjp_factors():
    args = (inch(0.25), inch(10), E70, 0.0)
    tension = pjp_weld(*args, LRFD, tension_normal=True).capacity
    shear = pjp_weld(*args, LRFD, tension_normal=False).capacity
    assert tension / shear == pytest.approx(0.80 / 0.75)
