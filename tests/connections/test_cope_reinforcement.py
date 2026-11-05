# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Cope reinforcement: doubler plate and longitudinal stiffener (AISC II.A-6 C/D)."""

import json
from pathlib import Path

import pytest

from openconex.connections.shear.check import check_shear_connection
from openconex.connections.shear.cope_reinforcement import (
    DoublerPlate,
    LongitudinalStiffener,
)
from openconex.connections.shear.coped_beam import CopedBeam, check_coped_beam
from openconex.core.loads import Method
from openconex.io.project import Project
from openconex.report.builder import build_report
from openconex.units import Kind, from_internal, to_internal

EXAMPLES = Path(__file__).parents[2] / "examples"


def inch(value):
    return to_internal(value, "in", Kind.LENGTH)


def kip(value):
    return to_internal(value, "kip", Kind.FORCE)


def ksi(value):
    return to_internal(value, "ksi", Kind.STRESS)


def by_id(results):
    return {result.id: result for result in results}


def _plate(**extra):
    """AISC II.A-6: W21x62 coped 8 in. deep by 9 in. long, 1/2 in. setback."""
    return CopedBeam(
        d=inch(21), tw=inch(0.4), bf=inch(8.24), tf=inch(0.615),
        Fy=ksi(50), Fu=ksi(65), c=inch(9), dc=inch(8), setback=inch(0.5),
        rows=0, **extra)


def test_ii_a_6_c_doubler_plate():
    checks = by_id(check_coped_beam(
        _plate(doubler=DoublerPlate(inch(0.25), inch(6.5), inch(0.5), inch(0.25))),
        kip(135), Method.LRFD))
    assert "coped_beam.flexure" not in checks
    assert from_internal(checks["coped_beam.doubler_flexure"].capacity,
                         Kind.FORCE, "kip") == pytest.approx(165, rel=0.01)
    assert from_internal(checks["coped_beam.doubler_shear_yielding"].capacity,
                         Kind.FORCE, "kip") == pytest.approx(205, rel=0.01)
    assert from_internal(checks["coped_beam.doubler_shear_rupture"].capacity,
                         Kind.FORCE, "kip") == pytest.approx(200, rel=0.01)
    assert checks["coped_beam.doubler_compact"].status.value == "ok"
    assert checks["coped_beam.doubler_weld"].status.value == "ok"


def test_ii_a_6_d_longitudinal_stiffener():
    checks = by_id(check_coped_beam(
        _plate(stiffener=LongitudinalStiffener(inch(4), inch(0.25), inch(0.25),
                                               inch(17))),
        kip(135), Method.LRFD))
    assert "coped_beam.flexure" not in checks
    assert from_internal(checks["coped_beam.stiffener_flexure"].capacity,
                         Kind.FORCE, "kip") == pytest.approx(136, rel=0.01)
    assert checks["coped_beam.stiffener_compact"].status.value == "ok"
    assert checks["coped_beam.stiffener_web_compact"].status.value == "ok"
    assert checks["coped_beam.stiffener_weld"].status.value == "ok"
    assert checks["coped_beam.stiffener_web_shear"].status.value == "ok"


def test_cope_reinforcement_is_parsed_and_checked_in_a_project():
    data = json.loads((EXAMPLES / "shear_double_angle_coped.ocnx").read_text(
        encoding="utf-8"))
    data["shear_connection"]["cope"]["doubler"] = {
        "thickness": "1/4 in", "depth": "6.5 in", "gap": "0.5 in", "weld": "1/4 in"}
    project = Project.model_validate(data)
    conn = project.shear_model()
    assert conn.cope.doubler is not None
    result = check_shear_connection(conn, next(iter(project.case_forces().values())),
                                    Method.LRFD)
    assert any(check.id.startswith("coped_beam.doubler") for check in result)
    report = build_report(project)
    assert report.ok
    assert any("placa doble" in row.cells[0].lower() for row in report.summary)


def test_cope_reinforcement_layout_and_3d():
    from openconex.drawing.shear import shear_layout

    data = json.loads((EXAMPLES / "shear_double_angle_coped.ocnx").read_text(
        encoding="utf-8"))
    data["shear_connection"]["cope"]["doubler"] = {
        "thickness": "1/4 in", "depth": "6.5 in", "gap": "0.5 in", "weld": "1/4 in"}
    data["shear_connection"]["cope"]["stiffener"] = {
        "width": "4 in", "thickness": "1/4 in", "weld": "1/4 in"}
    project = Project.model_validate(data)
    conn = project.shear_model()
    lay = shear_layout(conn)
    assert lay.cope_doubler is not None
    assert lay.cope_stiffener is not None
    pytest.importorskip("OCP")
    from openconex.geometry3d.shear import shear_parts
    names = {part.name for part in shear_parts(conn)}
    assert {"doubler", "stiffener"} <= names


def test_cope_reinforcement_rejects_a_bottom_cope():
    data = json.loads((EXAMPLES / "shear_double_angle_coped.ocnx").read_text(
        encoding="utf-8"))
    data["shear_connection"]["cope"]["dc_bottom"] = "2 in"
    data["shear_connection"]["cope"]["stiffener"] = {
        "width": "4 in", "thickness": "1/4 in", "weld": "1/4 in"}
    with pytest.raises(ValueError, match="top cope"):
        Project.model_validate(data)
