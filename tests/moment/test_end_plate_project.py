# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Moment end-plate projects: file, envelope, report, command, drawing, 3D and window."""

import json
import os
from pathlib import Path

import ezdxf
import pytest
from pydantic import ValidationError

from openconex.cli import main
from openconex.connections.moment.fr_moment import check_moment_envelope
from openconex.io.project import Project, load_project
from openconex.report.builder import build_report
from openconex.units import Kind, from_internal

EXAMPLES = Path(__file__).parents[2] / "examples"
NAMES = ["moment_end_plate_extended", "moment_end_plate_flush", "moment_end_plate_8es"]


def governing(project):
    out = {}
    for r in check_moment_envelope(project.moment_model(), project.load_combinations(),
                                   project.case_forces()):
        if r.applicable and (r.id not in out or r.ratio > out[r.id].ratio):
            out[r.id] = r
    return out


def kip_in(m):
    return from_internal(m, Kind.MOMENT, "kip*in")


def test_extended_example_matches_dg16_4_2_1():
    """1.2(35) + 1.6(65) = 146 kip·ft = 1752 k-in., the 1750 k-in. of Example 4.2.1."""
    results = governing(load_project(EXAMPLES / "moment_end_plate_extended.ocnx"))
    lrfd = [r for r in check_moment_envelope(
        load_project(EXAMPLES / "moment_end_plate_extended.ocnx").moment_model(),
        load_project(EXAMPLES / "moment_end_plate_extended.ocnx").load_combinations(),
        load_project(EXAMPLES / "moment_end_plate_extended.ocnx").case_forces())
        if r.combo == "LRFD-2"]
    by_id = {r.id: r for r in lrfd}
    assert kip_in(by_id["moment.end_plate_yielding"].demand) == pytest.approx(1752, rel=1e-3)
    assert kip_in(by_id["moment.end_plate_yielding"].capacity) == pytest.approx(2108, rel=1e-2)
    assert kip_in(by_id["moment.end_plate_bolt_rupture"].capacity) == pytest.approx(2175,
                                                                                    rel=1e-2)
    assert all(r.ratio <= 1 for r in results.values())


def test_flush_example_matches_dg16_3_2_2():
    project = load_project(EXAMPLES / "moment_end_plate_flush.ocnx")
    lrfd = {r.id: r for r in check_moment_envelope(
        project.moment_model(), project.load_combinations(), project.case_forces())
        if r.combo == "LRFD-2"}
    assert kip_in(lrfd["moment.end_plate_yielding"].demand) == pytest.approx(600, rel=1e-3)
    assert kip_in(lrfd["moment.end_plate_yielding"].capacity) == pytest.approx(643, rel=1e-2)
    assert kip_in(lrfd["moment.end_plate_bolt_rupture"].capacity) == pytest.approx(658, rel=1e-2)


def _data(**changes):
    data = json.loads((EXAMPLES / "moment_end_plate_extended.ocnx").read_text(
        encoding="utf-8"))
    data["moment_connection"]["end_plate"].update(changes.pop("plate", {}))
    data["moment_connection"].update(changes.pop("connection", {}))
    data.update(changes)
    return data


@pytest.mark.parametrize(("data", "message"), [
    (_data(plate={"pext": None}), "needs end_plate.pext"),
    (_data(plate={"layout": "extended_1_2"}), "needs end_plate.pb"),
    (_data(plate={"layout": "flush_4_stiffened_between", "pb": "3 in"}), "end_plate.ps_o"),
    (_data(connection={"end_plate": None}), "needs end_plate"),
    (_data(connection={"type": "bolted_flange_plate"}), "needs web"),
    (_data(plate={"bolt": {"diameter": "3/4 in", "grade": "ASTM F3125 Gr. A490"}}),
     "snug-tight"),
    (_data(cases=[{"name": "D", "type": "D", "M": "10 kip*ft", "M_weak": "1 kip*ft"}]),
     "only V and M"),
])
def test_invalid_projects(data, message):
    with pytest.raises(ValidationError, match=message):
        Project.model_validate(data)


def test_axial_force_in_the_cases():
    data = _data(cases=[{"name": "D", "type": "D", "V": "10 kip", "M": "100 kip*ft",
                         "P": "-20 kip"}])
    report = build_report(Project.model_validate(data))
    assert report.case_headers[2:] == ["V", "M", "P"]
    yielding = next(r for r in report.results if r.id == "moment.end_plate_yielding"
                    and r.combo == "LRFD-1")
    # 1.4 (1200 + 20/2 × 23.625) k-in.
    assert kip_in(yielding.demand) == pytest.approx(1.4 * (1200 + 10 * 23.625), rel=1e-3)


@pytest.mark.parametrize("lang", ["es", "en"])
@pytest.mark.parametrize("name", NAMES)
def test_report(name, lang):
    project = load_project(EXAMPLES / f"{name}.ocnx")
    project.info.language = lang
    report = build_report(project)
    assert report.ok
    assert any("Design Guide 16" in code for code in report.codes)
    assert report.figures[0].key == "elevation"


def test_command_writes_the_outputs(tmp_path):
    out = tmp_path / "ep"
    assert main(["moment", str(EXAMPLES / "moment_end_plate_extended.ocnx"), "-o", str(out),
                 "--html", "--dxf"]) == 0
    doc = ezdxf.readfile(out.with_suffix(".dxf"))
    msp = doc.modelspace()
    # end plate, column flanges, beam and four bolt rows (symmetric 4E: 2 + 2)
    bolts = [e for e in msp.query("LWPOLYLINE") if e.dxf.layer == "MC-PERNO"]
    assert len(bolts) == 4
    assert out.with_suffix(".html").exists()


@pytest.mark.parametrize("layout", ["extended_4_stiffened", "flush_4_stiffened_between",
                                    "flush_4_stiffened_inside"])
def test_stiffeners_in_drawing_and_3d(layout, tmp_path):
    plate = {"layout": layout, "pb": "3 in", "ps_o": "1.375 in",
             "stiffener_thickness": "3/8 in", "ps": "1.5 in"}
    project = Project.model_validate(_data(plate=plate))
    from openconex.drawing.moment import moment_layout
    lay = moment_layout(project.moment_model())
    assert lay.stiffeners
    pytest.importorskip("OCP")
    from openconex.geometry3d.base_plate import write_step
    from openconex.geometry3d.moment import moment_parts
    parts = moment_parts(project.moment_model())
    assert any(p.name.startswith("stiffener") for p in parts)
    assert write_step(parts, tmp_path / "x.step").stat().st_size > 0


@pytest.mark.parametrize("name", NAMES)
def test_3d_model(name, tmp_path):
    pytest.importorskip("OCP")
    from openconex.geometry3d.base_plate import write_step
    from openconex.geometry3d.moment import moment_parts
    parts = moment_parts(load_project(EXAMPLES / f"{name}.ocnx").moment_model())
    names = {p.name for p in parts}
    assert {"beam", "column", "end_plate"} <= names
    assert "web_plate" not in names
    assert write_step(parts, tmp_path / "x.step").stat().st_size > 0


def test_window_round_trip_and_calculate(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from openconex.gui.moment import MomentWindow
    QApplication.instance() or QApplication([])
    for name in NAMES:
        path = EXAMPLES / f"{name}.ocnx"
        window = MomentWindow(load_project(path), path)
        original = load_project(path)
        project = window.project_from_form()
        assert project.moment_connection.end_plate == original.moment_connection.end_plate
        assert project.moment_connection.web is None
        assert project.cases == original.cases
        assert window.calculate() and window.report.ok
        assert window.export("dxf", ".dxf", tmp_path / name).exists()
        assert window.save_to(tmp_path / f"{name}.ocnx")
    # switch a flange plate project to an end plate in the form
    window = MomentWindow()
    window.type.setCurrentIndex(window.type.findData("end_plate"))
    for key, value in (("width", "8 in"), ("thickness", "1/2 in"), ("gage", "3 in"),
                       ("pf", "1.75 in"), ("pf_o", "2.5 in"), ("pext", "5 in")):
        window._ep[key].setText(value)
    assert window.calculate()
    assert window.project.moment_connection.end_plate.layout.value == "extended_4"


def test_8es_example_matches_dg4():
    """DG4 4.4: Y_c = 377.7 in. with 1/2 in. continuity plates (t_fc,req = 0.75 in.), and the
    plate force F_fu - min φR_n = 399 - 284 = 115 kips (LRFD-2: M = 8082 k-in.)."""
    project = load_project(EXAMPLES / "moment_end_plate_8es.ocnx")
    lrfd = {r.id: r for r in check_moment_envelope(
        project.moment_model(), project.load_combinations(), project.case_forces())
        if r.combo == "LRFD-2"}
    bending = lrfd["moment.column_flange_bending"]
    assert from_internal(bending.demand, Kind.LENGTH, "in") == pytest.approx(0.75, abs=0.01)
    plates = lrfd["moment.continuity_plates"]
    assert from_internal(plates.demand, Kind.FORCE, "kip") == pytest.approx(115, rel=1e-2)
    assert not lrfd["moment.column_web_crippling"].applicable
    pytest.importorskip("OCP")
    from openconex.geometry3d.moment import moment_parts
    names = {p.name for p in moment_parts(project.moment_model())}
    assert {"continuity_plate1a", "continuity_plate2b", "stiffener1"} <= names
    assert sum(n.startswith("bolt") for n in names) == 16
