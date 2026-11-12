# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Moment connection projects: file, envelope, report, command, drawing, 3D and window."""

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
from openconex.units import Kind, to_internal

EXAMPLES = Path(__file__).parents[2] / "examples"


def kip(v):
    return to_internal(v, "kip", Kind.FORCE)


def governing(project):
    out = {}
    for r in check_moment_envelope(project.moment_model(), project.load_combinations(),
                                   project.case_forces()):
        if r.applicable and (r.id not in out or r.ratio > out[r.id].ratio):
            out[r.id] = r
    return out


def test_bolted_example_matches_ii_b_1():
    results = governing(load_project(EXAMPLES / "moment_bolted_flange_plate.ocnx"))
    bolts = results["moment.flange_bolts"]
    assert bolts.combo == "LRFD-2" and bolts.demand == pytest.approx(kip(168), rel=0.01)
    assert bolts.capacity == pytest.approx(kip(194), rel=0.01)
    bending = results["moment.column_flange_local_bending"]  # ASD-2 governs: 108/114
    expected = 171 if bending.combo.startswith("LRFD") else 114
    assert bending.capacity == pytest.approx(kip(expected), rel=0.01)


def test_welded_example_matches_ii_b_2():
    results = governing(load_project(EXAMPLES / "moment_welded_flange_plate.ocnx"))
    weld = results["moment.top_plate_weld_to_beam"]
    assert weld.capacity == pytest.approx(kip(169), rel=0.01)
    assert weld.ratio == pytest.approx(168 / 169, rel=0.01)


def _data(**changes):
    data = json.loads((EXAMPLES / "moment_bolted_flange_plate.ocnx").read_text(
        encoding="utf-8"))
    data["moment_connection"].update(changes.pop("connection", {}))
    data.update(changes)
    return data


@pytest.mark.parametrize(("data", "message"), [
    (_data(connection={"bolt": None}), "needs bolt"),
    (_data(connection={"type": "welded_flange_plate"}), "needs"),
    (_data(cases=[{"name": "D", "type": "D", "V": "7 kip", "P": "5 kip"}]), "only V and M"),
    (_data(shear_connection={"type": "seated", "beam": "W16X50", "support": "W14X90",
                             "length": "8 in", "thickness": "5/8 in", "leg": "4 in"}),
     "exactly one"),
])
def test_invalid_projects(data, message):
    with pytest.raises(ValidationError, match=message):
        Project.model_validate(data)


def test_welded_flange_type_needs_no_plates():
    data = _data(connection={"type": "welded_flange", "top": None, "bolt": None, "rows": 0})
    report = build_report(Project.model_validate(data))
    assert not any("placa de ala" in row.cells[0].lower() for row in report.summary)
    # P_f = M/(d - t_f) = 173 kips exceeds the 171 kips of flange local bending: II.B-3
    # defers to the checks of II.B-1, made with the plate force M/(d + t_p) = 161 kips.
    bending = next(r for r in report.results if r.id == "moment.column_flange_local_bending"
                   and r.combo == "LRFD-2")
    assert bending.demand == pytest.approx(kip(252 * 12 / (18.0 - 0.570)), rel=0.01)


@pytest.mark.parametrize("lang", ["es", "en"])
def test_report(lang):
    project = load_project(EXAMPLES / "moment_welded_flange_plate.ocnx")
    project.info.language = lang
    report = build_report(project)
    assert report.ok and report.case_headers[2:] == ["V", "M"]
    assert report.figures[0].key == "elevation"


def test_command_writes_the_outputs(tmp_path):
    out = tmp_path / "m"
    assert main(["moment", str(EXAMPLES / "moment_bolted_flange_plate.ocnx"), "-o", str(out),
                 "--html", "--dxf"]) == 0
    doc = ezdxf.readfile(out.with_suffix(".dxf"))
    assert len(doc.modelspace().query("CIRCLE")) == 3  # web bolts
    assert {"MC-VIGA", "MC-COLUMNA", "MC-PLACA"} <= {layer.dxf.name for layer in doc.layers}
    assert main(["moment", str(EXAMPLES / "shear_single_plate.ocnx")]) == 2
    assert main(["shear", str(EXAMPLES / "moment_bolted_flange_plate.ocnx")]) == 2
    assert main(["baseplate", str(EXAMPLES / "moment_bolted_flange_plate.ocnx")]) == 2


@pytest.mark.parametrize("name", ["moment_bolted_flange_plate", "moment_welded_flange_plate"])
def test_3d_model(name, tmp_path):
    pytest.importorskip("OCP")
    from openconex.geometry3d.base_plate import write_step
    from openconex.geometry3d.moment import moment_parts
    parts = moment_parts(load_project(EXAMPLES / f"{name}.ocnx").moment_model())
    assert {"beam", "column", "web_plate", "top_plate", "bottom_plate"} <= {p.name for p in parts}
    assert write_step(parts, tmp_path / "x.step").stat().st_size > 0


def test_window_round_trip_and_calculate(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from openconex.gui.moment import MomentWindow
    QApplication.instance() or QApplication([])
    for name in ("moment_bolted_flange_plate", "moment_welded_flange_plate"):
        path = EXAMPLES / f"{name}.ocnx"
        window = MomentWindow(load_project(path), path)
        original = load_project(path)
        project = window.project_from_form()
        assert project.moment_connection.type == original.moment_connection.type
        assert project.cases == original.cases
        assert window.calculate() and window.report.ok
        assert window.export("dxf", ".dxf", tmp_path / name).exists()
        assert window.save_to(tmp_path / f"{name}.ocnx")
    window = MomentWindow()
    assert window.calculate()
