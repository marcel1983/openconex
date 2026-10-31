# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Type I embedded base with face bearing plates (DG1 Example 5.3-1)."""

import dataclasses

import pytest

from openconex.connections.base_plate.check import (
    BasePlate,
    EmbeddedBase,
    check_base_plate,
)
from openconex.connections.base_plate.seismic import embedded_base_moment, face_plate_design
from openconex.core.loads import Forces, Method
from openconex.core.model import BoltSpec, HSSKind, HSSShape
from openconex.core.shapes import aisc_shapes
from openconex.units import Kind, from_internal, to_internal


def inch(value):
    return to_internal(value, "in", Kind.LENGTH)


def kip(value):
    return to_internal(value, "kip", Kind.FORCE)


def kip_ft(value):
    return to_internal(value, "kip*ft", Kind.MOMENT)


def by_id(results):
    return {r.id: r for r in results}


def _plate():
    return BasePlate(
        column=aisc_shapes().get("W14X176").to_ishape(),
        N=inch(24), B=inch(24), tp=inch(1),
        fc=to_internal(4, "ksi", Kind.STRESS),
        rod=BoltSpec(diameter=inch(1), grade="ASTM F1554 Gr. 36"),
        f=inch(8), rods_per_side=2,
        embedded_base=EmbeddedBase(
            embedment=inch(22), foundation_width=inch(60),
            face_plate_thickness=inch(1)))


def _forces():
    return Forces(P=kip(250), V2=kip(96), M3=kip_ft(700))


def test_dg1_5_3_1_embedded_base():
    results = check_base_plate(_plate(), _forces(), Method.LRFD)
    r = by_id(results)
    assert len(results) == 4
    assert from_internal(r["base_plate.embedded_moment"].capacity,
                         Kind.MOMENT, "kip*ft") == pytest.approx(719, rel=0.01)
    assert from_internal(r["base_plate.face_plate_bearing"].capacity,
                         Kind.FORCE, "kip") == pytest.approx(827, rel=0.01)
    assert from_internal(r["base_plate.face_plate_thickness"].demand,
                         Kind.THICKNESS, "in") == pytest.approx(0.941, rel=0.01)
    assert from_internal(r["base_plate.face_plate_seismic"].demand,
                         Kind.THICKNESS, "in") == pytest.approx(0.623, rel=0.01)
    assert all(result.status.value == "ok" for result in results)


def test_embedded_base_horizontal_rebar_and_plate_increase_moment():
    kwargs = dict(demand=kip_ft(8400), bj=inch(22.85),
                  F_rebar_top=kip(30), d_rebar_top=inch(5),
                  F_rebar_bottom=kip(20), d_rebar_bottom=inch(18))
    base = embedded_base_moment(kip(96), inch(22), inch(15.7), inch(60),
                                to_internal(4, "ksi", Kind.STRESS), kip_ft(8400))
    with_rebar = embedded_base_moment(
        kip(96), inch(22), inch(15.7), inch(60),
        to_internal(4, "ksi", Kind.STRESS), **kwargs)
    assert from_internal(with_rebar.capacity, Kind.MOMENT, "kip*ft") == \
        pytest.approx(1101.9, rel=0.01)
    assert with_rebar.capacity > base.capacity


def test_embedded_base_damage_limit_factor():
    base = embedded_base_moment(kip(96), inch(22), inch(15.7), inch(60),
                                to_internal(4, "ksi", Kind.STRESS), kip_ft(8400))
    limited = embedded_base_moment(
        kip(96), inch(22), inch(15.7), inch(60),
        to_internal(4, "ksi", Kind.STRESS), kip_ft(8400), damage_limit=True)
    assert limited.capacity == pytest.approx(0.8 * base.capacity)


def test_face_plate_seismic_thickness_has_a_three_eighths_minimum():
    face = face_plate_design(
        kip(250), inch(15.2), inch(15.7), inch(1.31), inch(0.2),
        to_internal(4, "ksi", Kind.STRESS), to_internal(50, "ksi", Kind.STRESS))
    assert from_internal(face["tp_min_seismic"], Kind.THICKNESS, "in") == pytest.approx(0.375)


def test_embedded_base_requires_lrfd():
    with pytest.raises(ValueError, match="LRFD"):
        check_base_plate(_plate(), _forces(), Method.ASD)


def test_embedded_base_rejects_weak_axis_moment():
    forces = _forces().model_copy(update={"M2": kip_ft(10)})
    with pytest.raises(ValueError, match="weak-axis"):
        check_base_plate(_plate(), forces, Method.LRFD)


def test_embedded_base_rejects_hss_columns():
    hss = HSSShape(name="HSS 12x12x1/2", kind=HSSKind.SQUARE, d=inch(12),
                   width=inch(12), t=inch(0.5),
                   grade="ASTM A500 Gr. B (rectangular)")
    plate = dataclasses.replace(_plate(), column=hss)
    with pytest.raises(ValueError, match="I-shapes"):
        check_base_plate(plate, _forces(), Method.LRFD)


def test_embedded_base_rejects_net_uplift():
    forces = _forces().model_copy(update={"P": kip(-10)})
    with pytest.raises(ValueError, match="uplift"):
        check_base_plate(_plate(), forces, Method.LRFD)
