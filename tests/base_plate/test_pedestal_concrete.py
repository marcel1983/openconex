# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Concrete of the pedestal: edges, A2/A1, shear breakout, pryout and interaction."""

import dataclasses

import pytest

from openconex.connections.base_plate.check import BasePlate, check_base_plate, concrete_edges
from openconex.core.loads import Forces, Method
from openconex.core.model import BoltSpec, IShape
from openconex.kernel.anchors import Edges
from openconex.units import Kind, to_internal


def inch(v):
    return to_internal(v, "in", Kind.LENGTH)


def kip(v):
    return to_internal(v, "kip", Kind.FORCE)


def kip_in(v):
    return to_internal(v, "kip*in", Kind.MOMENT)


W12X96 = IShape(name="W12X96", d=inch(12.7), bf=inch(12.2), tf=inch(0.9), tw=inch(0.55),
                k_des=inch(1.5))
# DG1 Example 4.7-4: four 3/4 in. F1554 Gr. 36 rods on a 4 in. square pattern, f'c = 4 ksi,
# 12 in. to the edge in the direction of the shear, side distances ≥ 1.5 ca1
EX_4_7_4 = BasePlate(column=W12X96, N=inch(14), B=inch(14), tp=inch(1.5),
                     fc=to_internal(4, "ksi", Kind.STRESS),
                     rod=BoltSpec(diameter=inch(0.75), grade="ASTM F1554 Gr. 36"), f=inch(2),
                     rods_per_side=2, rod_spacing=inch(4), hef=inch(12),
                     edges=Edges(left=inch(18), right=inch(18), bottom=inch(12)))


def by_id(results):
    out = {}
    for r in results:
        out.setdefault(r.id, r)
    return out


def test_dg1_4_7_4_shear_breakout_toward_the_edge():
    r = by_id(check_base_plate(EX_4_7_4, Forces(V2=kip(10)), Method.LRFD))
    breakout = r["anchor.concrete_breakout_shear"]
    assert breakout.capacity == pytest.approx(kip(18.4), rel=0.01)
    assert breakout.demand == pytest.approx(kip(10))
    assert {"anchor.pryout", "anchor.steel_shear"} <= set(r)


def test_friction_or_lug_skip_the_rod_shear_checks():
    r = by_id(check_base_plate(EX_4_7_4, Forces(P=kip(100), V2=kip(10)), Method.LRFD))
    assert "base_plate.friction" in r
    assert "anchor.concrete_breakout_shear" not in r and "anchor.pryout" not in r


def test_interaction_with_tension_and_shear():
    r = by_id(check_base_plate(EX_4_7_4, Forces(P=kip(-10), V2=kip(8)), Method.LRFD))
    interaction = r["anchor.interaction"]
    tension = max(r[i].ratio for i in ("anchor.steel_tension", "anchor.pullout",
                                       "anchor.concrete_breakout_tension"))
    shear = max(r[i].ratio for i in ("anchor.steel_shear", "anchor.concrete_breakout_shear",
                                     "anchor.pryout"))
    expected = tension + shear if min(tension, shear) > 0.2 else max(tension, shear)
    assert interaction.demand == pytest.approx(expected)


def test_edges_from_the_pedestal():
    bp = dataclasses.replace(EX_4_7_4, edges=Edges(), pedestal_N=inch(24), pedestal_B=inch(20))
    one_row, both = concrete_edges(bp), concrete_edges(bp, True)
    assert (one_row.left, one_row.right) == (pytest.approx(inch(8)), pytest.approx(inch(8)))
    assert (one_row.bottom, one_row.top) == (pytest.approx(inch(10)), pytest.approx(inch(14)))
    assert both.top == pytest.approx(inch(10))
    assert concrete_edges(EX_4_7_4) is EX_4_7_4.edges  # explicit edges win
    unbounded = dataclasses.replace(EX_4_7_4, edges=Edges())
    assert concrete_edges(unbounded).values() == []


def test_a2_over_a1_limited_by_the_pedestal():
    bp = dataclasses.replace(EX_4_7_4, pedestal_N=inch(21), pedestal_B=inch(21), A2_over_A1=4.0)
    check = by_id(check_base_plate(bp, Forces(P=kip(50)), Method.LRFD))["base_plate.a2_over_a1"]
    assert check.capacity == pytest.approx(1.5**2)
    assert check.status.value == "ng"
    assert "base_plate.a2_over_a1" not in by_id(check_base_plate(EX_4_7_4, Forces(P=kip(50)),
                                                                 Method.LRFD))


def test_side_face_blowout_for_deep_rods_near_an_edge():
    deep = dataclasses.replace(EX_4_7_4, hef=inch(24), edges=Edges(left=inch(3), right=inch(3),
                                                                     bottom=inch(12)))
    r = by_id(check_base_plate(deep, Forces(P=kip(-20)), Method.LRFD))
    assert r["anchor.side_face_blowout"].applicable
    shallow = by_id(check_base_plate(EX_4_7_4, Forces(P=kip(-20)), Method.LRFD))
    assert "anchor.side_face_blowout" not in shallow


def test_uplift_breakout_uses_both_rows():
    bp = dataclasses.replace(EX_4_7_4, edges=Edges())
    r = by_id(check_base_plate(bp, Forces(P=kip(-20)), Method.LRFD))
    area = next(s.value for s in r["anchor.concrete_breakout_tension"].steps
                if s.symbol == "A_{Nc}")
    assert area == pytest.approx((inch(4) + 2 * 1.5 * inch(12)) ** 2)
