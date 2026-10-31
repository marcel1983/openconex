# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Import of supports and reactions from SAP2000 / ETABS tables exported to Excel."""

import dataclasses
from pathlib import Path

import pytest
from openpyxl import Workbook

from openconex.cli import main
from openconex.core.loads import LoadType, Method
from openconex.core.model import HSSKind
from openconex.io.csi import CaseKind, ImportedColumn, Table, import_supports, read_tables
from openconex.io.csi_projects import Grouping, LoadSource, base_plate_projects, column_input
from openconex.io.project import HSSSectionInput, WSectionInput, load_project

TEMPLATE = Path(__file__).parents[1] / "examples" / "base_plate_generic_w.ocnx"

TONF, CM, M = 9806.65, 10.0, 1000.0  # N, mm


def _sheet(wb, sheet, title, columns, units, rows):
    ws = wb.create_sheet(sheet)
    ws.append([f"TABLE:  {title}"] + [None] * (len(columns) - 1))
    ws.append(columns)
    ws.append(units)
    for row in rows:
        ws.append(row)


def _table(name, columns, units, rows):
    return Table(name, columns, units,
                 [dict(zip(columns, row, strict=True)) for row in rows])


@pytest.fixture
def etabs_export():
    """Minimal ETABS v23 export with object tables and split load case sheets."""
    return {
        "Point Object Connectivity": _table(
            "Point Object Connectivity", ["UniqueName", "X", "Y", "Z"],
            ["", "m", "m", "m"],
            [["1", 0, 0, 0], ["2", 6, 0, 0], ["3", 0, 0, 3]]),
        "Joint Assignments - Restraints": _table(
            "Joint Assignments - Restraints",
            ["UniqueName", "UX", "UY", "UZ", "RX", "RY", "RZ"],
            [""] * 7,
            [["1", "Yes", "Yes", "Yes", "No", "No", "No"],
             ["2", "Yes", "Yes", "Yes", "No", "No", "No"]]),
        "Joint Reactions": _table(
            "Joint Reactions",
            ["Unique Name", "Output Case", "Case Type", "Step Type", "Step Number",
             "FX", "FY", "FZ", "MX", "MY", "MZ"],
            ["", "", "", "", "", "tonf", "tonf", "tonf", "tonf-m", "tonf-m", "tonf-m"],
            [["1", "Dead", "LinStatic", None, None, 1, 2, 10, 30, 40, 5],
             ["1", "SXE", "LinStatic", "Step By Step", 1, 3, 0, -1, 0, 50, 0],
             ["1", "SXE", "LinStatic", "Step By Step", 2, 3, 0, -2, 0, 100, 0],
             ["1", "U1", "Combination", None, None, 4, 2, 8, 30, 140, 5],
             ["1", "Modal", "LinModEigen", "Mode", 1, 1, 1, 1, 1, 1, 1],
             ["2", "Dead", "LinStatic", None, None, 0, 0, 20, 0, 0, 0]]),
        "Column Object Connectivity": _table(
            "Column Object Connectivity",
            ["Unique Name", "UniquePtI", "UniquePtJ", "Length"],
            ["", "", "", "m"],
            [["10", "1", "3", 3]]),
        "Frame Assignments - Section Properties": _table(
            "Frame Assignments - Section Properties",
            ["UniqueName", "Shape", "Section Property"],
            ["", "", ""],
            [["10", "Steel I/Wide Flange", "W14X90"]]),
        "Frame Assignments - Summary": _table(
            "Frame Assignments - Summary",
            ["UniqueName", "Design Type", "Analysis Section", "Design Section", "Axis Angle"],
            ["", "", "", "", "deg"],
            [["10", "Column", "W14X90", "W14X90", 90]]),
        "Frame Assignments - Local Axes": _table(
            "Frame Assignments - Local Axes", ["UniqueName", "Angle"], ["", "deg"],
            [["10", 90]]),
        "Frame Section Property Definitions - Summary": _table(
            "Frame Section Property Definitions - Summary",
            ["Name", "Material", "Shape"], ["", "", ""],
            [["W14X90", "A992Fy50", "Steel I/Wide Flange"]]),
        "Frame Section Property Definitions - Steel I/Wide Flange": _table(
            "Frame Section Property Definitions - Steel I/Wide Flange",
            ["Name", "Total Depth", "Top Flange Width", "Top Flange Thickness",
             "Web Thickness"],
            ["", "m", "m", "m", "m"],
            [["W14X90", 0.356, 0.369, 0.018, 0.011]]),
        "Load Pattern Definitions": _table(
            "Load Pattern Definitions", ["Name", "Type"], ["", ""],
            [["Dead", "Dead"], ["SXE", "Seismic"]]),
        "Load Case Definitions - Linear Static": _table(
            "Load Case Definitions - Linear Static",
            ["Name", "Load Name", "Design Type"], ["", "", ""],
            [["Dead", "Dead", "Program Determined"],
             ["SXE", "SXE", "Program Determined"]]),
        "Load Case Definitions - Summary": _table(
            "Load Case Definitions - Summary", ["Name", "Type"], ["", ""],
            [["Dead", "Linear Static"], ["SXE", "Linear Static"],
             ["Modal", "Modal - Eigen"]]),
        "Load Combination Definitions": _table(
            "Load Combination Definitions", ["Name", "Load Name", "SF"],
            ["", "", ""],
            [["U1", "Dead", 1.2], ["U1", "SXE", 1.0]]),
    }


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
    _sheet(wb, "Combination Definitions", "Combination Definitions",
           ["ComboName", "ComboType", "CaseType", "CaseName", "ScaleFactor"],
           ["Text", "Text", "Text", "Text", "Unitless"],
           [["U1", "Linear Add", "Linear Static", "DEAD", 1.2],
            ["U1", "Linear Add", "Linear Static", "SX", 1.0],
            ["ENV", "Envelope", "Linear Static", "DEAD", 1.0]])
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
            ["HSS6X6X3/8", "A500GrB46", "Box/Tube", 15.24, 15.24, 0.887, 0.887],
            ["W8X10", "A992Fy50", "I/Wide Flange", 20.0, 10.0, 0.52, 0.43]])
    path = tmp_path / "export.xlsx"
    wb.save(path)
    return path


def test_read_tables_uses_table_titles(export):
    tables = read_tables(export)
    assert "Frame Section Properties 01 - General" in tables
    assert tables["Joint Reactions"].unit("M2") == "Tonf-cm"
    assert len(tables["Joint Reactions"].rows) == 9


def test_etabs_table_and_column_aliases(export):
    tables = read_tables(export)
    table_aliases = {
        "Joint Restraint Assignments": "Joint Restraints",
        "Joint Reactions": "Joint Reaction Forces",
        "Load Case Definitions": "Load Cases",
        "Connectivity - Frame": "Frame Connectivity",
        "Frame Local Axes Assignments 1 - Typical": "Frame Local Axes",
        "Frame Section Properties 01 - General": "Frame Section Properties",
    }
    column_aliases = {
        "DesignType": "Design Type", "OutputCase": "Output Case",
        "CaseType": "Case Type", "StepType": "Step Type",
        "JointI": "Joint I", "JointJ": "Joint J",
        "CentroidX": "Centroid X", "CentroidY": "Centroid Y",
        "CentroidZ": "Centroid Z", "SectionName": "Section Name",
    }
    aliased = {}
    for table in tables.values():
        name = table_aliases.get(table.name, table.name)
        columns = [column_aliases.get(c, c) for c in table.columns]
        rows = [dict(zip(columns, [row.get(c) for c in table.columns], strict=True))
                for row in table.rows]
        aliased[name] = Table(name, columns, table.units, rows)
    data = import_supports(aliased)
    assert [s.joint for s in data.supports] == ["1", "2"]
    assert data.supports[0].column.section == "W14X90"
    assert data.cases["U1"].kind is CaseKind.COMBINATION


def test_etabs_object_tables_and_split_cases(etabs_export):
    data = import_supports(etabs_export)
    assert [s.joint for s in data.supports] == ["1", "2"]
    s1, s2 = data.supports
    assert s1.column is not None
    assert (s1.column.frame, s1.column.section, s1.column.shape) == \
        ("10", "W14X90", "Steel I/Wide Flange")
    assert s1.column.angle == pytest.approx(90)
    assert s1.column.dimensions["t3"] == pytest.approx(356.0)
    assert s2.column is None
    assert set(s1.forces) == {"Dead", "SXE", "U1"}
    assert s1.forces["SXE"].P == pytest.approx(-2 * TONF)
    assert s1.forces["SXE"].M2 == pytest.approx(100 * TONF * M)
    assert data.cases["SXE"].seismic
    assert data.cases["U1"].seismic
    assert "Modal" not in data.cases
    assert any("last output step" in warning for warning in data.warnings)
    projects, warnings = base_plate_projects(data, load_project(TEMPLATE))
    assert set(projects) == {"1"}
    assert projects["1"].base_plate.column == "W14X90"
    assert any("no column" in warning for warning in warnings)


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
    assert cases["U1"].seismic and cases["SX"].seismic
    assert not cases["DEAD"].seismic and not cases["ENV (Max)"].seismic
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


def _column(section, shape, material, t3, t2, tf, tw):
    return ImportedColumn("C", section, shape, 0.0, material,
                          {"t3": t3, "t2": t2, "tf": tf, "tw": tw})


def test_column_input():
    assert column_input(_column("W14X90", "I/Wide Flange", "A992Fy50", 356, 369, 18, 11))[:2] \
        == ("W14X90", "ASTM A992")
    built_up, grade, _ = column_input(_column("COL-1", "I/Wide Flange", "A572Gr50",
                                              450, 300, 9.652, 6.35))
    assert isinstance(built_up, WSectionInput) and built_up.d == "450 mm"
    assert (built_up.grade, grade) == ("ASTM A572 Gr. 50", "ASTM A572 Gr. 50")
    built_up, grade, warning = column_input(
        _column("COL-2", "I/Wide Flange", "X", 450, 300, 9.652, 6.35), "ASTM A36")
    assert built_up.grade == grade == "ASTM A36"
    assert "unknown material" in warning
    box = column_input(_column("HSS6X6X3/8", "Box/Tube", "A500GrB46", 152.4, 152.4, 8.87, 8.87))[0]
    assert isinstance(box, HSSSectionInput) and box.shape is HSSKind.SQUARE
    assert box.grade == "ASTM A500 Gr. B (rectangular)"
    pipe, pipe_grade, pipe_warning = column_input(_column("P", "Pipe", "A53", 100, 0, 0, 6))
    assert pipe is None and pipe_grade is None and "unknown material" in pipe_warning
    pipe, pipe_grade, pipe_warning = column_input(
        _column("P", "Pipe", "A53", 100, 0, 0, 6), "ASTM A500 Gr. C (round)")
    assert pipe.shape is HSSKind.ROUND and pipe.grade == pipe_grade
    assert pipe_grade == "ASTM A500 Gr. C (round)" and "unknown material" in pipe_warning
    assert column_input(_column("X", "Channel", "A36", 1, 1, 1, 1))[0] is None


@pytest.mark.parametrize(("section", "shape", "material", "dims", "grade"), [
    ("COL-1", "I/Wide Flange", "A913Gr65", (450, 300, 9.652, 6.35), "ASTM A913 Gr. 65"),
    ("COL-2", "I/Wide Flange", "A572Gr60", (450, 300, 9.652, 6.35), "ASTM A572 Gr. 60"),
    ("COL-3", "I/Wide Flange", "A709Gr50W", (450, 300, 9.652, 6.35), "ASTM A709 Gr. 50W"),
    ("HSS1", "Box/Tube", "A1085", (152.4, 152.4, 8.87, 8.87), "ASTM A1085"),
    ("HSS2", "Box/Tube", "A500GrC46", (152.4, 101.6, 8.87, 8.87),
     "ASTM A500 Gr. C (rectangular)"),
    ("HSS3", "Box/Tube", "A1065Gr50W", (152.4, 101.6, 8.87, 8.87), "ASTM A1065 Gr. 50W"),
    ("P1", "Pipe", "A53GrB", (100, 0, 0, 6), "ASTM A53 Gr. B"),
])
def test_typical_material_mapping(section, shape, material, dims, grade):
    result, used, warning = column_input(
        _column(section, shape, material, *dims), "ASTM A992")
    assert result is not None and warning is None
    assert used == grade
    assert result.grade == grade


def test_projects_from_load_cases(export):
    projects, warnings = base_plate_projects(import_supports(export), load_project(TEMPLATE))
    assert set(projects) == {"1", "2"}
    p1 = projects["1"]
    assert p1.base_plate.column == "W14X90"
    assert [(c.name, c.type) for c in p1.cases] == [("DEAD", LoadType.DEAD),
                                                    ("SX", LoadType.SEISMIC)]
    dead = p1.case_forces()["DEAD"]
    assert dead.P == pytest.approx(10 * TONF)
    assert (dead.V2, dead.V3) == (pytest.approx(2 * TONF), pytest.approx(-1 * TONF))
    assert (dead.M3, dead.M2) == (pytest.approx(-30 * TONF * CM), pytest.approx(40 * TONF * CM))
    assert p1.combinations.include_code and not p1.combinations.custom
    assert p1.load_combinations()
    assert not warnings
    assert isinstance(projects["2"].base_plate.column, HSSSectionInput)


def test_projects_from_combinations(export):
    data = import_supports(export)
    projects, _ = base_plate_projects(data, load_project(TEMPLATE), LoadSource.COMBINATIONS,
                                      method=Method.ASD)
    p1 = projects["1"]
    assert [c.name for c in p1.cases] == ["U1"]
    (combo,) = p1.combinations.custom
    assert (combo.name, combo.method, combo.factors, combo.seismic) == \
        ("U1", Method.ASD, {"U1": 1.0}, True)
    assert not p1.combinations.include_code
    projects, _ = base_plate_projects(data, load_project(TEMPLATE), LoadSource.COMBINATIONS,
                                      include="^ENV", envelopes=True)
    assert [c.name for c in projects["1"].cases] == ["ENV (Max)", "ENV (Min)"]
    assert "2" not in projects  # joint 2 has no envelope


def test_cli_create_projects(export, tmp_path, capsys):
    out = tmp_path / "projects"
    assert main(["supports", str(export), "--create", str(out), "--template", str(TEMPLATE),
                 "--loads", "combinations"]) == 0
    assert sorted(p.name for p in out.iterdir()) == ["joint-1.ocnx", "joint-2.ocnx"]
    assert load_project(out / "joint-1.ocnx").cases[0].name == "U1"
    assert main(["supports", str(export), "--create", str(out)]) == 2


def _same_column(data):
    """Both supports with the W14X90 column of joint 1."""
    s1, s2 = data.supports
    return dataclasses.replace(data, supports=[s1, dataclasses.replace(s2, column=s1.column)])


def test_group_by_column(export):
    data = _same_column(import_supports(export))
    projects, _ = base_plate_projects(data, load_project(TEMPLATE), group=Grouping.COLUMN)
    assert list(projects) == ["W14X90"]
    project = projects["W14X90"]
    assert [c.name for c in project.cases] == ["1: DEAD", "1: SX", "2: DEAD"]
    assert "joints 1, 2" in project.info.name
    combos = project.load_combinations()
    assert all(len({name.split(":")[0] for name in c.factors}) == 1 for c in combos)
    assert {c.name.split(":")[0] for c in combos} == {"1", "2"}
    by_joint = base_plate_projects(data, load_project(TEMPLATE))[0]
    assert len(combos) == sum(len(p.load_combinations()) for p in by_joint.values())


def test_group_by_column_with_imported_combinations(export):
    data = _same_column(import_supports(export))
    projects, _ = base_plate_projects(data, load_project(TEMPLATE), LoadSource.COMBINATIONS,
                                      group=Grouping.COLUMN)
    custom = projects["W14X90"].combinations.custom
    assert [(c.name, c.factors, c.seismic) for c in custom] == [
        ("1: U1", {"1: U1": 1.0}, True), ("2: U1", {"2: U1": 1.0}, True)]


def test_cli_group_by_column(export, tmp_path):
    out = tmp_path / "types"
    assert main(["supports", str(export), "--create", str(out), "--template", str(TEMPLATE),
                 "--group", "column"]) == 0
    assert sorted(p.name for p in out.iterdir()) == ["column-HSS6X6X3_8.ocnx",
                                                     "column-W14X90.ocnx"]


def test_repeated_warnings_are_joined(export):
    tables = read_tables(export)
    tables["Joint Reactions"].rows.append(dict(tables["Joint Reactions"].rows[6],
                                               OutputCase="NX", CaseType="LinStatic"))
    tables["Joint Reactions"].rows.append(dict(tables["Joint Reactions"].rows[0],
                                               OutputCase="NX", CaseType="LinStatic"))
    _, warnings = base_plate_projects(import_supports(tables), load_project(TEMPLATE))
    assert "joints 1, 2: load cases without a design type, not used: NX" in warnings
