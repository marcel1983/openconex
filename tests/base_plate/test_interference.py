# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Plan-view interference checks for anchor rods and washers."""

import pytest

from openconex.connections.base_plate.check import (
    BasePlate,
    PedestalRebar,
    ShearLug,
    check_base_plate,
)
from openconex.core.loads import Forces, Method
from openconex.core.model import BoltSpec
from openconex.core.shapes import aisc_shapes
from openconex.units import Kind, from_internal, to_internal


def inch(value):
    return to_internal(value, "in", Kind.LENGTH)


def by_id(results):
    return {r.id: r for r in results}


def _plate(**changes):
    data = dict(
        column=aisc_shapes().get("W12X96").to_ishape(),
        N=inch(24), B=inch(24), tp=inch(1),
        fc=to_internal(4, "ksi", Kind.STRESS),
        rod=BoltSpec(diameter=inch(1), grade="ASTM F1554 Gr. 36"),
        f=inch(9), rods_per_side=2, rod_spacing=inch(8), hef=0,
    )
    data.update(changes)
    return BasePlate(**data)


def _checks(plate):
    return by_id(check_base_plate(plate, Forces(), Method.LRFD))


def test_valid_anchor_layout_is_clear():
    r = _checks(_plate())
    assert r["base_plate.anchor_column_clearance"].status.value == "ok"
    assert r["base_plate.anchor_plate_edge"].status.value == "ok"


def test_anchor_inside_column_footprint_is_flagged():
    r = _checks(_plate(f=inch(5)))
    assert r["base_plate.anchor_column_clearance"].status.value == "ng"
    assert from_internal(r["base_plate.anchor_column_clearance"].capacity,
                         Kind.LENGTH, "in") == pytest.approx(0.0)


def test_washer_near_plate_edge_is_flagged():
    r = _checks(_plate(f=inch(11)))
    assert r["base_plate.anchor_plate_edge"].status.value == "ng"
    assert from_internal(r["base_plate.anchor_plate_edge"].demand,
                         Kind.LENGTH, "in") == pytest.approx(1.5)


def test_anchor_colliding_with_shear_lug_is_flagged():
    lug = ShearLug(width=inch(18), embedment=inch(6), thickness=inch(1),
                   weld=inch(0.25), direction="weak")
    r = _checks(_plate(rods_per_side=1, rod_spacing=0, shear_lug=lug))
    assert r["base_plate.anchor_lug_clearance"].status.value == "ng"


def test_anchor_colliding_with_pedestal_bar_is_flagged():
    bar = PedestalRebar(x=inch(9), y=inch(4), diameter=inch(0.75))
    r = _checks(_plate(pedestal_rebars=(bar,)))
    assert r["base_plate.anchor_rebar_clearance"].status.value == "ng"
    assert r["base_plate.anchor_rebar_clearance"].demand > 0
