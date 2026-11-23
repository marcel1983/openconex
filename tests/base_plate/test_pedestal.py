# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Pedestal designed as a short tied column (ACI 318-19), issue #57.

Reference values:

* Rectangular 12 × 12 in section, 4 #8, f'c = 4 ksi, fy = 60 ksi: Reynolds and
  Kramer, "Interaction Diagrams for Concrete Columns", ACI Designing Concrete
  Structures E702.2 (2007), points Z = -0.5 and Z = -5.
* Round 20 in section, 8 #9 on a 14.72 in circle, f'c = 5 ksi, fy = 60 ksi:
  StructurePoint, "Interaction Diagram - Circular Reinforced Concrete Column
  (ACI 318-14)" (2020), Tables 2 to 8 (after Wang et al., 8th ed.).

E702.2 uses the ACI 318-05 φ transition; the nominal P_n and M_n and the points
with φ = 0.65 or 0.90 are the same in ACI 318-19.
"""

import dataclasses
import json
import math
from pathlib import Path

import pytest

from openconex.connections.base_plate.check import check_base_plate, concrete_edges
from openconex.connections.base_plate.pedestal import (
    Bar,
    Pedestal,
    Section,
    axial_limits,
    beta1,
    flexural_strength,
    nominal_strength,
    pedestal_checks,
    round_edges,
)
from openconex.core.loads import Forces, Method
from openconex.io.project import Project, load_project
from openconex.units import Kind, from_internal, to_internal

EXAMPLES = Path(__file__).parents[2] / "examples"


def inch(v):
    return to_internal(v, "in", Kind.LENGTH)


def ksi(v):
    return to_internal(v, "ksi", Kind.STRESS)


def kip(v):
    return to_internal(v, "kip", Kind.FORCE)


def to_kip(v):
    return from_internal(v, Kind.FORCE, "kip")


def to_kft(v):
    return from_internal(v, Kind.MOMENT, "kip*ft")


def e702_section():
    area = to_internal(0.79, "in**2", Kind.AREA)
    return Section("rectangular", inch(12), inch(12),
                   (Bar(inch(3.5), 2 * area), Bar(inch(-3.5), 2 * area)))


def round_section():
    area = to_internal(1.27, "in**2", Kind.AREA)
    bars = tuple(Bar(inch(7.36 * math.sin(math.radians(90 + 45 * k))), area)
                 for k in range(8))
    return Section("round", inch(20), inch(20), bars)


@pytest.mark.parametrize(("c", "Pn", "Mn"), [
    (7.06, 281.02, 99.41),   # Z = -0.5
    (5.40, 160.96, 105.45),  # Z = -1.1
    (2.14, -43.73, 52.38),   # Z = -5
    (25.05, 658.98, 2.82),   # Z = 0.9, a > h
])
def test_e702_nominal_points(c, Pn, Mn):
    n = nominal_strength(e702_section(), inch(c), ksi(4), ksi(60))
    assert to_kip(n.Pn) == pytest.approx(Pn, rel=0.01)
    assert to_kft(n.Mn) == pytest.approx(Mn, rel=0.02, abs=0.1)


def test_e702_axial_limits():
    po, pmax, pnt = axial_limits(e702_section(), ksi(4), ksi(60))
    assert to_kip(pmax) == pytest.approx(347.60, rel=0.001)
    assert to_kip(pnt) == pytest.approx(-170.64, rel=0.001)
    assert to_kip(po) == pytest.approx(668.46, rel=0.001)


@pytest.mark.parametrize(("phiPn", "phiMn", "phi"), [
    (182.67, 64.62, 0.65),
    (-39.36, 47.14, 0.90),
])
def test_e702_design_strength_at_axial_load(phiPn, phiMn, phi):
    moment, got_phi, _ = flexural_strength(e702_section(), kip(phiPn), ksi(4), ksi(60))
    assert to_kft(moment) == pytest.approx(phiMn, rel=0.01)
    assert got_phi == pytest.approx(phi)


@pytest.mark.parametrize(("c", "Pn", "Mn"), [
    (17.37, 1312.64, 277.54),  # fs = 0
    (12.91, 856.27, 375.24),   # fs = -0.5 fy
    (10.28, 518.93, 407.73),   # balanced
    (6.51, 37.53, 330.30),     # εt = 0.005
    (6.256, 0.0, 320.11),      # pure bending
])
def test_structurepoint_round_column(c, Pn, Mn):
    n = nominal_strength(round_section(), inch(c), ksi(5), ksi(60))
    assert to_kip(n.Pn) == pytest.approx(Pn, rel=0.01, abs=1.0)
    assert to_kft(n.Mn) == pytest.approx(Mn, rel=0.01)


def test_structurepoint_round_axial_and_beta1():
    po, _, pnt = axial_limits(round_section(), ksi(5), ksi(60))
    assert to_kip(po) == pytest.approx(1902, rel=0.002)
    assert to_kip(pnt) == pytest.approx(-548.64, rel=0.001)
    assert beta1(ksi(5)) == pytest.approx(0.80)
    assert beta1(ksi(4)) == pytest.approx(0.85)
    assert beta1(ksi(10)) == pytest.approx(0.65)


def test_axial_load_outside_the_diagram_has_no_moment_strength():
    moment, _, _ = flexural_strength(e702_section(), kip(400), ksi(4), ksi(60))
    assert moment == 0.0


def _pedestal(**kwargs):
    defaults = dict(height=inch(36), tie_diameter=inch(0.5), tie_spacing=inch(12))
    defaults.update(kwargs)
    return Pedestal(**defaults)


def _bars(c=15.0, d=1.27):
    pts = sorted({(x, y) for x in (-c, -c / 3, c / 3, c) for y in (-c, -c / 3, c / 3, c)
                  if abs(x) == c or abs(y) == c})
    return [(inch(x), inch(y), inch(d)) for x, y in pts]


def by_id(results):
    return {r.id: r for r in results}


def test_pedestal_shear_matches_aci_table_22_5_5_1a():
    """V_c = (2√f'c + N_u/6A_g) b_w d and V_s = A_v f_yt d/s, φ = 0.75 (hand calculation)."""
    bars = _bars()
    results = by_id(pedestal_checks(_pedestal(), inch(36), inch(36), bars, ksi(4), kip(200),
                                    kip(50), 0.0, 0.0, 0.0, Method.LRFD))
    shear = results["base_plate.pedestal_shear"]
    d = 18 + 15
    bwd = 36 * d
    vc = (2 * math.sqrt(4000) + 200_000 / (6 * 36 * 36)) * bwd / 1000
    vs = 2 * math.pi * 0.5**2 / 4 * 60 * d / 12
    assert to_kip(shear.capacity) == pytest.approx(0.75 * (vc + vs), rel=0.001)


def test_pedestal_shear_without_ties_uses_equation_c():
    bars = _bars()
    ped = Pedestal(height=inch(36))
    results = by_id(pedestal_checks(ped, inch(36), inch(36), bars, ksi(4), kip(200),
                                    kip(50), 0.0, 0.0, 0.0, Method.LRFD))
    shear = results["base_plate.pedestal_shear"]
    assert "base_plate.pedestal_tie_spacing" not in results
    assert any("22.5.5.1(c)" in step.clause for step in shear.steps)


def test_pedestal_checks_list_and_base_moment():
    bars = _bars()
    results = by_id(pedestal_checks(_pedestal(), inch(36), inch(36), bars, ksi(4), kip(200),
                                    kip(20), 0.0, to_internal(100, "kip*ft", Kind.MOMENT),
                                    0.0, Method.LRFD))
    assert set(results) == {
        "base_plate.pedestal_slenderness", "base_plate.pedestal_reinforcement_min",
        "base_plate.pedestal_reinforcement_max", "base_plate.pedestal_axial",
        "base_plate.pedestal_flexure", "base_plate.pedestal_shear",
        "base_plate.pedestal_tie_spacing"}
    flexure = results["base_plate.pedestal_flexure"]
    assert to_kft(flexure.demand) == pytest.approx(100 + 20 * 3)  # M + V h
    assert results["base_plate.pedestal_slenderness"].demand == pytest.approx(1.0)
    rho = 12 * math.pi * 1.27**2 / 4 / 36**2
    assert results["base_plate.pedestal_reinforcement_min"].capacity == pytest.approx(rho)


def test_pedestal_biaxial_uses_linear_contour():
    bars = _bars()
    m = to_internal(100, "kip*ft", Kind.MOMENT)
    single = by_id(pedestal_checks(_pedestal(), inch(36), inch(36), bars, ksi(4), kip(200),
                                   0.0, 0.0, m, 0.0, Method.LRFD))
    both = by_id(pedestal_checks(_pedestal(), inch(36), inch(36), bars, ksi(4), kip(200),
                                 0.0, 0.0, m, m, Method.LRFD))
    ratio = single["base_plate.pedestal_flexure"].ratio
    assert both["base_plate.pedestal_flexure"].ratio == pytest.approx(2 * ratio, rel=1e-6)
    assert both["base_plate.pedestal_flexure"].kind is Kind.DIMENSIONLESS


def test_pedestal_tension_and_asd():
    bars = _bars()
    results = by_id(pedestal_checks(_pedestal(), inch(36), inch(36), bars, ksi(4), kip(-100),
                                    0.0, 0.0, 0.0, 0.0, Method.LRFD))
    axial = results["base_plate.pedestal_axial"]
    area = 12 * math.pi * 1.27**2 / 4
    assert to_kip(axial.capacity) == pytest.approx(0.9 * 60 * area, rel=1e-4)
    assert pedestal_checks(_pedestal(), inch(36), inch(36), bars, ksi(4), kip(100), 0.0, 0.0,
                           0.0, 0.0, Method.ASD) == []


def test_pedestal_rejects_unsupported_shapes():
    with pytest.raises(ValueError, match="not supported"):
        Pedestal(height=inch(36), shape="octagonal")
    data = json.loads((EXAMPLES / "base_plate_pedestal.ocnx").read_text(encoding="utf-8"))
    data["base_plate"]["pedestal"]["shape"] = "L"
    with pytest.raises(ValueError, match="rectangular"):
        Project.model_validate(data)


def test_round_edges_rectangle_is_inscribed():
    r, f, s2 = inch(20), inch(9.25), inch(6)
    e = round_edges(r, f, s2)
    assert math.hypot(f + e, s2 + e) == pytest.approx(r)


def test_round_pedestal_project_end_to_end():
    project = load_project(EXAMPLES / "base_plate_pedestal_round.ocnx")
    bp = project.base_plate_model()
    assert bp.pedestal_shape == "round"
    assert bp.pedestal_B == bp.pedestal_N
    edges = concrete_edges(bp)
    assert edges.left == pytest.approx(edges.bottom)
    forces = project.case_forces()
    combo = project.load_combinations()[1]
    from openconex.core.loads import combine
    results = by_id(check_base_plate(bp, combine(combo, forces), combo.method, combo.name))
    assert "base_plate.pedestal_flexure" in results
    a2 = results["base_plate.a2_over_a1"]
    k = 40 / math.hypot(24, 22)
    assert a2.capacity == pytest.approx(min(k * k, 4.0))


@pytest.mark.parametrize("name", ["base_plate_pedestal.ocnx", "base_plate_pedestal_round.ocnx"])
def test_pedestal_examples_pass(name):
    from openconex.report.builder import build_base_plate_report
    report = build_base_plate_report(load_project(EXAMPLES / name))
    assert report.ok
    ids = {r.id for r in report.results}
    assert "base_plate.pedestal_flexure" in ids
    assert any("ACI 318-19 §22" in a or "ACI 318-19 §22.2" in a or "columna corta" in a
               for a in report.assumptions)


def test_pedestal_input_validation():
    data = json.loads((EXAMPLES / "base_plate_pedestal.ocnx").read_text(encoding="utf-8"))
    broken = json.loads(json.dumps(data))
    broken["base_plate"]["pedestal_rebars"] = []
    with pytest.raises(ValueError, match="pedestal_rebars"):
        Project.model_validate(broken)
    broken = json.loads(json.dumps(data))
    del broken["base_plate"]["pedestal"]["tie_spacing"]
    with pytest.raises(ValueError, match="tie"):
        Project.model_validate(broken)
    broken = json.loads(json.dumps(data))
    broken["base_plate"]["pedestal"]["shape"] = "round"
    broken["base_plate"]["pedestal_B"] = "30 in"
    with pytest.raises(ValueError, match="diameter"):
        Project.model_validate(broken)


def test_pedestal_requires_plan_size():
    project = load_project(EXAMPLES / "base_plate_pedestal.ocnx")
    bp = dataclasses.replace(project.base_plate_model(), pedestal_B=None)
    with pytest.raises(ValueError, match="pedestal_N and pedestal_B"):
        check_base_plate(bp, Forces(P=kip(100)), Method.LRFD)
