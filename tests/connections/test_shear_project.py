# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Shear connection projects: file, engine dispatch, report, command and drawing."""

import json
from pathlib import Path

import ezdxf
import pytest
from pydantic import ValidationError

from openconex.cli import main
from openconex.connections.shear.check import check_shear_envelope
from openconex.io.project import Project, load_project
from openconex.report.builder import build_report
from openconex.units import Kind, to_internal

EXAMPLES = Path(__file__).parents[2] / "examples"


def kip(v):
    return to_internal(v, "kip", Kind.FORCE)


def governing(project):
    out = {}
    for r in check_shear_envelope(project.shear_model(), project.load_combinations(),
                                  project.case_forces()):
        if r.id not in out or r.ratio > out[r.id].ratio:
            out[r.id] = r
    return out


def test_single_plate_example_matches_ii_a_17a():
    results = governing(load_project(EXAMPLES / "shear_single_plate.ocnx"))
    bolts = results["single_plate.bolts"]
    assert bolts.combo == "LRFD-2" and bolts.demand == pytest.approx(kip(49.6))
    assert bolts.capacity == pytest.approx(kip(58.5), rel=0.01)
    assert results["single_plate.block_shear"].capacity == pytest.approx(kip(65.3), rel=0.01)


def test_coped_double_angle_example_matches_ii_a_4():
    results = governing(load_project(EXAMPLES / "shear_double_angle_coped.ocnx"))
    assert results["coped_beam.block_shear"].capacity == pytest.approx(kip(68.6), rel=0.01)
    assert results["coped_beam.shear_yielding"].capacity == pytest.approx(kip(170), rel=0.01)
    assert results["double_angle.bolts_beam"].demand == pytest.approx(kip(60))


def test_seated_example_matches_ii_a_12a():
    project = load_project(EXAMPLES / "shear_seated_ii_a_12a.ocnx")
    checks = list(check_shear_envelope(project.shear_model(), project.load_combinations(),
                                       project.case_forces()))

    def find(check_id, method):
        return next(r for r in checks if r.id == check_id and r.combo.startswith(method))

    assert find("seated.flexural_yielding", "LRFD").capacity == pytest.approx(
        kip(90.0), rel=0.01)
    assert find("seated.shear_yielding", "LRFD").capacity == pytest.approx(
        kip(108.0), rel=0.01)
    assert find("seated.bolts", "LRFD").capacity == pytest.approx(kip(71.6), rel=0.01)
    assert find("seated.bearing_length", "LRFD").demand == pytest.approx(
        to_internal(1.03, "in", Kind.LENGTH), rel=1e-3)


def test_single_plate_coped_example_matches_ii_a_18():
    results = governing(load_project(EXAMPLES / "shear_single_plate_coped.ocnx"))
    bolts = results["single_plate.bolts"]
    assert bolts.demand == pytest.approx(kip(39.8), rel=0.01)
    assert bolts.capacity == pytest.approx(kip(58.5), rel=0.01)
    assert results["single_plate.block_shear"].capacity == pytest.approx(kip(65.3),
                                                                        rel=0.01)
    assert results["coped_beam.block_shear"].capacity == pytest.approx(kip(88.2),
                                                                      rel=0.01)
    assert all(result.status.value == "ok" for result in results.values())


def _data(**changes):
    data = json.loads((EXAMPLES / "shear_single_plate.ocnx").read_text(encoding="utf-8"))
    data["shear_connection"].update(changes.pop("connection", {}))
    data.update(changes)
    return data


def test_axial_tension_uses_the_part_12_checks():
    data = _data(cases=[{"name": "D", "type": "D", "V": "8 kip", "P": "-10 kip"},
                        {"name": "L", "type": "L", "V": "25 kip", "P": "-20 kip"}])
    ids = set(governing(Project.model_validate(data)))
    assert {"single_plate.tension_yielding", "single_plate.interaction_rupture"} <= ids


def test_axial_compression_on_a_single_plate_is_checked():
    data = _data(cases=[{"name": "D", "type": "D", "V": "8 kip", "P": "5 kip"}])
    results = governing(Project.model_validate(data))
    assert "shear_connection.axial_compression" not in results
    assert results["single_plate.compression"].status.value == "ok"


def test_axial_compression_on_a_seat_is_reported_as_not_verified():
    data = _data(connection={"type": "seated", "length": "8 in", "thickness": "5/8 in",
                             "leg": "4 in"},
                 cases=[{"name": "D", "type": "D", "V": "8 kip", "P": "5 kip"}])
    check = governing(Project.model_validate(data))["shear_connection.axial_compression"]
    assert check.status.value == "ng"


def test_axial_tension_on_a_seat_is_reported_as_not_verified():
    data = _data(connection={"type": "seated", "length": "8 in", "thickness": "5/8 in",
                             "leg": "4 in"},
                 cases=[{"name": "D", "type": "D", "V": "8 kip", "P": "-5 kip"}])
    check = governing(Project.model_validate(data))["shear_connection.axial_unsupported"]
    assert check.status.value == "ng"


@pytest.mark.parametrize(("data", "message"), [
    (_data(connection={"a": None}), "needs a"),
    (_data(base_plate={"column": "W12X96", "fc": "4 ksi"}), "exactly one"),
    (_data(cases=[{"name": "D", "type": "D", "V": "8 kip", "M": "10 kip*in"}]), "only V and P"),
    (_data(connection={"grade": "unknown"}), "unknown material"),
])
def test_invalid_projects(data, message):
    with pytest.raises(ValidationError, match=message):
        Project.model_validate(data)


@pytest.mark.parametrize("lang", ["es", "en"])
def test_report_and_drawing(lang, tmp_path):
    project = load_project(EXAMPLES / "shear_double_angle_coped.ocnx")
    project.info.language = lang
    report = build_report(project)
    assert report.ok and report.case_headers[2:] == ["V", "P"]
    assert any(f.key == "elevation" for f in report.figures)
    assert len(report.summary) == 10


def test_command_writes_the_outputs(tmp_path, capsys):
    out = tmp_path / "sp"
    code = main(["shear", str(EXAMPLES / "shear_single_plate.ocnx"), "-o", str(out), "--html",
                 "--docx", "--dxf"])
    assert code == 0
    for suffix in (".html", ".docx", ".dxf"):
        assert out.with_suffix(suffix).exists()
    doc = ezdxf.readfile(out.with_suffix(".dxf"))
    assert len(doc.modelspace().query("CIRCLE")) == 4
    texts = [entity.dxf.text for entity in doc.modelspace().query("TEXT")]
    assert any("LISTA DE MATERIALES" in text for text in texts)
    assert any("Placa de corte" in text for text in texts)
    assert any("SOLDADURAS" in text for text in texts)
    assert "single_plate.bolts" not in capsys.readouterr().err


def test_commands_refuse_the_other_project_type(tmp_path):
    assert main(["baseplate", str(EXAMPLES / "shear_single_plate.ocnx")]) == 2
    assert main(["shear", str(EXAMPLES / "base_plate_generic_w.ocnx")]) == 2


@pytest.mark.parametrize("kind", ["double_angle", "single_plate", "extended_single_plate",
                                  "end_plate", "seated", "stiffened_seat"])
def test_every_type_draws(kind, tmp_path):
    fields = {
        "double_angle": {"leh_support": "1.25 in", "leh": "1.25 in"},
        "extended_single_plate": {"lines": 2, "gage": "3 in", "a": "9 in"},
        "end_plate": {},
        "seated": {"leg": "4 in", "thickness": "5/8 in", "length": "8 in"},
        "stiffened_seat": {"width": "7 in", "length": "15 in", "thickness": "5/8 in",
                           "weld": "5/16 in"},
    }.get(kind, {})
    project = Project.model_validate(_data(connection={"type": kind, **fields}))
    from openconex.drawing.shear import write_shear_dxf
    path = write_shear_dxf(project.shear_model(), tmp_path / "x.dxf",
                           project.info.unit_system())
    assert path.exists()
    assert build_report(project).summary


@pytest.mark.parametrize("name", ["shear_single_plate", "shear_double_angle_coped"])
def test_3d_model(name, tmp_path):
    pytest.importorskip("OCP")
    from openconex.geometry3d.base_plate import write_step
    from openconex.geometry3d.shear import shear_parts
    parts = shear_parts(load_project(EXAMPLES / f"{name}.ocnx").shear_model())
    assert {"beam", "support"} <= {p.name for p in parts}
    assert write_step(parts, tmp_path / "x.step").stat().st_size > 0


@pytest.mark.parametrize(("kind", "expected"), [
    ("seated", "L 4 in x 4 in x 0.25 in x 4 in"),
    ("stiffened_seat", "Placa de asiento 0.375 in x 7 in x 8 in"),
])
def test_seat_details_are_in_the_bill_of_materials(kind, expected, tmp_path):
    from openconex.drawing.shear import write_shear_dxf
    fields = {
        "seated": {"leg": "4 in", "thickness": "5/8 in", "length": "8 in"},
        "stiffened_seat": {"width": "7 in", "length": "15 in", "thickness": "5/8 in",
                           "weld": "5/16 in"},
    }[kind]
    project = Project.model_validate(_data(connection={"type": kind, **fields}))
    path = write_shear_dxf(project.shear_model(), tmp_path / "x.dxf",
                           project.info.unit_system())
    texts = [entity.dxf.text for entity in ezdxf.readfile(path).modelspace().query("TEXT")]
    assert any(expected in text for text in texts)


@pytest.mark.parametrize("kind", ["seated", "stiffened_seat"])
def test_3d_seats_include_the_stability_angle(kind):
    pytest.importorskip("OCP")
    from openconex.geometry3d.shear import shear_parts
    fields = {
        "seated": {"leg": "4 in", "thickness": "5/8 in", "length": "8 in"},
        "stiffened_seat": {"width": "7 in", "length": "15 in", "thickness": "5/8 in",
                           "weld": "5/16 in"},
    }[kind]
    project = Project.model_validate(_data(connection={"type": kind, **fields}))
    names = {p.name for p in shear_parts(project.shear_model())}
    assert {"beam", "support", "top_angle"} <= names
    if kind == "stiffened_seat":
        assert "seat" in names
