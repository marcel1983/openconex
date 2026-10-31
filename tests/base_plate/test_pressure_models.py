# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Optional bearing models: triangular pressure and effective area (DG1 App. B)."""

import tomllib
from pathlib import Path

import pytest

from openconex.connections.base_plate.check import (
    BasePlate,
    BearingAreaModel,
    PressureModel,
    check_base_plate,
)
from openconex.core.loads import Forces, Method
from openconex.core.model import BoltSpec
from openconex.core.shapes import aisc_shapes
from openconex.io.project import load_project
from openconex.report.builder import build_base_plate_report
from openconex.units import Kind, from_internal, to_internal

CASES = Path(__file__).parents[1] / "reference" / "dg1"
EXAMPLES = Path(__file__).parents[2] / "examples"


def q(text):
    from openconex.units import ureg

    quantity = ureg.Quantity(text)
    for unit in ("mm", "mm**2", "N", "MPa", "N*mm", "N/mm", "N*mm/mm"):
        if quantity.dimensionality == ureg.Unit(unit).dimensionality:
            return float(quantity.to(unit).magnitude)
    raise ValueError(text)


def load(case_id):
    with (CASES / f"ex_{case_id}.toml").open("rb") as fh:
        return tomllib.load(fh)


def g(case, key):
    return q(case["given"][key])


def by_id(results):
    return {r.id: r for r in results}


def _shape(label):
    return aisc_shapes().get(label).to_ishape()


def _plate(case_id, **kw):
    case = load(case_id)
    column = _shape(case["given"]["column"])
    return BasePlate(
        column=column, N=g(case, "N"), B=g(case, "B"), tp=g(case, "tp")
        if "tp" in case["given"] else to_internal(1.0, "in", Kind.LENGTH),
        fc=g(case, "fc"), rod=BoltSpec(diameter=to_internal(0.75, "in", Kind.LENGTH)),
        f=to_internal(5.5, "in", Kind.LENGTH), rods_per_side=2,
        A2_over_A1=case["given"].get("A2_over_A1", 1.0), **kw)


def test_triangular_low_moment_b_2_1():
    case = load("B.2-1")
    plate = _plate("B.2-1", pressure_model=PressureModel.TRIANGULAR)
    r = by_id(check_base_plate(
        plate, Forces(P=g(case, "Pu"), M3=q(case["given"]["Mu"])), Method.LRFD))
    assert from_internal(r["base_plate.bearing"].demand, Kind.STRESS, "ksi") == \
        pytest.approx(1.86, rel=0.01)
    assert from_internal(r["base_plate.bearing"].capacity, Kind.STRESS, "ksi") == \
        pytest.approx(2.21, rel=0.01)
    assert from_internal(r["base_plate.thickness_compression"].demand, Kind.LENGTH, "in") == \
        pytest.approx(0.993, rel=0.01)


def test_triangular_large_moment_b_2_2():
    case = load("B.2-2")
    plate = _plate("B.2-2", pressure_model=PressureModel.TRIANGULAR)
    r = by_id(check_base_plate(
        plate, Forces(P=g(case, "Pu"), M3=q(case["given"]["Mu"])), Method.LRFD))
    compression = from_internal(
        r["base_plate.thickness_compression"].demand, Kind.LENGTH, "in")
    tension = from_internal(r["base_plate.thickness_tension"].demand, Kind.LENGTH, "in")
    assert max(compression, tension) == pytest.approx(1.08, rel=0.01)
    steps = {s.symbol: s.value for s in r["base_plate.thickness_compression"].steps}
    assert from_internal(steps["T"], Kind.FORCE, "kip") == pytest.approx(21.6, rel=0.01)


def test_triangular_example_project():
    project = load_project(EXAMPLES / "base_plate_triangular.ocnx")
    assert project.base_plate_model().pressure_model is PressureModel.TRIANGULAR
    report = build_base_plate_report(project)
    assert report.ok
    assert any("triangular" in assumption.lower() for assumption in report.assumptions)


def test_effective_area_example_project():
    project = load_project(EXAMPLES / "base_plate_effective_area.ocnx")
    assert project.base_plate_model().bearing_area_model is BearingAreaModel.EFFECTIVE
    report = build_base_plate_report(project)
    assert report.ok
    assert any("efectiva" in assumption.lower() for assumption in report.assumptions)


def test_effective_area_b_3_1():
    case = load("B.3-1")
    plate = _plate("B.3-1", bearing_area_model=BearingAreaModel.EFFECTIVE,
                   pressure_model=PressureModel.RECTANGULAR)
    r = by_id(check_base_plate(
        plate, Forces(P=g(case, "Pu")), Method.LRFD))
    assert from_internal(r["base_plate.bearing"].capacity, Kind.FORCE, "kip") == \
        pytest.approx(787, rel=0.01)
