# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Plate bending at the anchor rods (DG1 Examples 4.7-3 and 4.7-7)."""

import pytest

from openconex.connections.base_plate.check import BasePlate, check_base_plate
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


def by_id(results):
    return {r.id: r for r in results}


def test_axial_tension_plate_bending_ex_4_7_3():
    column = aisc_shapes().get("W10X45").to_ishape()
    plate = BasePlate(
        column=column, N=inch(16), B=inch(16), tp=inch(1),
        fc=to_internal(4, "ksi", Kind.STRESS),
        rod=BoltSpec(diameter=inch(0.875), grade="ASTM F1554 Gr. 36"),
        f=inch(2), rods_per_side=2, rod_spacing=inch(4), hef=inch(15),
        A2_over_A1=1.0, rod_bending_lever=inch((4 - 0.350) / 2))
    r = by_id(check_base_plate(plate, Forces(P=kip(-70)), Method.LRFD))
    check = r["base_plate.plate_bending_rods"]
    assert from_internal(check.demand, Kind.MOMENT, "kip*in") == pytest.approx(32.0, rel=0.01)
    assert check.status.value == "ok"


def test_axial_tension_plate_bending_ex_4_7_3_asd():
    column = aisc_shapes().get("W10X45").to_ishape()
    plate = BasePlate(
        column=column, N=inch(16), B=inch(16), tp=inch(1),
        fc=to_internal(4, "ksi", Kind.STRESS),
        rod=BoltSpec(diameter=inch(0.875), grade="ASTM F1554 Gr. 36"),
        f=inch(2), rods_per_side=2, rod_spacing=inch(4), hef=inch(15),
        A2_over_A1=1.0, rod_bending_lever=inch((4 - 0.350) / 2))
    r = by_id(check_base_plate(plate, Forces(P=kip(-45)), Method.ASD))
    check = r["base_plate.plate_bending_rods"]
    assert from_internal(check.demand, Kind.MOMENT, "kip*in") == pytest.approx(20.7, rel=0.01)


def test_brace_tension_plate_bending_ex_4_7_7():
    column = aisc_shapes().get("W21X83").to_ishape()
    plate = BasePlate(
        column=column, N=inch(20), B=inch(20), tp=inch(1.75),
        fc=to_internal(5, "ksi", Kind.STRESS),
        rod=BoltSpec(diameter=inch(1.5), grade="ASTM F1554 Gr. 36"),
        f=inch(4), rods_per_side=4, rod_spacing=inch(8), hef=inch(24),
        A2_over_A1=4.0, rod_bending_lever=inch(3.0))
    r = by_id(check_base_plate(plate, Forces(P=kip(-138)), Method.LRFD))
    check = r["base_plate.plate_bending_rods"]
    assert from_internal(check.demand, Kind.MOMENT, "kip*in") == pytest.approx(51.9, rel=0.01)


def test_plate_bending_check_is_optional():
    column = aisc_shapes().get("W10X45").to_ishape()
    plate = BasePlate(
        column=column, N=inch(16), B=inch(16), tp=inch(1),
        fc=to_internal(4, "ksi", Kind.STRESS),
        rod=BoltSpec(diameter=inch(0.875), grade="ASTM F1554 Gr. 36"),
        f=inch(2), rods_per_side=2, rod_spacing=inch(4), hef=inch(15),
        A2_over_A1=1.0)
    r = by_id(check_base_plate(plate, Forces(P=kip(-70)), Method.LRFD))
    assert "base_plate.plate_bending_rods" not in r
