# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Import of supports and reactions from SAP2000 / ETABS tables exported to Excel."""

import pytest
from openpyxl import Workbook

from openconex.cli import main
from openconex.core.loads import LoadType
from openconex.io.csi import CaseKind, import_supports, read_tables

TONF, CM = 9806.65, 10.0  # N, mm


def _sheet(wb, sheet, title, columns, units, rows):
    ws = wb.create_sheet(sheet)
    ws.append([f"TABLE:  {title}"] + [None] * (len(columns) - 1))
    ws.append(columns)
    ws.append(units)
    for row in rows:
        ws.append(row)


@pytest.fixture
def export(tmp_path):
    """Two supports: joint 1 with a W column rotated 90°, joint 2 with a box column."""
    wb = Workbook()
    wb.remove(wb.active)
    _sheet(wb, "Joint Coordinates", "Joint Coordinates",
           ["Joint", "CoordSys", "CoordType", "XorR", "Y", "Z", "GlobalX", "GlobalY", "GlobalZ"],
           ["Text", "Text", "Text", "cm", "cm", "cm", "cm", "cm", "cm"],
           [["1", "GLOBAL", "Cartesian", 0, 0, 0, 0, 0, 0],
            ["2", "GLOBAL", "Cartesian", 600, 0, 0, 600, 0, 0],
            ["3", "GLOBAL", "Cartesian", 0, 0, 400, 0, 0, 400]])
    _sheet(wb, "Joint Restraint Assignments", "Joint Restraint Assignments",
           ["Joint", "U1", "U2", "U3", "R1", "R2", "R3"], ["Text"] + ["Yes/No"] * 6,
           [["1"] + ["Yes"] * 6, ["2", "Yes", "Yes", "Yes", "No", "No", "No"]])
    _sheet(wb, "Load Case Definitions", "Load Case Definitions",
           ["Case", "Type", "DesignType"], ["Text"] * 3,
           [["DEAD", "LinStatic", "Dead"], ["LIVE", "LinStatic", "Live"],
            ["SX", "LinStatic", "Quake"], ["NX", "LinStatic", "Notional"],
            ["MODAL", "LinModal", "Quake"]])
    _sheet(wb, "Joint Reactions", "Joint Reactions",
           ["Joint", "OutputCase", "CaseType", "StepType", "StepNum",
            "F1", "F2", "F3", "M1", "M2", "M3"],
           ["Text", "Text", "Text", "Text", "Unitless",
            "Tonf", "Tonf", "Tonf", "Tonf-cm", "Tonf-cm", "Tonf-cm"],
           [["1", "DEAD", "LinStatic", None, None, 1, 2, 10, 30, 40, 5],
            ["1", "SX", "LinStatic", None, None, 3, 0, -2, 0, 100, 0],
            ["1", "MODAL", "LinModal", "Mode", 1, 1, 1, 1, 1, 1, 1],
            ["1", "U1", "Combination", None, None, 4, 2, 8, 30, 140, 5],
            ["1", "ENV", "Combination", "Max", None, 5, 3, 12, 0, 0, 0],
            ["1", "ENV", "Combination", "Min", None, -5, -3, 6, 0, 0, 0],
            ["2", "DEAD", "LinStatic", None, None, 0, 0, 20, 0, 0, 0],
            ["2", "U1", "Combination", None, None, 1, 0, 25, 0, 0, 0],
            ["9", "DEAD", "LinStatic", None, None, 0, 0, 99, 0, 0, 0]])
    _sheet(wb, "Connectivity - Frame", "Connectivity - Frame",
           ["Frame", "JointI", "JointJ", "IsCurved", "Length", "CentroidX", "CentroidY",
            "CentroidZ"], ["Text", "Text", "Text", "Yes/No", "cm", "cm", "cm", "cm"],
           [["C1", "3", "1", "No", 400, 0, 0, 200],        # column defined top-down
            ["B1", "1", "2", "No", 600, 300, 0, 0],        # tie beam at the support level
            ["C2", "2", "4", "No", 400, 600, 0, 200]])
    _sheet(wb, "Frame Section Assignments", "Frame Section Assignments",
           ["Frame", "SectionType", "AutoSelect", "AnalSect", "DesignSect", "MatProp"],
           ["Text"] * 6,
           [["C1", "I/Wide Flange", "N.A.", "W14X90", "W14X90", "Default"],
            ["B1", "I/Wide Flange", "N.A.", "W8X10", "W8X10", "Default"],
            ["C2", "Box/Tube", "N.A.", "HSS6X6X3/8", "HSS6X6X3/8", "Default"]])
    _sheet(wb, "Frame Local Axes", "Frame Local Axes Assignments 1 - Typical",
           ["Frame", "Angle", "AdvanceAxes"], ["Text", "Degrees", "Yes/No"],
           [["C1", 90, "No"]])
    _sheet(wb, "Frame Props 01 - General", "Frame Section Properties 01 - General",
           ["SectionName", "Material", "Shape", "t3", "t2", "tf", "tw"],
           ["Text", "Text", "Text", "cm", "cm", "cm", "cm"],
           [["W14X90", "A992Fy50", "I/Wide Flange", 35.6, 36.9, 1.80, 1.12],
            ["HSS6X6X3/8", "A500GrB46", "Box/Tube", 15.24, 15.24, 0.887, 0.887]])
    path = tmp_path / "export.xlsx"
    wb.save(path)
    return path


def test_read_tables_uses_table_titles(export):
    tables = read_tables(export)
    assert "Frame Section Properties 01 - General" in tables
    assert tables["Joint Reactions"].unit("M2") == "Tonf-cm"
    assert len(tables["Joint Reactions"].rows) == 9


def test_supports_columns_and_sections(export):
    data = import_supports(export)
    assert [s.joint for s in data.supports] == ["1", "2"]
    s1, s2 = data.supports
    assert (s2.x, s2.restraints) == (6000.0, (True, True, True, False, False, False))
    assert (s1.column.frame, s1.column.section, s1.column.angle) == ("C1", "W14X90", 90.0)
    assert s1.column.dimensions["t3"] == pytest.approx(356.0)
    assert (s2.column.frame, s2.column.shape) == ("C2", "Box/Tube")


def test_forces_in_column_axes(export):
    s1, s2 = import_supports(export).supports
    dead = s1.forces["DEAD"]  # angle 90°: local 2 = global Y, local 3 = -global X
    assert dead.P == pytest.approx(10 * TONF)
    assert (dead.V2, dead.V3) == (pytest.approx(2 * TONF), pytest.approx(-1 * TONF))
    assert dead.M2 == pytest.approx(40 * TONF * CM)
    assert dead.M3 == pytest.approx(-30 * TONF * CM)
    assert dead.T == pytest.approx(5 * TONF * CM)
    assert s2.forces["U1"].V2 == pytest.approx(1 * TONF)  # angle 0: local 2 = global X


def test_case_classification(export):
    data = import_supports(export)
    cases = data.cases
    assert set(cases) == {"DEAD", "SX", "U1", "ENV (Max)", "ENV (Min)"}
    assert (cases["DEAD"].kind, cases["DEAD"].load_type) == (CaseKind.LOAD_CASE, LoadType.DEAD)
    assert cases["SX"].load_type is LoadType.SEISMIC
    assert cases["U1"].kind is CaseKind.COMBINATION
    assert cases["ENV (Max)"].kind is CaseKind.ENVELOPE
    assert any("MODAL" in w for w in data.warnings)


def test_without_frame_tables(export):
    tables = read_tables(export)
    for name in ("Connectivity - Frame", "Frame Section Assignments"):
        del tables[name]
    data = import_supports(tables)
    assert all(s.column is None for s in data.supports)
    assert any("Connectivity" in w for w in data.warnings)


def test_missing_required_table(export):
    tables = read_tables(export)
    del tables["Joint Reactions"]
    with pytest.raises(ValueError, match="Joint Reactions"):
        import_supports(tables)


def test_unknown_unit(export):
    tables = read_tables(export)
    tables["Joint Reactions"].units[5] = "furlong"
    with pytest.raises(ValueError, match="furlong"):
        import_supports(tables)


def test_cli_supports(export, capsys):
    assert main(["supports", str(export), "--units", "SI_kN_m"]) == 0
    out = capsys.readouterr().out
    assert "2 supports, 3 of 5 output cases" in out
    assert "W14X90 (I/Wide Flange, frame C1, angle 90°)" in out
    assert "max P" in out and "ENV (Max)" in out
