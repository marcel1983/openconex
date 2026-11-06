# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Skewed double bent plate against AISC Design Example II.A-10 (v15.1)."""

import json
from pathlib import Path

import pytest

from openconex.connections.shear.bent_plate import (
    BentPlate,
    SkewedBentPlate,
    check_bent_plate,
    check_skewed_bent_plate,
    parse_skew,
)
from openconex.connections.shear.check import ShearType, check_shear_envelope
from openconex.core.loads import Method
from openconex.core.model import BoltSpec
from openconex.drawing.shear import shear_dxf
from openconex.io.project import Project
from openconex.report.shear import build_shear_report
from openconex.units import Kind, to_internal

EXAMPLES = Path(__file__).parents[2] / "examples"


def inch(v):
    return to_internal(v, "in", Kind.LENGTH)


def kip(v):
    return to_internal(v, "kip", Kind.FORCE)


def ksi(v):
    return to_internal(v, "ksi", Kind.STRESS)


def bent(thickness=5 / 16, width=6.75):
    return BentPlate(
        thickness=inch(thickness), plate_Fy=ksi(36), plate_Fu=ksi(58),
        length=inch(8.5), width=inch(width), rows=3, spacing=inch(3),
        lev=inch(1.25), leh=inch(1.25), bolt=BoltSpec(diameter=inch(0.875)),
        weld=inch(0.25), weld_return=inch(2.5), weld_offset=inch(3.625),
        FEXX=ksi(70), beam_tw=inch(0.455), beam_Fu=ksi(65),
        support_t=inch(0.490), support_Fu=ksi(65))


def connection(thickness=5 / 16):
    return SkewedBentPlate(plate_a=bent(thickness, 7.25), plate_b=bent(thickness),
                           share_a=0.375, skew="6:12")


def check(conn, R, method):
    return {result.id: result for result in check_skewed_bent_plate(conn, R, method)}


@pytest.mark.parametrize(("method", "R", "bolt_group", "shear_yield", "rupture",
                          "block", "weld_capacity"),
                         [(Method.LRFD, 80, 61.4, 57.5, 44.9, 56.1, 64.2),
                          (Method.ASD, 53.3, 40.9, 38.3, 30.0, 37.5, 42.8)])
def test_example_ii_a_10(method, R, bolt_group, shear_yield, rupture, block, weld_capacity):
    trial = check(connection(5 / 16), kip(R), method)
    final = check(connection(3 / 8), kip(R), method)
    assert trial["skewed_bent_plate.plate_b.bolts"].capacity == pytest.approx(
        kip(bolt_group), rel=0.01)
    assert trial["skewed_bent_plate.plate_b.shear_yielding"].capacity == pytest.approx(
        kip(shear_yield), rel=0.01)
    assert trial["skewed_bent_plate.plate_b.shear_rupture"].capacity == pytest.approx(
        kip(rupture), rel=0.01)
    assert trial["skewed_bent_plate.plate_b.shear_rupture"].status.value == "ng"
    assert final["skewed_bent_plate.plate_b.shear_rupture"].capacity == pytest.approx(
        kip(rupture * (3 / 8) / (5 / 16)), rel=0.01)
    assert final["skewed_bent_plate.plate_b.block_shear"].capacity == pytest.approx(
        kip(block), rel=0.01)
    assert final["skewed_bent_plate.plate_b.weld"].capacity == pytest.approx(
        kip(weld_capacity), rel=0.01)


def test_published_values_and_trace():
    results = check(connection(3 / 8), kip(80), Method.LRFD)
    assert results["skewed_bent_plate.plate_a.bolts"].demand == pytest.approx(kip(30))
    assert results["skewed_bent_plate.plate_b.bolts"].demand == pytest.approx(kip(50))
    weld = results["skewed_bent_plate.plate_b.weld"]
    steps = {step.symbol: step.value for step in weld.steps}
    assert steps["C"] == pytest.approx(kip(2.52) / inch(1), rel=0.01)
    assert steps["D_{req}"] == pytest.approx(3.11, rel=0.01)
    assert steps["D"] == pytest.approx(4.0)
    t_min = results["skewed_bent_plate.beam_web_thickness"]
    assert t_min.demand == pytest.approx(inch(0.296), rel=0.01)
    assert t_min.capacity == pytest.approx(inch(0.455))
    assert results["skewed_bent_plate.plate_thickness"].demand == pytest.approx(
        inch(5 / 16))
    assert all(result.status.value == "ok" for result in results.values())


def test_direct_share_override():
    conn = SkewedBentPlate(plate_a=bent(), plate_b=bent(), share_a=0.5)
    results = check(conn, kip(80), Method.LRFD)
    assert results["skewed_bent_plate.plate_a.bolts"].demand == pytest.approx(kip(40))
    assert results["skewed_bent_plate.plate_b.bolts"].demand == pytest.approx(kip(40))


def test_project_round_trip_and_envelope():
    data = json.loads((EXAMPLES / "shear_skewed_bent_plate.ocnx").read_text(
        encoding="utf-8"))
    project = Project.model_validate(data)
    conn = project.shear_model()
    assert conn.type is ShearType.SKEWED_BENT_PLATE
    assert conn.element.share_a == pytest.approx(0.375)
    assert conn.element.plate_b.width == pytest.approx(inch(6.75))
    assert conn.element.plate_a.leg_beam == pytest.approx(inch(4.4375))
    assert conn.element.plate_b.leg_beam == pytest.approx(inch(3.5625))
    assert conn.element.plate_a.bend_radius == pytest.approx(inch(0.5625))
    assert conn.element.row_distance == pytest.approx(inch(6))
    results = check_shear_envelope(conn, project.load_combinations(), project.case_forces())
    assert results
    assert all(result.status.value != "ng" for result in results)
    assert {result.combo.split("-")[0] for result in results} == {"LRFD", "ASD"}


def test_project_needs_the_load_split():
    data = json.loads((EXAMPLES / "shear_skewed_bent_plate.ocnx").read_text(
        encoding="utf-8"))
    del data["shear_connection"]["row_distance"]
    with pytest.raises(ValueError, match="row_distance"):
        Project.model_validate(data)


def test_invalid_share():
    with pytest.raises(ValueError, match="between 0 and 1"):
        SkewedBentPlate(plate_a=bent(), plate_b=bent(), share_a=1.0)


def test_single_plate_helper():
    results = {result.id: result for result in check_bent_plate(
        bent(), kip(50), Method.LRFD)}
    assert results["skewed_bent_plate.plate_b.bolts"].demand == pytest.approx(kip(50))
    assert results["skewed_bent_plate.plate_b.weld"].status.value == "ok"


def test_report_has_plan_figure():
    data = json.loads((EXAMPLES / "shear_skewed_bent_plate.ocnx").read_text(
        encoding="utf-8"))
    report = build_shear_report(Project.model_validate(data))
    assert report.ok
    keys = [figure.key for figure in report.figures]
    assert keys[0] == "plan"
    assert set(keys) <= {"plan", "isometric"}
    assert len(report.summary) == 12


def test_plan_dxf_contains_the_skew_and_plates():
    data = json.loads((EXAMPLES / "shear_skewed_bent_plate.ocnx").read_text(
        encoding="utf-8"))
    project = Project.model_validate(data)
    doc = shear_dxf(project.shear_model(), project.info.unit_system(), "es")
    texts = [entity.dxf.text for entity in doc.modelspace() if entity.dxftype() == "TEXT"]
    assert "PLANTA" in texts
    assert any("Placa doblada A" in text for text in texts)
    assert any("Placa doblada B" in text for text in texts)
    assert any("6:12" in text for text in texts)
    assert {layer.dxf.name for layer in doc.layers} >= {"SC-VIGA", "SC-APOYO", "SC-PLACA"}


def test_parse_skew():
    assert parse_skew("6:12") == pytest.approx(0.463647609, rel=1e-6)
    assert parse_skew("26.565 deg") == pytest.approx(0.463647609, rel=1e-5)
    assert parse_skew("0.463647609 rad") == pytest.approx(0.463647609, rel=1e-6)
    assert parse_skew("26.565") == pytest.approx(0.463647609, rel=1e-5)
    assert parse_skew("") == 0.0

