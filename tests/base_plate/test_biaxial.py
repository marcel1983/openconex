# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Biaxial bending of base plates (AISC DG1 3rd ed. §4.3.7, Example 4.7-14)."""

import dataclasses
import math

import pytest

from openconex.connections.base_plate.check import BasePlate, check_base_plate
from openconex.core.loads import Forces, Method
from openconex.core.model import BoltSpec, IShape
from openconex.i18n import LANGUAGES, catalog
from openconex.units import Kind, to_internal


def inch(v):
    return to_internal(v, "in", Kind.LENGTH)


def kip(v):
    return to_internal(v, "kip", Kind.FORCE)


def kip_in(v):
    return to_internal(v, "kip*in", Kind.MOMENT)


W8X48 = IShape(name="W8X48", d=inch(8.50), bf=inch(8.11), tf=inch(0.685), tw=inch(0.400),
               k_des=inch(0.937))
# DG1 Example 4.7-14: 14 x 14 x 1¾ in. plate, four 5/8 in. F1554 Gr. 55 rods 1.5 in. from
# the edges, f'c = 4 ksi, A2/A1 = 4
EX_4_7_14 = BasePlate(column=W8X48, N=inch(14), B=inch(14), tp=inch(1.75),
                      fc=to_internal(4, "ksi", Kind.STRESS),
                      rod=BoltSpec(diameter=inch(0.625), grade="ASTM F1554 Gr. 55"),
                      f=inch(5.5), rods_per_side=2, rod_spacing=inch(11), A2_over_A1=4.0)
FORCES = Forces(P=kip(90), M3=kip_in(700), M2=kip_in(450))


def by_id(results):
    return {r.id: r for r in results}


def test_dg1_4_7_14_interaction():
    r = by_id(check_base_plate(EX_4_7_14, FORCES, Method.LRFD, "4.7-14"))
    biaxial = r["base_plate.biaxial"]
    assert biaxial.demand == pytest.approx(0.988, rel=0.01)
    assert biaxial.capacity == 1.0 and biaxial.status.value == "ok"
    steps = {s.symbol: s.value for s in biaxial.steps}
    assert steps["T_{x,cap}"] == pytest.approx(kip(25.4), rel=0.01)
    assert steps["M_{x,cap}"] == pytest.approx(kip_in(837), rel=0.01)
    assert steps["M_{y,cap}"] == pytest.approx(kip_in(837), rel=0.01)
    # each axis also checked separately; e_y = 5.00 in. < e_crit: no tension on the weak axis
    assert {"base_plate.bearing_weak", "base_plate.thickness_compression_weak"} <= set(r)
    assert "base_plate.thickness_tension_weak" not in r


def test_without_weak_moment_nothing_changes():
    uniaxial = check_base_plate(EX_4_7_14, Forces(P=kip(90), M3=kip_in(700)), Method.LRFD)
    assert not any(c.id.endswith("_weak") or c.id == "base_plate.biaxial" for c in uniaxial)


def test_weak_axis_alone_matches_rotated_plate():
    """M2 about a square plate gives the same bearing as M3 on the rotated plate."""
    weak = by_id(check_base_plate(EX_4_7_14, Forces(P=kip(90), M2=kip_in(450)), Method.LRFD))
    strong = by_id(check_base_plate(EX_4_7_14, Forces(P=kip(90), M3=kip_in(450)), Method.LRFD))
    assert weak["base_plate.bearing_weak"].ratio == pytest.approx(
        strong["base_plate.bearing"].ratio)


def test_weak_axis_uses_cantilevers_of_the_rotated_plate():
    """With M2, m is measured against bf and n against d (DG1 §4.3.7)."""
    bp = dataclasses.replace(EX_4_7_14, N=inch(28), B=inch(12), f=inch(12),
                             rod_spacing=inch(6))
    r = by_id(check_base_plate(bp, Forces(P=kip(90), M2=kip_in(450)), Method.LRFD))
    step = next(s for s in r["base_plate.thickness_compression_weak"].steps
                if s.symbol == "l")
    expected = max(inch((12 - 0.95 * 8.11) / 2), inch((28 - 0.8 * 8.50) / 2))
    assert step.value == pytest.approx(expected)


def test_interaction_fails_when_moments_grow():
    big = Forces(P=kip(90), M3=kip_in(800), M2=kip_in(600))
    assert by_id(check_base_plate(EX_4_7_14, big, Method.LRFD))["base_plate.biaxial"].ratio > 1


def test_asd_interaction_uses_rod_strength_of_aisc():
    r = by_id(check_base_plate(EX_4_7_14, Forces(P=kip(60), M3=kip_in(450), M2=kip_in(300)),
                               Method.ASD))
    assert 0 < r["base_plate.biaxial"].ratio < 1


def test_shear_is_the_resultant():
    forces = Forces(P=kip(90), V2=kip(3), V3=kip(4))
    friction = by_id(check_base_plate(EX_4_7_14, forces, Method.LRFD))["base_plate.friction"]
    assert friction.demand == pytest.approx(kip(5))


def test_weak_axis_without_rods_off_the_axis():
    one_row = BasePlate(column=W8X48, N=inch(14), B=inch(14), tp=inch(1.75),
                        fc=to_internal(4, "ksi", Kind.STRESS),
                        rod=BoltSpec(diameter=inch(0.625), grade="ASTM F1554 Gr. 55"),
                        f=inch(5.5), rods_per_side=1, A2_over_A1=4.0)
    small = by_id(check_base_plate(one_row, Forces(P=kip(90), M2=kip_in(100)), Method.LRFD))
    large = by_id(check_base_plate(one_row, Forces(P=kip(90), M2=kip_in(900)), Method.LRFD))
    assert small["base_plate.bearing_weak"].status.value == "ok"
    assert large["base_plate.bearing_weak"].status.value == "ng"
    assert "base_plate.biaxial" not in large


def test_uplift_uses_elastic_biaxial_rod_forces():
    forces = Forces(P=kip(-20), M3=kip_in(50), M2=kip_in(50))
    r = by_id(check_base_plate(EX_4_7_14, forces, Method.LRFD))
    # corner rod: 20/4 + 50·5.5/(4·5.5²) + 50·5.5/(4·5.5²) kips
    corner = kip(5 + 2 * 50 / (4 * 5.5))
    assert r["anchor.steel_tension"].demand == pytest.approx(corner, rel=1e-6)
    assert math.isfinite(r["base_plate.biaxial"].ratio)


@pytest.mark.parametrize("lang", LANGUAGES)
def test_new_checks_have_titles(lang):
    results = check_base_plate(EX_4_7_14, FORCES, Method.LRFD)
    texts = catalog(lang)
    for check in results:
        assert check.text_id in texts, check.text_id
