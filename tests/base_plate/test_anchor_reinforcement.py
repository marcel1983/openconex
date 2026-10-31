# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Anchor reinforcement in the complete base plate check (DG1 Example 4.7-15)."""

import pytest

from openconex.connections.base_plate.check import BasePlate, Reinforcement, check_base_plate
from openconex.core.loads import Forces, Method
from openconex.core.model import BoltSpec
from openconex.core.shapes import aisc_shapes
from openconex.units import Kind, from_internal, to_internal


def inch(value):
    return to_internal(value, "in", Kind.LENGTH)


def kip(value):
    return to_internal(value, "kip", Kind.FORCE)


def by_id(results):
    return {r.id: r for r in results}


def _plate(reinforcement):
    return BasePlate(
        column=aisc_shapes().get("W10X45").to_ishape(),
        N=inch(20), B=inch(20), tp=inch(1.5),
        fc=to_internal(4, "ksi", Kind.STRESS),
        rod=BoltSpec(diameter=inch(0.875), grade="ASTM F1554 Gr. 36"),
        f=inch(2), rods_per_side=2, rod_spacing=inch(4), hef=inch(14),
        A2_over_A1=1.0, reinforcement=reinforcement)


REINFORCEMENT = Reinforcement(
    area=to_internal(1.76, "in**2", Kind.AREA), fy=to_internal(60, "ksi", Kind.STRESS),
    db=inch(0.75), clear_cover=inch(2), anchor_to_bar=inch(2.83), le=inch(15.2),
    bars="4 #6")


def test_dg1_4_7_15_end_to_end():
    r = by_id(check_base_plate(_plate(REINFORCEMENT), Forces(P=kip(-70)), Method.LRFD))
    assert r["anchor.reinforcement"].status.value == "ok"
    assert from_internal(r["anchor.reinforcement"].capacity, Kind.FORCE, "kip") == \
        pytest.approx(79.2, rel=0.01)
    assert from_internal(r["anchor.reinforcement_development"].demand,
                         Kind.LENGTH, "in") == pytest.approx(9.71, rel=0.01)
    assert from_internal(r["anchor.reinforcement_embedment"].demand,
                         Kind.LENGTH, "in") == pytest.approx(13.6, rel=0.01)
    assert "anchor.concrete_breakout_tension" not in r


def test_insufficient_reinforcement_is_reported():
    small = Reinforcement(
        area=to_internal(0.50, "in**2", Kind.AREA), fy=REINFORCEMENT.fy,
        db=REINFORCEMENT.db, clear_cover=REINFORCEMENT.clear_cover,
        anchor_to_bar=REINFORCEMENT.anchor_to_bar, le=REINFORCEMENT.le)
    r = by_id(check_base_plate(_plate(small), Forces(P=kip(-70)), Method.LRFD))
    assert r["anchor.reinforcement"].status.value == "ng"


def test_without_reinforcement_breakout_is_checked():
    r = by_id(check_base_plate(_plate(None), Forces(P=kip(-70)), Method.LRFD))
    assert "anchor.concrete_breakout_tension" in r
    assert "anchor.reinforcement" not in r
