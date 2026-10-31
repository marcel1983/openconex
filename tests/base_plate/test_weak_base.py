# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Weak seismic base with ductile anchor rods (DG1 Example 6.4-1)."""

import dataclasses

import pytest

from openconex.connections.base_plate.check import BasePlate, WeakBase, check_base_plate
from openconex.core.loads import Forces, Method
from openconex.core.model import BoltSpec
from openconex.core.shapes import aisc_shapes
from openconex.units import Kind, from_internal, to_internal


def inch(value):
    return to_internal(value, "in", Kind.LENGTH)


def kip(value):
    return to_internal(value, "kip", Kind.FORCE)


def kip_in(value):
    return to_internal(value, "kip*in", Kind.MOMENT)


def in2(value):
    return to_internal(value, "in**2", Kind.AREA)


def by_id(results):
    return {r.id: r for r in results}


def _plate():
    return BasePlate(
        column=aisc_shapes().get("W12X96").to_ishape(),
        N=inch(20), B=inch(20), tp=inch(1.25),
        fc=to_internal(4, "ksi", Kind.STRESS),
        rod=BoltSpec(diameter=inch(1), grade="ASTM F1554 Gr. 55"),
        f=inch(8), rods_per_side=3, rod_spacing=inch(16), hef=inch(24),
        A2_over_A1=4.0, bearing_area=in2(3.21), seismic=True,
        weak_base=WeakBase(reduced_diameter=inch(0.75), stretch_length=inch(8)))


def test_dg1_6_4_1_weak_base():
    r = by_id(check_base_plate(_plate(), Forces(P=kip(376), M3=kip_in(3600)), Method.LRFD))
    assert from_internal(r["base_plate.weak_base_area"].demand, Kind.AREA, "in**2") == \
        pytest.approx(0.325, rel=0.02)
    assert from_internal(r["base_plate.weak_base_stretch"].demand, Kind.LENGTH, "in") == \
        pytest.approx(8.0)
    assert from_internal(r["base_plate.thickness_tension"].demand, Kind.LENGTH, "in") == \
        pytest.approx(1.05, rel=0.01)
    assert from_internal(r["anchor.steel_tension"].demand, Kind.FORCE, "kip") == \
        pytest.approx(15.8, rel=0.02)
    assert from_internal(r["anchor.pullout"].demand, Kind.FORCE, "kip") == \
        pytest.approx(39.7, rel=0.01)
    assert from_internal(r["anchor.concrete_breakout_tension"].demand,
                         Kind.FORCE, "kip") == pytest.approx(119, rel=0.01)
    assert r["base_plate.weak_base_area"].status.value == "ok"
    assert r["base_plate.weak_base_stretch"].status.value == "ok"


def test_weak_base_requires_defined_yield_stress():
    plate = dataclasses.replace(
        _plate(), rod=BoltSpec(diameter=inch(1), grade="ASTM F3125 Gr. A325"))
    with pytest.raises(ValueError, match="defined yield"):
        check_base_plate(plate, Forces(P=kip(376), M3=kip_in(3600)), Method.LRFD)
