# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Complete base plate check per load combination."""

import pytest

from openconex.connections.base_plate.check import BasePlate, check_base_plate, check_envelope
from openconex.core.loads import Forces, LoadCase, LoadType, Method, asce7_combinations
from openconex.core.model import BoltSpec, IShape
from openconex.units import Kind, to_internal


def inch(v):
    return to_internal(v, "in", Kind.LENGTH)


def kip(v):
    return to_internal(v, "kip", Kind.FORCE)


def kip_in(v):
    return to_internal(v, "kip*in", Kind.MOMENT)


W18X76 = IShape(name="W18X76", d=inch(18.2), bf=inch(11.0), tf=inch(0.68), tw=inch(0.425),
                k_des=inch(1.08))
PLATE = BasePlate(column=W18X76, N=inch(28), B=inch(12), tp=inch(1.5),
                  fc=to_internal(4, "ksi", Kind.STRESS),
                  rod=BoltSpec(diameter=inch(1), grade="ASTM F1554 Gr. 36"), f=inch(12),
                  rods_per_side=2, rod_spacing=inch(6), hef=inch(12), A2_over_A1=4.0,
                  flange_weld=inch(0.25))


def by_id(results):
    return {r.id: r for r in results}


def test_dg1_4_7_9_ratios():
    """Same ratios as AISC DG1 Example 4.7-9 (moment only, LRFD)."""
    r = by_id(check_base_plate(PLATE, Forces(M3=kip_in(1200)), Method.LRFD))
    assert r["base_plate.thickness_compression"].ratio == pytest.approx(1.31 / 1.5, rel=0.01)
    assert r["base_plate.thickness_tension"].ratio == pytest.approx(1.06 / 1.5, rel=0.01)
    assert r["anchor.steel_tension"].ratio == pytest.approx(23.5 / 26.3, rel=0.01)
    assert r["anchor.concrete_breakout_tension"].ratio == pytest.approx(47.0 / 51.7, rel=0.01)
    assert r["anchor.pullout"].ratio == pytest.approx(23.5 / 33.6, rel=0.01)
    assert r["weld.strength"].ratio == pytest.approx(65.9 / 92.3, rel=0.01)
    assert all(x.status == "ok" for x in r.values())


def test_axial_compression_only():
    r = by_id(check_base_plate(PLATE, Forces(P=kip(300)), Method.LRFD))
    assert set(r) == {"base_plate.bearing", "base_plate.thickness_compression"}


def test_asd_uses_aisc_rod_checks():
    r = by_id(check_base_plate(PLATE, Forces(M3=kip_in(816), V2=kip(10)), Method.ASD))
    assert "bolt.tension" in r and "bolt.shear" in r
    assert not any(k.startswith("anchor.") for k in r)


def test_shear_by_friction_with_compression():
    r = by_id(check_base_plate(PLATE, Forces(P=kip(200), V2=kip(20)), Method.LRFD))
    assert "base_plate.friction" in r and r["base_plate.friction"].status == "ok"


def test_too_small_plate_is_reported():
    r = by_id(check_base_plate(PLATE, Forces(P=kip(50), M3=kip_in(30000)), Method.LRFD))
    assert r["base_plate.bearing"].status == "ng"


def test_envelope_over_asce7_combinations():
    cases = [LoadCase(name="D", type=LoadType.DEAD), LoadCase(name="W", type=LoadType.WIND)]
    forces = {"D": Forces(P=kip(50)), "W": Forces(P=kip(-20), M3=kip_in(600), V2=kip(8))}
    combos = asce7_combinations(cases)
    results, worst = check_envelope(PLATE, combos, forces)
    assert {r.combo for r in results} == {c.name for c in combos}
    assert worst.ratio == max(r.ratio for r in results)
