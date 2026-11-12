# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Beam-end reactions of a SAP2000 export and the shear connection projects built from them."""

from pathlib import Path

import pytest

from openconex.cli import main
from openconex.io.csi import Table
from openconex.io.csi_beams import import_beam_ends
from openconex.io.csi_projects import LoadSource
from openconex.io.csi_shear_projects import ShearGrouping, shear_projects
from openconex.io.project import load_project
from openconex.units import Kind, to_internal

EXAMPLES = Path(__file__).parents[1] / "examples"


def _table(name, columns, units, rows):
    return Table(name, columns, units, [dict(zip(columns, r, strict=True)) for r in rows])


def kn(value):
    return to_internal(value, "kN", Kind.FORCE)


def model(releases=True):
    """Two columns, a pinned beam B1 between them and a beam B2 framing into girder G1.

    C1 has its local axes at 0° (B1 along axis 2: flange); C2 at 90° (B1 along
    axis 3: web). B2 frames into G1 at joint 9 (girder web); its far end has no support.
    """
    joints = [("1", 0, 0, 0), ("2", 0, 0, 3000), ("3", 6000, 0, 0), ("4", 6000, 0, 3000),
              ("7", 0, 6000, 3000), ("8", 6000, 6000, 3000), ("9", 3000, 6000, 3000),
              ("10", 3000, 9000, 3000)]
    frames = [("C1", "1", "2", "W14X90"), ("C2", "3", "4", "W14X90"), ("B1", "2", "4", "W18X50"),
              ("G1a", "7", "9", "W21X62"), ("G1b", "9", "8", "W21X62"),
              ("B2", "10", "9", "W16X36")]
    forces = []
    for case, ctype, scale in (("DEAD", "LinStatic", 1.0), ("LIVE", "LinStatic", 2.0),
                               ("COMB1", "Combination", 3.4)):
        forces += [("B1", 0, case, ctype, "", 10 * scale, -50 * scale),
                   ("B1", 3000, case, ctype, "", 10 * scale, 0.0),
                   ("B1", 6000, case, ctype, "", 10 * scale, 50 * scale),
                   ("B2", 0, case, ctype, "", 0.0, -20 * scale),
                   ("B2", 3000, case, ctype, "", 0.0, 20 * scale)]
    tables = {
        "Joint Coordinates": _table("Joint Coordinates", ["Joint", "XorR", "Y", "Z"],
                                    ["", "mm", "mm", "mm"], joints),
        "Connectivity - Frame": _table("Connectivity - Frame", ["Frame", "JointI", "JointJ"],
                                       ["", "", ""], [f[:3] for f in frames]),
        "Frame Section Assignments": _table(
            "Frame Section Assignments", ["Frame", "AnalSect"], ["", ""],
            [(f[0], f[3]) for f in frames]),
        "Frame Section Properties 01 - General": _table(
            "Frame Section Properties 01 - General",
            ["SectionName", "Material", "Shape", "t3", "t2", "tf", "tw"],
            ["", "", "", "mm", "mm", "mm", "mm"],
            [(s, "A992Fy50", "I/Wide Flange", 400, 200, 15, 10)
             for s in ("W14X90", "W18X50", "W21X62", "W16X36")]),
        "Frame Local Axes Assignments 1 - Typical": _table(
            "Frame Local Axes Assignments 1 - Typical", ["Frame", "Angle"], ["", "Degrees"],
            [("C1", 0), ("C2", 90)]),
        "Element Forces - Frames": _table(
            "Element Forces - Frames",
            ["Frame", "Station", "OutputCase", "CaseType", "StepType", "P", "V2"],
            ["", "mm", "", "", "", "KN", "KN"], forces),
        "Load Case Definitions": _table("Load Case Definitions", ["Case", "DesignType"],
                                        ["", ""], [("DEAD", "Dead"), ("LIVE", "Live")]),
    }
    if releases:
        tables["Frame Release Assignments 1 - General"] = _table(
            "Frame Release Assignments 1 - General", ["Frame", "M3I", "M3J"], ["", "", ""],
            [("B1", "Yes", "Yes"), ("B2", "Yes", "Yes")])
    return tables


def test_pinned_beam_ends_and_their_supports():
    data = import_beam_ends(model())
    ends = {e.label: e for e in data.ends}
    assert set(ends) == {"B1-I", "B1-J", "B2-J"}
    assert (ends["B1-I"].support.section, ends["B1-I"].support_element) == ("W14X90", "flange")
    assert (ends["B1-J"].support_kind, ends["B1-J"].support_element) == ("column", "web")
    assert (ends["B2-J"].support.section, ends["B2-J"].support_element) == ("W21X62", "web")
    assert ends["B2-J"].support_kind == "girder"
    assert any("B2-I" in w for w in data.warnings)  # the far end has no support
    dead = ends["B1-I"].forces["DEAD"]
    assert dead.V2 == pytest.approx(kn(-50)) and dead.P == pytest.approx(kn(-10))
    assert ends["B1-J"].forces["LIVE"].V2 == pytest.approx(kn(100))


def test_without_releases_every_beam_end_is_used():
    data = import_beam_ends(model(releases=False))
    assert {e.label for e in data.ends} == {"B1-I", "B1-J", "B2-J"}
    assert any("release" in w for w in data.warnings)


def test_projects_per_end_and_per_section():
    template = load_project(EXAMPLES / "shear_single_plate.ocnx")
    data = import_beam_ends(model())
    projects, _ = shear_projects(data, template)
    assert set(projects) == {"B1-I", "B1-J", "B2-J"}
    b1 = projects["B1-J"]
    assert b1.shear_connection.beam == "W18X50"
    assert b1.shear_connection.support_element == "web"
    assert {c.name for c in b1.cases} == {"DEAD", "LIVE"}
    assert b1.case_forces()["LIVE"].P == pytest.approx(kn(-20))
    grouped, _ = shear_projects(data, template, group=ShearGrouping.SECTION)
    assert set(grouped) == {"W18X50_W14X90_flange", "W18X50_W14X90_web",
                            "W16X36_W21X62_web"}
    combos, _ = shear_projects(data, template, LoadSource.COMBINATIONS)
    assert [c.name for c in combos["B1-I"].cases] == ["COMB1"]


def test_the_template_must_be_a_shear_connection():
    with pytest.raises(ValueError, match="shear_connection"):
        shear_projects(import_beam_ends(model()),
                       load_project(EXAMPLES / "base_plate_dg1_4_7_11.ocnx"))


def test_etabs_and_missing_tables_are_rejected():
    tables = model()
    del tables["Element Forces - Frames"]
    with pytest.raises(ValueError, match="Element Forces"):
        import_beam_ends(tables)


def test_command_creates_and_checks_projects(tmp_path, monkeypatch, capsys):
    import openconex.io.csi_beams as module
    monkeypatch.setattr(module, "read_tables", lambda _path: model())
    out = tmp_path / "proj"
    code = main(["beams", "model.xlsx", "--create", str(out), "--template",
                 str(EXAMPLES / "shear_single_plate.ocnx")])
    assert code == 0
    files = sorted(p.name for p in out.glob("*.ocnx"))
    assert files == ["end-B1-I.ocnx", "end-B1-J.ocnx", "end-B2-J.ocnx"]
    assert main(["shear", str(out / "end-B1-I.ocnx")]) in (0, 1)
    assert main(["beams", "model.xlsx"]) == 0
    assert "B2-J" in capsys.readouterr().out
