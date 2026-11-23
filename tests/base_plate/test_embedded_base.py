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


def test_embedded_base_uplift_needs_an_embedded_plate():
    forces = _forces().model_copy(update={"P": kip(-10)})
    with pytest.raises(ValueError, match="uplift"):
        check_base_plate(_plate(), forces, Method.LRFD)


def _with_plate(**kwargs):
    embedded = dataclasses.replace(_plate().embedded_base, base_plate_width=inch(24),
                                   base_plate_thickness=inch(1.5), **kwargs)
    return dataclasses.replace(_plate(), embedded_base=embedded)


def test_face_plate_weld_matches_manual_equation_8_2a():
    """φR_n = 1.392 D L kip for E70 fillets (AISC Manual Part 8, Eq. 8-2a)."""
    plate = _with_plate(face_plate_weld=inch(5 / 16))
    r = by_id(check_base_plate(plate, _forces(), Method.LRFD))
    col = plate.column
    length = from_internal(2 * (col.d - 2 * col.tf) + 2 * (col.bf - col.tw), Kind.LENGTH, "in")
    weld = r["base_plate.face_plate_weld"]
    assert from_internal(weld.capacity, Kind.FORCE, "kip") == pytest.approx(
        1.392 * 5 * length, rel=0.002)
    assert from_internal(weld.demand, Kind.FORCE, "kip") == pytest.approx(250)


def test_face_plate_weld_is_optional():
    r = by_id(check_base_plate(_plate(), _forces(), Method.LRFD))
    assert "base_plate.face_plate_weld" not in r


def test_embedded_plate_bearing_and_bending_follow_dg1_4_3_1():
    from openconex.connections.base_plate.plate import compression_design

    plate = _with_plate()
    r = by_id(check_base_plate(plate, _forces(), Method.LRFD))
    col = plate.column
    comp = compression_design(kip(250), col.d, col.bf, inch(24), inch(24), plate.Fy,
                              plate.fc, 1.0, Method.LRFD)
    assert r["base_plate.embedded_plate_bearing"].capacity == pytest.approx(comp.Pp_available)
    assert r["base_plate.embedded_plate_thickness"].demand == pytest.approx(comp.tp_req)
    assert r["base_plate.embedded_plate_thickness"].capacity == pytest.approx(inch(1.5))
    assert "base_plate.embedded_uplift_breakout" not in r


def test_embedded_base_uplift_checks_breakout_and_pullout():
    plate = _with_plate()
    forces = _forces().model_copy(update={"P": kip(-50)})
    r = by_id(check_base_plate(plate, forces, Method.LRFD))
    assert {"base_plate.embedded_uplift_breakout", "base_plate.embedded_uplift_pullout",
            "base_plate.embedded_plate_thickness", "base_plate.embedded_moment"} <= set(r)
    assert "base_plate.face_plate_bearing" not in r
    pull = r["base_plate.embedded_uplift_pullout"]
    col = plate.column
    area = from_internal(inch(24) ** 2 - (2 * col.bf * col.tf + (col.d - 2 * col.tf) * col.tw),
                         Kind.AREA, "in**2")
    # φN_pn = 0.70 (8 A_brg f'c), cracked concrete (ACI 318-19 §17.6.3)
    assert from_internal(pull.capacity, Kind.FORCE, "kip") == pytest.approx(
        0.70 * 8 * area * 4, rel=1e-3)
    breakout = r["base_plate.embedded_uplift_breakout"]
    assert from_internal(breakout.demand, Kind.FORCE, "kip") == pytest.approx(50)


def _type2(**kwargs):
    from openconex.connections.base_plate.check import EmbeddedType

    plate = BasePlate(
        column=aisc_shapes().get("W12X96").to_ishape(),
        N=inch(24), B=inch(22), tp=inch(2),
        fc=to_internal(4, "ksi", Kind.STRESS),
        rod=BoltSpec(diameter=inch(1), grade="ASTM F1554 Gr. 36"),
        f=inch(9.25), rods_per_side=2, rod_spacing=inch(12), hef=inch(18),
        embedded_base=EmbeddedBase(embedment=inch(18), foundation_width=inch(48),
                                   face_plate_thickness=0.0, type=EmbeddedType.TYPE_II,
                                   **kwargs))
    return plate


def test_type2_superposes_blockout_and_base_plate():
    from openconex.connections.base_plate.plate import biaxial_capacity

    plate = _type2()
    forces = Forces(P=kip(150), V2=kip(35), M3=kip_ft(350))
    results = check_base_plate(plate, forces, Method.LRFD)
    r = by_id(results)
    total = r["base_plate.type2_moment"]
    mhb = r["base_plate.embedded_moment"]
    alone = embedded_base_moment(kip(35), inch(18), plate.column.bf, inch(48), plate.fc, 0.0)
    steps = {s.symbol: s.value for s in total.steps}
    _, m_bp = biaxial_capacity(kip(150), inch(24), inch(22), inch(9.25), plate.fc, 1.0,
                               steps["T_{cap}"], Method.LRFD)
    assert total.capacity == pytest.approx(alone.capacity + m_bp)
    # moment shared in proportion to the strengths: equal ratios
    assert mhb.ratio == pytest.approx(total.ratio, rel=1e-9)
    assert "base_plate.bearing" in r and "base_plate.face_plate_bearing" not in r
    assert all(x.status.value == "ok" for x in results)


def test_type2_without_blockout_depth_is_the_exposed_plate():
    plate = _type2()
    shallow = dataclasses.replace(
        plate, embedded_base=dataclasses.replace(plate.embedded_base, embedment=inch(0.01)))
    forces = Forces(P=kip(150), M3=kip_ft(100))
    r = by_id(check_base_plate(shallow, forces, Method.LRFD))
    exposed = by_id(check_base_plate(dataclasses.replace(plate, embedded_base=None), forces,
                                     Method.LRFD))
    assert r["base_plate.bearing"].demand == pytest.approx(exposed["base_plate.bearing"].demand,
                                                           rel=1e-3)


def test_type2_requires_the_base_plate():
    plate = dataclasses.replace(_type2(), tp=0.0)
    with pytest.raises(ValueError, match="Type II"):
        check_base_plate(plate, Forces(P=kip(150), M3=kip_ft(100)), Method.LRFD)


def test_type2_example_project():
    from pathlib import Path

    from openconex.io.project import load_project
    from openconex.report.builder import build_base_plate_report

    path = Path(__file__).parents[2] / "examples" / "base_plate_embedded_type2.ocnx"
    report = build_base_plate_report(load_project(path))
    assert report.ok
    ids = {r.id for r in report.results}
    assert {"base_plate.type2_moment", "base_plate.embedded_moment",
            "base_plate.bearing"} <= ids
