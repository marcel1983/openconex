# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Bolted beam and column splices (F7) against the independent calculation in
docs/verificacion/calculos/empalmes.py, plus behaviour and project checks."""

import dataclasses
import json
import runpy
from pathlib import Path

import pytest

from openconex.cli import main
from openconex.connections.splice.splice import (
    check_beam_splice,
    check_column_splice,
    filler_factor,
)
from openconex.core.loads import Method
from openconex.io.project import Project, load_project
from openconex.units import Kind, from_internal, to_internal

ROOT = Path(__file__).parents[2]
BEAM = ROOT / "examples" / "splice_beam_bolted.ocnx"
COLUMN = ROOT / "examples" / "splice_column_fillers.ocnx"
INDEPENDENT = runpy.run_path(str(ROOT / "docs" / "verificacion" / "calculos" / "empalmes.py"))


def inch(v):
    return to_internal(v, "in", Kind.LENGTH)


def kip(v):
    return to_internal(v, "kip", Kind.FORCE)


def kip_ft(v):
    return to_internal(v, "kip*ft", Kind.MOMENT)


def by_id(results):
    return {r.id.removeprefix("splice."): r for r in results}


def in_kips(r):
    unit = {Kind.FORCE: "kip", Kind.MOMENT: "kip*ft"}.get(r.kind, "in")
    return from_internal(r.capacity, r.kind, unit)


@pytest.fixture(scope="module")
def beam_results():
    model = load_project(BEAM).splice_model()
    return by_id(check_beam_splice(model, kip(60), kip_ft(300), kip(-20), Method.LRFD))


@pytest.fixture(scope="module")
def column_results():
    model = load_project(COLUMN).splice_model()
    return by_id(check_column_splice(model, 0.0, kip_ft(150), kip(200), Method.LRFD,
                                     V_weak=kip(20)))


BEAM_KEYS = ["flange_bolts", "flange_plate_tension_yielding", "flange_plate_tension_rupture",
             "flange_plate_compression", "beam_flange_block_shear", "beam_flexural_rupture",
             "web_plate_shear_yielding", "web_plate_shear_rupture", "web_plate_block_shear"]


@pytest.mark.parametrize("key", BEAM_KEYS)
def test_beam_splice_matches_the_independent_calculation(beam_results, key):
    expected = INDEPENDENT["beam_splice"]()
    assert in_kips(beam_results[key]) == pytest.approx(expected[key], rel=0.005), key


def test_beam_splice_flange_forces_and_web(beam_results):
    expected = INDEPENDENT["beam_splice"]()
    r = beam_results
    assert from_internal(r["flange_bolts"].demand, Kind.FORCE, "kip") == \
        pytest.approx(expected["T"], rel=1e-4)
    assert from_internal(r["flange_plate_compression"].demand, Kind.FORCE, "kip") == \
        pytest.approx(expected["C"], rel=1e-4)
    assert from_internal(r["web_plate_flexural_yielding"].demand, Kind.MOMENT, "kip*in") == \
        pytest.approx(expected["web_plate_moment"], rel=1e-4)
    for key in ("web_plate_flexural_yielding", "web_plate_flexural_rupture"):
        cap = from_internal(r[key].capacity, Kind.MOMENT, "kip*in")
        assert cap == pytest.approx(expected[key], rel=0.005), key
    assert from_internal(r["web_plate_tension_yielding"].demand, Kind.FORCE, "kip") == \
        pytest.approx(-expected["web_axial"], rel=1e-3)
    assert r["beam_flexural_rupture"].applicable == bool(
        expected["beam_flexural_rupture_applies"])
    assert all(c.status.value in ("ok", "n/a") for c in r.values())


COLUMN_KEYS = ["upper_flange_bolts", "lower_flange_bolts", "flange_plate_tension_yielding",
               "flange_plate_tension_rupture", "column_flange_bearing", "column_web_bearing"]


@pytest.mark.parametrize("key", COLUMN_KEYS)
def test_column_splice_matches_the_independent_calculation(column_results, key):
    expected = INDEPENDENT["column_splice"]()
    assert in_kips(column_results[key]) == pytest.approx(expected[key], rel=0.005), key


def test_column_splice_demands(column_results):
    expected = INDEPENDENT["column_splice"]()
    r = column_results
    assert from_internal(r["upper_flange_bolts"].demand, Kind.FORCE, "kip") == \
        pytest.approx(expected["upper_flange_bolts_demand"], rel=1e-4)
    assert from_internal(r["column_flange_bearing"].demand, Kind.FORCE, "kip") == \
        pytest.approx(expected["C"], rel=1e-4)
    assert not r["flange_plate_compression"].applicable  # finished ends: bearing
    # 0.35 in. fillers on the upper (shallower) column: 0.96 on its bolt shear
    assert expected["filler_factor"] == pytest.approx(0.96)
    assert r["filler_thickness"].demand == pytest.approx(inch(0.35))


def test_filler_factor():
    assert filler_factor(inch(0.25)) == 1.0
    assert filler_factor(inch(0.5)) == pytest.approx(0.9)
    assert filler_factor(inch(0.75)) == pytest.approx(0.85)
    assert filler_factor(inch(1.0)) == pytest.approx(0.85)
    assert filler_factor(inch(1.0), developed=True) == 1.0


def test_net_tension_column_loads_both_flanges():
    model = load_project(COLUMN).splice_model()
    r = by_id(check_column_splice(model, 0.0, 0.0, kip(-100), Method.LRFD))
    assert from_internal(r["flange_plate_tension_yielding"].demand, Kind.FORCE, "kip") == \
        pytest.approx(50.0)
    assert r["column_flange_bearing"].demand == 0.0


def test_unfinished_ends_check_the_plates_in_compression():
    model = dataclasses.replace(load_project(COLUMN).splice_model(), finished_ends=False,
                                gap=inch(0.25))
    r = by_id(check_column_splice(model, 0.0, kip_ft(50), kip(300), Method.LRFD))
    assert r["flange_plate_compression"].applicable
    assert "column_flange_bearing" not in r
    assert r["upper_flange_bolts"].demand > r["flange_plate_tension_yielding"].demand


def test_no_flange_overlap_fails_bearing():
    project = load_project(COLUMN)
    project.splice.upper = "W12X65"  # d = 12.1 in.: flanges miss the W14X132 flanges
    r = by_id(check_column_splice(project.splice_model(), 0.0, kip_ft(10), kip(100),
                                  Method.LRFD))
    assert r["column_flange_bearing"].capacity == 0.0
    assert r["column_flange_bearing"].status.value == "ng"


def test_asd_is_consistent_with_lrfd():
    model = load_project(BEAM).splice_model()
    lrfd = by_id(check_beam_splice(model, kip(60), kip_ft(300), 0.0, Method.LRFD))
    asd = by_id(check_beam_splice(model, kip(40), kip_ft(200), 0.0, Method.ASD))
    for key in ("flange_plate_tension_yielding", "web_plate_shear_rupture"):
        ratio = lrfd[key].capacity / asd[key].capacity
        assert ratio == pytest.approx(1.5, rel=0.01), key


def test_inner_plates_put_the_bolts_in_double_shear():
    project = load_project(BEAM)
    single = project.model_copy(deep=True)
    single.splice.flange.inner_width = None
    single.splice.flange.inner_thickness = None
    two = by_id(check_beam_splice(project.splice_model(), 0, kip_ft(300), 0, Method.LRFD))
    one = by_id(check_beam_splice(single.splice_model(), 0, kip_ft(300), 0, Method.LRFD))
    assert two["flange_bolts"].capacity > one["flange_bolts"].capacity
    assert "inner_plate_block_shear" in two and "inner_plate_block_shear" not in one


def _data(path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize(("change", "message"), [
    (lambda d: d["splice"].pop("web"), "needs web"),
    (lambda d: d["cases"][0].update(V_weak="5 kip"), "only P, V and M"),
    (lambda d: d["cases"][0].update(M_weak="5 kip*ft"), "M_weak"),
    (lambda d: d["splice"]["flange"].pop("inner_thickness"), "inner_width/inner_thickness"),
])
def test_beam_project_validation(change, message):
    data = _data(BEAM)
    change(data)
    with pytest.raises(ValueError, match=message):
        Project.model_validate(data)


def test_column_project_needs_web_plates_for_shear():
    data = _data(COLUMN)
    data["splice"].pop("web")
    with pytest.raises(ValueError, match="needs web plates"):
        Project.model_validate(data)
    for case in data["cases"]:
        case.pop("V", None)
    assert Project.model_validate(data).splice_model().web is None


def test_only_one_connection_block():
    data = _data(BEAM)
    data["moment_connection"] = _data(ROOT / "examples" / "moment_bolted_flange_plate.ocnx")[
        "moment_connection"]
    with pytest.raises(ValueError, match="exactly one"):
        Project.model_validate(data)


@pytest.mark.parametrize("example", [BEAM, COLUMN], ids=lambda p: p.stem)
def test_cli_writes_the_outputs(example, tmp_path, capsys):
    out = tmp_path / example.stem
    assert main(["splice", str(example), "-o", str(out), "--html", "--docx", "--dxf",
                 "--lang", "en"]) == 0
    for ext in (".html", ".docx", ".dxf"):
        assert out.with_suffix(ext).exists()
    assert "splice" in capsys.readouterr().out.lower()


def test_other_commands_reject_splices(capsys):
    assert main(["moment", str(BEAM)]) == 2
    assert "openconex splice" in capsys.readouterr().err


def test_report_and_drawing(tmp_path):
    import ezdxf

    from openconex.drawing.splice import write_splice_dxf
    from openconex.report.builder import build_report

    for example in (BEAM, COLUMN):
        project = load_project(example)
        report = build_report(project)
        assert report.ok
        assert report.figures
        path = write_splice_dxf(project.splice_model(), tmp_path / f"{example.stem}.dxf",
                                project.info.unit_system())
        layers = {e.dxf.layer for e in ezdxf.readfile(path).modelspace()}
        assert {"SP-PERFIL", "SP-PLACA", "SP-PERNO"} <= layers
    assert "SP-RELLENO" in layers  # the column example has fillers


def test_3d_parts():
    pytest.importorskip("OCP")
    from openconex.geometry3d.splice import splice_parts

    beam = {p.name for p in splice_parts(load_project(BEAM).splice_model())}
    assert {"member_1", "member_2", "flange_plate_top", "web_plate_a",
            "inner_plate_top_a"} <= beam
    assert sum(n.startswith("flange_bolt") for n in beam) == 32
    column = {p.name for p in splice_parts(load_project(COLUMN).splice_model())}
    assert {"filler_top", "filler_bottom"} <= column
