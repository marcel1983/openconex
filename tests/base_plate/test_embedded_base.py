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

    plate = _plate()
    embedded = dataclasses.replace(plate.embedded_base, face_plate_thickness=0.0,
                                   type=EmbeddedType.TYPE_II,
                                   base_plate_width=inch(22),
                                   base_plate_thickness=inch(1.5), **kwargs)
    return dataclasses.replace(plate, embedded_base=embedded)


def test_type2_moment_is_horizontal_bearing_only():
    """DG1 §5.2.2 Type II, conservative: M_VB = 0, compression through the embedded plate."""
    plate = _type2()
    results = check_base_plate(plate, _forces(), Method.LRFD)
    r = by_id(results)
    col = plate.column
    alone = embedded_base_moment(kip(96), inch(22), col.bf, inch(60), plate.fc, kip_ft(700),
                                 bj=(col.bf + inch(22)) / 2)
    moment = r["base_plate.embedded_moment"]
    assert moment.capacity == pytest.approx(alone.capacity)
    steps = {s.symbol: s.value for s in moment.steps}
    assert steps["M_{VB}"] == 0.0
    assert set(r) == {"base_plate.embedded_moment", "base_plate.embedded_plate_bearing",
                      "base_plate.embedded_plate_thickness"}
    assert all(x.status.value == "ok" for x in results)


def test_type2_equals_type1_with_the_same_embedded_plate():
    type2 = _type2()
    type1 = dataclasses.replace(type2, embedded_base=dataclasses.replace(
        type2.embedded_base, type="I", face_plate_thickness=inch(1)))
    r1 = by_id(check_base_plate(type1, _forces(), Method.LRFD))
    r2 = by_id(check_base_plate(type2, _forces(), Method.LRFD))
    assert r2["base_plate.embedded_moment"].capacity == pytest.approx(
        r1["base_plate.embedded_moment"].capacity)


def test_type2_breakout_force_eq_5_9():
    """F_t = 40/9 A35 sqrt(f'c/d) (CCD, psi and in, result in lb), Scenario 1."""
    from openconex.connections.base_plate.check import type2_breakout_force

    plate = _type2()
    # 0.3N block 6.6 in, cone spread 22/tan 35° = 31.42 in, side room (60 − 22)/2 = 19 in
    spread = 22 / 0.7002075382097097
    along = 0.3 * 22 + spread + 19
    across = 22 + 2 * 19
    expected = 40 / 9 * along * across * (4000 / 22) ** 0.5
    assert from_internal(type2_breakout_force(plate), Kind.FORCE, "lbf") == pytest.approx(
        expected, rel=1e-9)
    steps = {s.symbol for s in by_id(check_base_plate(plate, _forces(), Method.LRFD))[
        "base_plate.embedded_moment"].steps}
    assert "F_t" in steps


def test_type2_uplift_goes_through_the_embedded_plate():
    r = by_id(check_base_plate(_type2(), Forces(P=kip(-50), V2=kip(20), M3=kip_ft(200)),
                               Method.LRFD))
    assert {"base_plate.embedded_uplift_breakout",
            "base_plate.embedded_uplift_pullout"} <= set(r)


def test_type2_requires_the_embedded_plate():
    plate = _type2()
    plate = dataclasses.replace(plate, embedded_base=dataclasses.replace(
        plate.embedded_base, base_plate_width=None, base_plate_thickness=None))
    with pytest.raises(ValueError, match="Type II"):
        check_base_plate(plate, _forces(), Method.LRFD)


def test_type2_example_project():
    from pathlib import Path

    from openconex.io.project import load_project
    from openconex.report.builder import build_base_plate_report

    path = Path(__file__).parents[2] / "examples" / "base_plate_embedded_type2.ocnx"
    project = load_project(path)
    report = build_base_plate_report(project)
    assert report.ok
    assert {r.id for r in report.results} == {
        "base_plate.embedded_moment", "base_plate.embedded_plate_bearing",
        "base_plate.embedded_plate_thickness"}
    data = project.model_dump(mode="json")
    del data["base_plate"]["embedded_base"]["base_plate_width"]
    with pytest.raises(ValueError, match="Type II needs the embedded base plate"):
        type(project).model_validate(data)
