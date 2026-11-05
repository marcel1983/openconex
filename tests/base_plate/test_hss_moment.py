# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""HSS base plates under axial compression and moment (STI, 2024).

Reference: M. Manor, "HSS Base Plate Design for Axial Compression and Bending
Moment", Steel Tube Institute, September 2024. Examples 1 and 2.

The article adapts AISC DG1 3rd ed. to HSS columns. Rectangular and square HSS
use the same 0.95 coefficient in both directions. The article notes that no
published example exists for round HSS with moment, so OpenConex rejects that
case instead of presenting an unvalidated approximation.
"""

import dataclasses
import json
from pathlib import Path

import pytest

from openconex.connections.base_plate import plate as bpl
from openconex.connections.base_plate.check import (
    BasePlate,
    BearingAreaModel,
    PressureModel,
    check_base_plate,
)
from openconex.core.loads import Forces, Method
from openconex.core.model import BoltSpec, HSSKind, HSSShape, IShape
from openconex.io.project import Project, load_project
from openconex.units import Kind, from_internal, to_internal

EXAMPLES = Path(__file__).parents[2] / "examples"


def inch(value):
    return to_internal(value, "in", Kind.LENGTH)


def kip(value):
    return to_internal(value, "kip", Kind.FORCE)


def ksi(value):
    return to_internal(value, "ksi", Kind.STRESS)


def kip_in(value):
    return to_internal(value, "kip*in", Kind.MOMENT)


def kip_ft(value):
    return to_internal(value, "kip*ft", Kind.MOMENT)


def by_id(results):
    return {result.id: result for result in results}


def _sti_round_compression():
    column = HSSShape(
        name="HSS 12x0.375", kind=HSSKind.ROUND, d=inch(12), t=inch(0.349),
        grade="ASTM A500 Gr. C (round)")
    return BasePlate(
        column=column, N=inch(18), B=inch(18), tp=inch(1.25), fc=ksi(3),
        rod=BoltSpec(diameter=inch(0.75)), f=inch(4.2), rods_per_side=2,
        rod_spacing=inch(9.6), A2_over_A1=1.0)


def _sti_rectangular_moment():
    column = HSSShape(
        name="HSS 16x12x1/2", kind=HSSKind.RECTANGULAR, d=inch(16), width=inch(12),
        t=inch(0.465), grade="ASTM A500 Gr. C (rectangular)")
    return BasePlate(
        column=column, N=inch(24), B=inch(20), tp=inch(1.5), fc=ksi(4),
        rod=BoltSpec(diameter=inch(0.75)), f=inch(10), rods_per_side=4,
        rod_spacing=inch(11.4), A2_over_A1=1.0)


def test_sti_example_1_round_hss_compression():
    """STI Example 1: HSS 12x0.375, Pu = 500 kip, 18x18x1 1/4 in plate."""
    bp = _sti_round_compression()
    result = by_id(check_base_plate(bp, Forces(P=kip(500)), Method.LRFD))
    assert from_internal(result["base_plate.thickness_compression"].demand,
                         Kind.LENGTH, "in") == pytest.approx(1.10, rel=0.01)
    assert from_internal(result["base_plate.thickness_compression"].capacity,
                         Kind.LENGTH, "in") == pytest.approx(1.25, rel=0.01)


def test_sti_example_2_rectangular_hss_moment():
    """STI Example 2: HSS 16x12x1/2, Pu = 376 kip, Mu = 300 kip-ft."""
    bp = _sti_rectangular_moment()
    forces = Forces(P=kip(376), M3=kip_ft(300))
    result = by_id(check_base_plate(bp, forces, Method.LRFD, "LRFD-1"))

    compression = result["base_plate.thickness_compression"]
    assert from_internal(compression.demand, Kind.LENGTH, "in") == \
        pytest.approx(1.38, rel=0.01)
    steps = {step.symbol: step.value for step in compression.steps}
    assert from_internal(steps["Y"], Kind.LENGTH, "in") == pytest.approx(9.71, rel=0.01)
    assert from_internal(steps["T"], Kind.FORCE, "kip") == pytest.approx(53.3, rel=0.01)

    tension = result["base_plate.thickness_tension"]
    assert from_internal(tension.demand, Kind.LENGTH, "in") == \
        pytest.approx(0.73, rel=0.01)
    assert from_internal(result["anchor.steel_tension"].demand, Kind.FORCE, "kip") == \
        pytest.approx(13.3, rel=0.01)


def test_rectangular_hss_moment_intermediate_values():
    bp = _sti_rectangular_moment()
    assert from_internal(bpl.bearing_stress(bp.fc, 1.0, Method.LRFD),
                         Kind.STRESS, "ksi") == pytest.approx(2.21, rel=0.01)

    bend = bpl.rectangular_bending(kip(376), kip_ft(300), bp.N, bp.B, bp.f,
                                   bp.fc, 1.0, Method.LRFD)
    assert from_internal(bend.Y, Kind.LENGTH, "in") == pytest.approx(9.71, rel=0.01)
    assert from_internal(bend.T, Kind.FORCE, "kip") == pytest.approx(53.3, rel=0.01)

    design = bpl.compression_design(
        kip(376), bp.column.d, bp.column.bf, bp.N, bp.B, bp.Fy, bp.fc, 1.0,
        Method.LRFD, hss=bp.column.kind)
    assert from_internal(design.m, Kind.LENGTH, "in") == pytest.approx(4.4, rel=0.01)
    assert from_internal(design.n, Kind.LENGTH, "in") == pytest.approx(4.3, rel=0.01)


def test_round_hss_with_moment_is_rejected():
    bp = _sti_round_compression()
    with pytest.raises(ValueError, match="round HSS with moment"):
        check_base_plate(bp, Forces(P=kip(100), M3=kip_in(100)), Method.LRFD)


def test_effective_area_with_moment_is_rejected():
    bp = dataclasses.replace(
        _sti_rectangular_moment(), bearing_area_model=BearingAreaModel.EFFECTIVE)
    with pytest.raises(ValueError, match="concentric compression"):
        check_base_plate(bp, Forces(P=kip(100), M3=kip_in(100)), Method.LRFD)


def test_triangular_model_supports_weak_axis_moment():
    column = IShape(name="SQ-12", d=inch(12), bf=inch(12), tf=inch(0.5), tw=inch(0.5))
    bp = BasePlate(
        column=column, N=inch(19), B=inch(19), tp=inch(1.25), fc=ksi(4),
        rod=BoltSpec(diameter=inch(0.75)), f=inch(8.5), rods_per_side=2,
        rod_spacing=inch(17), pressure_model=PressureModel.TRIANGULAR)
    strong = by_id(check_base_plate(bp, Forces(P=kip(376), M3=kip_in(940)),
                                    Method.LRFD))
    weak = by_id(check_base_plate(bp, Forces(P=kip(376), M2=kip_in(940)),
                                  Method.LRFD))
    strong_thickness = strong["base_plate.thickness_compression"].demand
    weak_thickness = weak["base_plate.thickness_compression_weak"].demand
    assert weak_thickness == pytest.approx(strong_thickness, rel=1e-9)
    assert weak["base_plate.bearing_weak"].demand == \
        pytest.approx(strong["base_plate.bearing"].demand, rel=1e-9)


def test_project_rejects_round_hss_moment():
    data = json.loads((EXAMPLES / "base_plate_hss_round.ocnx").read_text(encoding="utf-8"))
    data["base_plate"]["column"] = {
        "type": "HSS", "shape": "round", "d": "12 in", "t": "0.5 in",
        "grade": "ASTM A500 Gr. C (round)"}
    data["cases"][0]["M"] = "100 kip*in"
    with pytest.raises(ValueError, match="round HSS with moment"):
        Project.model_validate(data)


def test_project_rejects_effective_area_with_moment():
    data = json.loads((EXAMPLES / "base_plate_effective_area.ocnx").read_text(
        encoding="utf-8"))
    data["cases"][0]["M"] = "100 kip*in"
    with pytest.raises(ValueError, match="concentric compression"):
        Project.model_validate(data)


def test_project_accepts_triangular_weak_axis_moment():
    data = json.loads((EXAMPLES / "base_plate_triangular.ocnx").read_text(encoding="utf-8"))
    data["base_plate"]["rod_spacing"] = "6 in"
    data["cases"][0]["M_weak"] = "100 kip*in"
    project = Project.model_validate(data)
    bp = project.base_plate_model()
    assert bp.pressure_model is PressureModel.TRIANGULAR
    results = check_base_plate(bp, project.case_forces()["B21"], Method.LRFD, "B21")
    assert any(result.id == "base_plate.bearing_weak" for result in results)


def test_hss_round_example_still_loads_without_moment():
    path = EXAMPLES / "base_plate_hss_round.ocnx"
    project = load_project(path)
    assert project is not None
