# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Shear lug in the complete base plate check (AISC DG1 3rd ed. Example 4.7-5)."""

import dataclasses

import pytest

from openconex.connections.base_plate.check import BasePlate, ShearLug, check_base_plate
from openconex.core.loads import Forces, Method
from openconex.core.model import BoltSpec, IShape
from openconex.i18n import LANGUAGES, catalog
from openconex.kernel.anchors import Edges
from openconex.units import Kind, to_internal


def inch(v):
    return to_internal(v, "in", Kind.LENGTH)


def kip(v):
    return to_internal(v, "kip", Kind.FORCE)


def kip_in(v):
    return to_internal(v, "kip*in", Kind.MOMENT)


W14X90 = IShape(name="W14X90", d=inch(14.0), bf=inch(14.5), tf=inch(0.710), tw=inch(0.440),
                k_des=inch(1.31))
# DG1 Example 4.7-5: 15 x 15 in. plate, four 3/4 in. F1554 Gr. 36 rods on an 8.5 in.
# pattern, hef = 12 in., 8 x 1 in. lug with 2 in. embedment below 2 in. of grout,
# 5/16 in. fillet welds, 14.5 in. to the edge of the wall in the shear direction
LUG = ShearLug(width=inch(8), embedment=inch(2), thickness=inch(1), weld=inch(0.3125),
               grout=inch(2), ca1=inch(14.5))
PLATE = BasePlate(column=W14X90, N=inch(15), B=inch(15), tp=inch(1.5),
                  fc=to_internal(4, "ksi", Kind.STRESS),
                  rod=BoltSpec(diameter=inch(0.75), grade="ASTM F1554 Gr. 36"), f=inch(4.25),
                  rods_per_side=2, rod_spacing=inch(8.5), hef=inch(12), A2_over_A1=4.0,
                  edges=Edges(bottom=inch(10.8)), shear_lug=LUG)


def by_id(results):
    return {r.id: r for r in results}


@pytest.mark.parametrize(("method", "V", "expected"), [
    (Method.LRFD, 25.0, {"base_plate.lug_shear_yielding": 240, "base_plate.lug_shear_rupture": 234,
                         "anchor.shear_lug_bearing": 70.9, "anchor.shear_lug_breakout": 26.1}),
    (Method.ASD, 16.0, {"base_plate.lug_shear_yielding": 160,
                        "base_plate.lug_shear_rupture": 156}),
])
def test_dg1_4_7_5(method, V, expected):
    r = by_id(check_base_plate(PLATE, Forces(V2=kip(V)), method, "W"))
    for key, value in expected.items():
        assert r[key].capacity == pytest.approx(kip(value), rel=0.01), key
    weld = r["base_plate.lug_weld"]
    weld_demand, weld_strength = (7.91, 10.4) if method is Method.LRFD else (5.06, 6.95)
    assert weld.demand == pytest.approx(kip(weld_demand) / inch(1), rel=0.01)
    assert weld.capacity == pytest.approx(kip(weld_strength) / inch(1), rel=0.01)
    flexure = r["base_plate.lug_flexural_yielding"]
    assert flexure.demand == pytest.approx(kip_in(3.00 * V), rel=1e-6)
    assert flexure.capacity == pytest.approx(kip_in(90.0 if method is Method.LRFD else 59.9),
                                             rel=0.01)
    assert r["base_plate.lug_anchor_embedment"].status.value == "ok"
    # the lug takes the shear: no friction or rod shear
    assert "base_plate.friction" not in r and "anchor.steel_shear" not in r


def test_dg1_4_7_5_lug_moment_on_the_plate():
    """M = Vu e = 75 kip·in resisted by bearing and rods: T = 6.41 kip (DG1)."""
    r = by_id(check_base_plate(PLATE, Forces(V2=kip(25)), Method.LRFD))
    rods = r["anchor.steel_tension"]
    assert rods.demand == pytest.approx(kip(6.41 / 2), rel=0.06)  # DG1 rounds Y


def test_psi_brg_from_axial_load():
    comp = by_id(check_base_plate(PLATE, Forces(P=kip(100), V2=kip(25)), Method.LRFD))
    plain = by_id(check_base_plate(PLATE, Forces(V2=kip(25)), Method.LRFD))
    ratio = comp["anchor.shear_lug_bearing"].capacity / plain["anchor.shear_lug_bearing"].capacity
    assert ratio == pytest.approx(min(1 + 4 * 100 / (15 * 15 * 4), 2.0))
    uplift = by_id(check_base_plate(PLATE, Forces(P=kip(-20), V2=kip(25)), Method.LRFD))
    assert uplift["anchor.shear_lug_bearing"].capacity < plain["anchor.shear_lug_bearing"].capacity


def test_direction_of_the_lug():
    forces = Forces(P=kip(50), V2=kip(10), V3=kip(5))
    strong = by_id(check_base_plate(PLATE, forces, Method.LRFD))
    assert strong["anchor.shear_lug_bearing"].demand == pytest.approx(kip(10))
    assert strong["base_plate.friction"].demand == pytest.approx(kip(5))  # V3 to friction
    both = check_base_plate(dataclasses.replace(
        PLATE, shear_lug=dataclasses.replace(LUG, direction="both")), forces, Method.LRFD)
    demands = sorted(c.demand for c in both if c.id == "anchor.shear_lug_bearing")
    assert demands == [pytest.approx(kip(5)), pytest.approx(kip(10))]
    assert not any(c.id == "base_plate.friction" for c in both)


def test_short_anchors_for_the_lug():
    short = dataclasses.replace(PLATE, hef=inch(4))
    r = by_id(check_base_plate(short, Forces(V2=kip(25)), Method.LRFD))
    assert r["base_plate.lug_anchor_embedment"].status.value == "ng"


@pytest.mark.parametrize("lang", LANGUAGES)
def test_lug_checks_have_titles(lang):
    texts = catalog(lang)
    for check in check_base_plate(PLATE, Forces(V2=kip(25)), Method.LRFD):
        assert check.text_id in texts, check.text_id


def test_example_project_with_shear_lug(tmp_path):
    from pathlib import Path

    from openconex.cli import main
    from openconex.io.project import load_project

    path = Path(__file__).parents[2] / "examples" / "base_plate_shear_lug.ocnx"
    project = load_project(path)
    lug = project.base_plate_model().shear_lug
    assert (lug.width, lug.grout, lug.ca1) == (pytest.approx(inch(8)), pytest.approx(inch(2)),
                                               pytest.approx(inch(14.5)))
    assert main(["baseplate", str(path), "-o", str(tmp_path / "lug"), "--html"]) == 0
    html = (tmp_path / "lug.html").read_text(encoding="utf-8")
    assert "Llave de corte: soldadura a la placa" in html and "h_sl" in html
