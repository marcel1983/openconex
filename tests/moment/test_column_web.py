# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Moment connections to the column web (AISC Design Guide 13, Appendix D; Ferrell, 1998).

The Appendix gives detailing rules and the force transfer, not a worked example: the
plate thickness and extension rules are checked against its values, the strengths
against hand calculations with AISC 360-22 (§J2.4, §J4.1).
"""

import dataclasses
import json
import os
from pathlib import Path

import ezdxf
import pytest
from pydantic import ValidationError

from openconex.cli import main
from openconex.connections.moment.fr_moment import ColumnFace, check_moment_connection
from openconex.core.loads import Method
from openconex.io.project import Project, load_project
from openconex.report.builder import build_report
from openconex.units import Kind, from_internal, to_internal

EXAMPLE = Path(__file__).parents[2] / "examples" / "moment_column_web.ocnx"


def kip(v):
    return from_internal(v, Kind.FORCE, "kip")


def inch(v):
    return from_internal(v, Kind.LENGTH, "in")


def results(mc, M_kip_ft=132.0):
    return {r.id: r for r in check_moment_connection(
        mc, to_internal(24, "kip", Kind.FORCE), to_internal(M_kip_ft, "kip*ft", Kind.MOMENT),
        Method.LRFD)}


def test_welded_flange_to_column_web():
    mc = load_project(EXAMPLE).moment_model()
    assert mc.support is ColumnFace.WEB
    r = results(mc)
    # flange force M/(d - t_f) = 132(12)/(17.99 - 0.570) = 90.9 kips
    pf = 132 * 12 / (17.99 - 0.570)
    assert kip(r["moment.web_connection_weld_top"].demand) == pytest.approx(pf, rel=2e-3)
    # four 3/8 in. fillets on (14.5 - 0.440)/2 - 3/4 - 2(3/8) = 5.53 in. each:
    # 4(0.75)(0.6)(70)(0.707)(0.375)(5.53) = 185 kips
    lw = (14.5 - 0.44) / 2 - 0.75 - 0.75
    expected = 4 * 0.75 * 0.6 * 70 * 0.7071 * 0.375 * lw
    assert kip(r["moment.web_connection_weld_top"].capacity) == pytest.approx(expected,
                                                                              rel=3e-3)
    # connection plate yielding across the clear web depth: 0.9(50)(14.0 - 2(0.710))(7/8)
    yielding = r["moment.web_connection_plate_yielding_top"]
    assert kip(yielding.capacity) == pytest.approx(0.9 * 50 * (14.0 - 1.42) * 0.875, rel=3e-3)
    # Ferrell (1998): t_f + 1/4 in. and t_f + 3/8 in.; extension of at least 3/4 in.
    assert inch(r["moment.web_connection_plate_thickness_top"].demand) == pytest.approx(0.82)
    assert inch(r["moment.web_connection_plate_thickness_bottom"].demand) == pytest.approx(
        0.945)
    assert inch(r["moment.web_connection_plate_extension"].demand) == pytest.approx(0.75)
    # no strong-axis column checks
    assert not any(k.startswith("moment.column_") for k in r)
    # the web plate weld develops the column web, not the flange
    rupture = r["moment.web_support_rupture"]
    assert kip(rupture.capacity) == pytest.approx(0.75 * 0.6 * 65 * 2 * 9 * 0.44, rel=3e-3)


def test_thin_connection_plate_fails():
    mc = load_project(EXAMPLE).moment_model()
    thin = dataclasses.replace(mc, top=dataclasses.replace(
        mc.top, thickness=to_internal(0.625, "in", Kind.LENGTH)))
    assert results(thin)["moment.web_connection_plate_thickness_top"].ratio > 1


def test_bolted_flange_plate_to_column_web():
    data = json.loads((Path(__file__).parents[2] / "examples"
                       / "moment_bolted_flange_plate.ocnx").read_text(encoding="utf-8"))
    data["moment_connection"]["support"] = "web"
    data["moment_connection"]["column"] = "W14X90"
    project = Project.model_validate(data)
    r = results(project.moment_model(), 100)
    assert "moment.flange_plate_weld" not in r
    assert "moment.flange_bolts" in r and "moment.web_connection_weld_top" in r
    assert "moment.web_connection_plate_thickness_top" not in r
    # 7 in. flange plate between the W14x90 flanges: 14.0 - 2(0.710) = 12.6 in.
    assert inch(r["moment.web_connection_fit"].capacity) == pytest.approx(12.6, abs=0.05)
    assert inch(r["moment.web_connection_fit"].demand) == pytest.approx(7.0)


def _data(**changes):
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    data["moment_connection"].update(changes)
    return data


@pytest.mark.parametrize(("data", "message"), [
    (_data(type="welded_flange_plate",
           top={"width": "6 in", "thickness": "1 in", "weld_to_column": "3/8 in",
                "weld_to_beam": "5/16 in", "weld_length": "9 in"},
           bottom={"width": "8 in", "thickness": "3/4 in", "weld_to_column": "3/8 in",
                   "weld_to_beam": "5/16 in", "weld_length": "12 in"}),
     "welded_flange or bolted_flange_plate"),
    (_data(bottom=None), "needs bottom"),
    (_data(panel_zone=True), "no panel zone"),
    (_data(continuity_plate="1/2 in"), "no panel zone"),
])
def test_invalid(data, message):
    with pytest.raises(ValidationError, match=message):
        Project.model_validate(data)


def test_report_drawing_3d_and_window(tmp_path):
    project = load_project(EXAMPLE)
    report = build_report(project)
    assert report.ok
    out = tmp_path / "web"
    assert main(["moment", str(EXAMPLE), "-o", str(out), "--dxf"]) == 0
    assert ezdxf.readfile(out.with_suffix(".dxf"))
    pytest.importorskip("OCP")
    from openconex.geometry3d.moment import moment_parts
    names = {p.name for p in moment_parts(project.moment_model())}
    assert {"beam", "column", "top_plate", "bottom_plate", "web_plate"} <= names
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from openconex.gui.moment import MomentWindow
    QApplication.instance() or QApplication([])
    window = MomentWindow(project, EXAMPLE)
    assert window.project_from_form().moment_connection == project.moment_connection
    assert window.calculate() and window.report.ok
