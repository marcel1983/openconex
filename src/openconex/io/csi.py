# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Support reactions and columns from SAP2000 / ETABS database tables.

The analysis program exports its database tables to Excel (File > Export >
Microsoft Excel). Each sheet holds one table: a title row ``TABLE:  name``, a
row of field names, a row of units and the data. The tables used here are:

======================================  ==========================================
Table                                   Use
======================================  ==========================================
Joint Coordinates                       position of the supports
Joint Restraint Assignments             which joints are supports
Joint Reactions                         forces per output case
Load Case Definitions                   design type of each load case (D, L, E…)
Load Pattern Definitions                design type of each load pattern
Case - Static 1 - Load Assignments      patterns applied by each static case
Combination Definitions                 cases of each combination
Connectivity - Frame                    column connected to each support
Frame Section Assignments               section of that column
Frame Local Axes Assignments 1 - Typical  rotation of the column local axes
Frame Section Properties 01 - General   section dimensions
======================================  ==========================================

Only the first four are required; without the frame tables the supports are
read without a column.

Sign convention of the imported forces (acting on the base plate): P is the
vertical reaction F3 (positive = compression in the column). V2, V3, M2 and M3
are the reaction components along the column local axes 2 and 3 and T the
reaction moment about the vertical axis. For a vertical column with the default
local axes (angle 0) axis 2 is global X and axis 3 global Y; the angle rotates
them about the column axis. For I shapes the strong axis is the local axis 3.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from openconex.core.loads import Forces, LoadType
from openconex.units import Kind, to_internal

__all__ = [
    "CaseKind",
    "CsiImport",
    "ImportedCase",
    "ImportedColumn",
    "Support",
    "Table",
    "import_supports",
    "read_tables",
]

REQUIRED = ("Joint Coordinates", "Joint Restraint Assignments", "Joint Reactions")

# ETABS and SAP2000 share most of the CSI database schema, but some versions
# use shorter or spaced table and column names. Normalize the common aliases
# when reading the workbook.
_TABLE_ALIASES = {
    "Joint Coordinates": ("Joint Coordinates", "Point Coordinates",
                          "Joint Object Coordinates", "Point Object Coordinates"),
    "Joint Restraint Assignments": ("Joint Restraint Assignments", "Joint Restraints",
                                    "Point Restraint Assignments", "Point Restraints"),
    "Joint Reactions": ("Joint Reactions", "Joint Reaction Forces", "Point Reactions"),
    "Load Case Definitions": ("Load Case Definitions", "Load Cases"),
    "Load Pattern Definitions": ("Load Pattern Definitions", "Load Patterns"),
    "Case - Static 1 - Load Assignments": (
        "Case - Static 1 - Load Assignments", "Static 1 - Load Assignments"),
    "Combination Definitions": ("Combination Definitions", "Load Combinations"),
    "Connectivity - Frame": ("Connectivity - Frame", "Frame Connectivity"),
    "Frame Section Assignments": ("Frame Section Assignments", "Frame Section Assignment"),
    "Frame Section Properties 01 - General": (
        "Frame Section Properties 01 - General", "Frame Section Properties"),
    "Frame Local Axes Assignments 1 - Typical": (
        "Frame Local Axes Assignments 1 - Typical", "Frame Local Axes",
        "Frame Local Axes Assignments"),
}

_COLUMN_ALIASES = {
    "UniqueName": ("UniqueName", "Unique Name"),
    "Joint": ("Joint", "Point"),
    "GlobalX": ("GlobalX", "Global X", "X"),
    "Y": ("Y",),
    "Z": ("Z",),
    "XorR": ("XorR", "X or R", "X"),
    "DesignType": ("DesignType", "Design Type"),
    "OutputCase": ("OutputCase", "Output Case"),
    "CaseType": ("CaseType", "Case Type"),
    "StepType": ("StepType", "Step Type"),
    "JointI": ("JointI", "Joint I"),
    "JointJ": ("JointJ", "Joint J"),
    "CentroidX": ("CentroidX", "Centroid X"),
    "CentroidY": ("CentroidY", "Centroid Y"),
    "CentroidZ": ("CentroidZ", "Centroid Z"),
    "AnalSect": ("AnalSect", "Analysis Section"),
    "DesignSect": ("DesignSect", "Design Section"),
    "SectionName": ("SectionName", "Section Name"),
    "ComboName": ("ComboName", "Combo Name"),
    "CaseName": ("CaseName", "Case Name"),
    "LoadPat": ("LoadPat", "Load Pattern"),
    "LoadName": ("LoadName", "Load Name"),
}

# CSI unit names -> pint
_UNITS = {
    "n": "N", "kn": "kN", "kgf": "kgf", "tonf": "tf", "lb": "lbf", "kip": "kip",
    "mm": "mm", "cm": "cm", "m": "m", "in": "in", "ft": "ft",
}

# CSI design type of a load case -> OpenConex load type
_DESIGN_TYPES = {
    "dead": LoadType.DEAD, "super dead": LoadType.DEAD, "live": LoadType.LIVE,
    "reducible live": LoadType.LIVE, "roof live": LoadType.ROOF_LIVE, "snow": LoadType.SNOW,
    "rain": LoadType.RAIN, "wind": LoadType.WIND, "quake": LoadType.SEISMIC,
    "seismic": LoadType.SEISMIC,
}


@dataclass(frozen=True)
class Table:
    name: str
    columns: list[str]
    units: list[str]
    rows: list[dict[str, Any]]

    def unit(self, column: str) -> str:
        return self.units[self.columns.index(column)]


def _normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _canonical(name: str, aliases: dict[str, tuple[str, ...]]) -> str:
    key = _normalized(name)
    for canonical, options in aliases.items():
        if key in {_normalized(option) for option in options}:
            return canonical
    return name


def _normalize_table(table: Table) -> Table:
    columns = [_canonical(c, _COLUMN_ALIASES) for c in table.columns]
    return Table(_canonical(table.name, _TABLE_ALIASES), columns, table.units, [
        {columns[i]: value for i, value in enumerate(row.values()) if i < len(columns)}
        for row in table.rows])


def read_tables(path: str | Path) -> dict[str, Table]:
    """All database tables of an Excel file exported by SAP2000 or ETABS."""
    from openpyxl import load_workbook

    tables: dict[str, Table] = {}
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        for sheet in workbook.worksheets:
            rows = [r for r in sheet.iter_rows(values_only=True)]
            if len(rows) < 3 or not str(rows[0][0] or "").startswith("TABLE:"):
                continue
            name = str(rows[0][0]).removeprefix("TABLE:").strip()  # sheet names are abridged
            columns = [str(c) if c is not None else "" for c in rows[1]]
            units = [str(c) if c is not None else "" for c in rows[2]]
            data = [dict(zip(columns, r, strict=False)) for r in rows[3:]
                    if any(v is not None for v in r)]
            table = _normalize_table(Table(name, columns, units, data))
            tables[table.name] = table
    finally:
        workbook.close()
    return tables


def _pint_unit(csi_unit: str) -> str:
    try:
        return "*".join(_UNITS[part.strip().lower()] for part in csi_unit.split("-"))
    except KeyError:
        raise ValueError(f"unknown unit in exported table: {csi_unit!r}") from None


def _converter(table: Table, column: str, kind: Kind):
    unit = _pint_unit(table.unit(column))
    factor = to_internal(1.0, unit, kind)
    return lambda value: float(value or 0.0) * factor


class CaseKind(StrEnum):
    LOAD_CASE = "case"
    """Unfactored load case; OpenConex can combine it."""
    COMBINATION = "combination"
    """Combination defined in the analysis program (already factored)."""
    ENVELOPE = "envelope"
    """Maximum or minimum of a case: components need not be concurrent."""


@dataclass(frozen=True)
class ImportedCase:
    name: str
    """Output case label, with " (Max)" or " (Min)" for envelopes."""
    output_case: str
    case_type: str
    kind: CaseKind
    load_type: LoadType | None = None
    design_type: str = ""
    seismic: bool = False
    """Includes a seismic load pattern, directly or through cases and combinations."""


@dataclass(frozen=True)
class ImportedColumn:
    frame: str
    section: str
    shape: str
    """CSI shape name: I/Wide Flange, Box/Tube, Pipe…"""
    angle: float = 0.0
    """Rotation of the local axes 2-3 about the column axis [degrees]."""
    material: str = ""
    dimensions: dict[str, float] = field(default_factory=dict)
    """t3 (depth), t2 (width), tf, tw [mm], as given by the program."""


@dataclass(frozen=True)
class Support:
    joint: str
    x: float
    y: float
    z: float
    restraints: tuple[bool, bool, bool, bool, bool, bool]
    column: ImportedColumn | None
    forces: dict[str, Forces]
    """Forces on the plate by case label (see ImportedCase.name)."""


@dataclass(frozen=True)
class CsiImport:
    supports: list[Support]
    cases: dict[str, ImportedCase]
    warnings: list[str]


def _restraints(table: Table) -> dict[str, tuple[bool, ...]]:
    keys = ("U1", "U2", "U3", "R1", "R2", "R3")
    return {str(r["Joint"]): tuple(str(r.get(k, "")).lower() == "yes" for k in keys)
            for r in table.rows}


def _coordinates(table: Table) -> dict[str, tuple[float, float, float]]:
    cols = ("GlobalX", "GlobalY", "GlobalZ") if "GlobalX" in table.columns else ("XorR", "Y", "Z")
    conv = [_converter(table, c, Kind.LENGTH) for c in cols]
    return {str(r["Joint"]): tuple(f(r[c]) for f, c in zip(conv, cols, strict=True))
            for r in table.rows}


def _cases(tables: dict[str, Table]) -> dict[str, tuple[str, LoadType | None]]:
    table = tables.get("Load Case Definitions")
    if table is None:
        return {}
    return {str(r["Case"]): (str(r.get("DesignType") or ""),
                             _DESIGN_TYPES.get(str(r.get("DesignType") or "").lower()))
            for r in table.rows}


def _seismic_cases(tables: dict[str, Table]) -> set[str]:
    """Load cases and combinations that include a seismic (Quake) load pattern."""
    def rows(name):
        return tables[name].rows if name in tables else []

    quake = {str(r["LoadPat"]) for r in rows("Load Pattern Definitions")
             if str(r.get("DesignType") or "").lower() == "quake"}
    direct = {str(r["Case"]) for r in rows("Load Case Definitions")
              if str(r.get("DesignType") or "").lower() == "quake"}
    direct |= {str(r["Case"]) for r in rows("Case - Static 1 - Load Assignments")
               if str(r.get("LoadName")) in quake}
    children: dict[str, set[str]] = {}
    for r in rows("Combination Definitions"):
        children.setdefault(str(r["ComboName"]), set()).add(str(r["CaseName"]))
    found: dict[str, bool] = {}

    def seismic(name: str) -> bool:
        if name not in found:
            found[name] = False  # guards against cycles
            found[name] = name in direct or any(seismic(c) for c in children.get(name, ()))
        return found[name]

    return {name for name in direct | set(children) if seismic(name)}


def _columns(tables: dict[str, Table], coords, warnings) -> dict[str, ImportedColumn]:
    """Vertical frame connected to each support joint."""
    conn = tables.get("Connectivity - Frame")
    if conn is None or not conn.rows:
        warnings.append("no 'Connectivity - Frame' data: supports imported without column")
        return {}
    sections = {str(r["Frame"]): str(r.get("AnalSect") or r.get("DesignSect") or "")
                for r in tables["Frame Section Assignments"].rows} \
        if "Frame Section Assignments" in tables else {}
    angles = {str(r["Frame"]): float(r.get("Angle") or 0.0)
              for r in tables["Frame Local Axes Assignments 1 - Typical"].rows} \
        if "Frame Local Axes Assignments 1 - Typical" in tables else {}
    props = _section_props(tables.get("Frame Section Properties 01 - General"))
    to_mm = _converter(conn, "CentroidX", Kind.LENGTH)
    found: dict[str, ImportedColumn] = {}
    for r in conn.rows:
        for end in ("JointI", "JointJ"):
            joint = str(r[end])
            if joint not in coords:
                continue
            x, y, z = coords[joint]
            cx, cy, cz = (to_mm(r[c]) for c in ("CentroidX", "CentroidY", "CentroidZ"))
            if math.hypot(cx - x, cy - y) > 1e-3 * max(abs(cz - z), 1.0) or cz <= z:
                continue  # not a column standing on the joint
            frame = str(r["Frame"])
            section = sections.get(frame, "")
            shape, material, dims = props.get(section, ("", "", {}))
            if joint in found:
                warnings.append(f"joint {joint}: several columns, using frame {found[joint].frame}")
                continue
            found[joint] = ImportedColumn(frame, section, shape, angles.get(frame, 0.0),
                                          material, dims)
    return found


def _section_props(table: Table | None) -> dict[str, tuple[str, str, dict[str, float]]]:
    if table is None:
        return {}
    keys = [k for k in ("t3", "t2", "tf", "tw", "t2b", "tfb") if k in table.columns]
    conv = {k: _converter(table, k, Kind.LENGTH) for k in keys}
    return {str(r["SectionName"]): (str(r.get("Shape") or ""), str(r.get("Material") or ""),
                                    {k: conv[k](r[k]) for k in keys if r.get(k) is not None})
            for r in table.rows}


def _plate_forces(f1, f2, f3, m1, m2, m3, angle: float) -> Forces:
    c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    return Forces(P=f3, V2=f1 * c + f2 * s, V3=-f1 * s + f2 * c,
                  M2=m1 * c + m2 * s, M3=-m1 * s + m2 * c, T=m3)


def _column(table: Table, *names: str) -> str | None:
    keys = {_normalized(name): name for name in table.columns}
    for name in names:
        if name in table.columns:
            return name
        found = keys.get(_normalized(name))
        if found:
            return found
    return None


def _cell(row: dict[str, Any], *names: str) -> Any:
    keys = {_normalized(name): name for name in row}
    for name in names:
        if name in row:
            return row[name]
        found = keys.get(_normalized(name))
        if found:
            return row[found]
    return None


def _first_table(tables: dict[str, Table], *names: str) -> Table | None:
    for name in names:
        if name in tables:
            return tables[name]
    keys = {_normalized(name): table for name, table in tables.items()}
    for name in names:
        found = keys.get(_normalized(name))
        if found is not None:
            return found
    return None


def _is_etabs(tables: dict[str, Table]) -> bool:
    return any(name in tables for name in (
        "Point Object Connectivity", "Joint Assignments - Restraints",
        "Column Object Connectivity"))


def _etabs_section_dims(tables: dict[str, Table]) -> dict[str, dict[str, float]]:
    tables_defs = (
        (_first_table(tables, "Frame Section Property Definitions - Steel I/Wide Flange",
                      "Frame Sec Def - Steel I"),
         {"t3": ("Total Depth",), "t2": ("Top Flange Width",),
          "tf": ("Top Flange Thickness",), "tw": ("Web Thickness",)}),
        (_first_table(tables, "Frame Section Property Definitions - Steel Tube",
                      "Frame Sec Def - Steel Tube"),
         {"t3": ("Total Depth",), "t2": ("Total Width",),
          "tf": ("Flange Thickness",), "tw": ("Web Thickness",)}),
        (_first_table(tables, "Frame Section Property Definitions - Concrete Rectangular",
                      "Frame Sec Def - Conc Rect"),
         {"t3": ("Depth",), "t2": ("Width",)}),
    )
    result: dict[str, dict[str, float]] = {}
    for table, fields in tables_defs:
        if table is None:
            continue
        for row in table.rows:
            name = str(_cell(row, "Name") or "")
            if not name:
                continue
            dims = {}
            for key, aliases in fields.items():
                col = _column(table, *aliases)
                if col is not None and _cell(row, col) is not None:
                    dims[key] = _converter(table, col, Kind.LENGTH)(_cell(row, col))
            result[name] = dims
    return result


def _etabs_column_info(tables: dict[str, Table]) -> dict[str, dict[str, Any]]:
    """Section, material, shape, angle and dimensions keyed by frame UniqueName."""
    info: dict[str, dict[str, Any]] = {}
    sect = _first_table(tables, "Frame Assignments - Section Properties",
                        "Frame Assigns - Sect Prop")
    if sect is not None:
        for row in sect.rows:
            uid = str(_cell(row, "UniqueName") or "")
            if uid:
                info.setdefault(uid, {}).update(
                    section=str(_cell(row, "Section Property") or ""),
                    shape=str(_cell(row, "Shape") or ""))
    summary = _first_table(tables, "Frame Assignments - Summary", "Frame Assigns - Summary")
    if summary is not None:
        for row in summary.rows:
            uid = str(_cell(row, "UniqueName") or "")
            if uid:
                entry = info.setdefault(uid, {})
                entry.setdefault(
                    "section",
                    str(_cell(row, "Design Section", "Analysis Section",
                              "DesignSect", "AnalSect") or ""))
                angle = _cell(row, "Axis Angle")
                if angle is not None:
                    entry["angle"] = float(angle)
    axes = _first_table(tables, "Frame Assignments - Local Axes", "Frame Assigns - Local Axes")
    if axes is not None:
        for row in axes.rows:
            uid = str(_cell(row, "UniqueName") or "")
            if uid:
                entry = info.setdefault(uid, {})
                angle = _cell(row, "Angle")
                if angle is not None:
                    entry["angle"] = float(angle)
    props = _first_table(tables, "Frame Section Property Definitions - Summary",
                         "Frame Prop - Summary")
    prop_info: dict[str, tuple[str, str]] = {}
    if props is not None:
        for row in props.rows:
            name = str(_cell(row, "Name") or "")
            if name:
                prop_info[name] = (str(_cell(row, "Material") or ""),
                                   str(_cell(row, "Shape") or ""))
    dims = _etabs_section_dims(tables)
    for entry in info.values():
        section = entry.get("section", "")
        material, shape = prop_info.get(section, ("", ""))
        entry["material"] = material
        entry["shape"] = entry.get("shape") or shape
        entry["dimensions"] = dims.get(section, {})
    return info


def _etabs_patterns(tables: dict[str, Table]) -> tuple[dict[str, tuple[str, LoadType | None]],
                                                      set[str]]:
    table = tables.get("Load Pattern Definitions")
    if table is None:
        return {}, set()
    patterns: dict[str, tuple[str, LoadType | None]] = {}
    seismic: set[str] = set()
    for row in table.rows:
        name = str(_cell(row, "Name") or "")
        design = str(_cell(row, "Type") or "")
        if not name:
            continue
        load_type = _DESIGN_TYPES.get(design.lower())
        patterns[name] = (design, load_type)
        if load_type is LoadType.SEISMIC:
            seismic.add(name)
    return patterns, seismic


def _etabs_cases(tables: dict[str, Table]) -> tuple[dict[str, tuple[str, LoadType | None]],
                                                    dict[str, set[str]], set[str]]:
    patterns, seismic_patterns = _etabs_patterns(tables)
    case_info = dict(patterns)
    case_loads: dict[str, set[str]] = {}
    case_kind: dict[str, str] = {}
    for table_name in ("Load Case Definitions - Linear Static",
                       "Load Case Definitions - Nonlinear Static",
                       "Load Case Definitions - Response Spectrum",
                       "Load Case Definitions - Summary",
                       "Load Cases - Linear Static", "Load Cases - Nonlinear Static",
                       "Load Cases - Response Spectrum", "Load Cases - Summary"):
        table = _first_table(tables, table_name)
        if table is None:
            continue
        for row in table.rows:
            name = str(_cell(row, "Name") or "")
            if not name:
                continue
            load = _cell(row, "Load Name")
            if load:
                case_loads.setdefault(name, set()).add(str(load))
            design = str(_cell(row, "Design Type") or "")
            if design and design.lower() != "program determined":
                load_type = _DESIGN_TYPES.get(design.lower())
                if load_type is not None:
                    case_info[name] = (design, load_type)
            kind = str(_cell(row, "Type") or "")
            if kind:
                case_kind[name] = kind
    for name, loads in case_loads.items():
        if name in case_info and case_info[name][1] is not None:
            continue
        for load in loads:
            if load in patterns and patterns[load][1] is not None:
                case_info[name] = patterns[load]
                break
    seismic_cases = {name for name, loads in case_loads.items()
                     if loads & seismic_patterns}
    seismic_cases |= {name for name, kind in case_kind.items()
                      if "response spectrum" in kind.lower()}
    children: dict[str, set[str]] = {}
    combos = tables.get("Load Combination Definitions")
    if combos is not None:
        for row in combos.rows:
            name = str(_cell(row, "Name") or "")
            load = str(_cell(row, "Load Name") or "")
            if name and load:
                children.setdefault(name, set()).add(load)
    found: dict[str, bool] = {}

    def seismic(name: str) -> bool:
        if name not in found:
            found[name] = False
            found[name] = name in seismic_cases or any(
                seismic(child) for child in children.get(name, ()))
        return found[name]

    seismic_names = {name for name in seismic_cases | set(children) if seismic(name)}
    return case_info, case_loads, seismic_names


def _import_etabs(tables: dict[str, Table], warnings: list[str]) -> CsiImport:
    coords_table = tables.get("Point Object Connectivity")
    restraints_table = tables.get("Joint Assignments - Restraints")
    reactions_table = tables.get("Joint Reactions")
    if coords_table is None or restraints_table is None or reactions_table is None:
        missing = [name for name, table in (
            ("Point Object Connectivity", coords_table),
            ("Joint Assignments - Restraints", restraints_table),
            ("Joint Reactions", reactions_table)) if table is None]
        raise ValueError("missing tables: " + ", ".join(missing))

    coord_uid = _column(coords_table, "UniqueName")
    coord_x = _column(coords_table, "X", "GlobalX")
    coord_y = _column(coords_table, "Y")
    coord_z = _column(coords_table, "Z")
    if None in (coord_uid, coord_x, coord_y, coord_z):
        raise ValueError("Point Object Connectivity needs UniqueName, X, Y and Z")
    coord_conv = [_converter(coords_table, col, Kind.LENGTH)
                  for col in (coord_x, coord_y, coord_z)]
    coords = {str(_cell(row, coord_uid)): tuple(
        conv(_cell(row, col)) for conv, col in zip(coord_conv, (coord_x, coord_y, coord_z),
                                                   strict=True))
        for row in coords_table.rows}

    rest_uid = _column(restraints_table, "UniqueName")
    if rest_uid is None:
        raise ValueError("Joint Assigns - Restraints needs UniqueName")
    keys = ("UX", "UY", "UZ", "RX", "RY", "RZ")
    restraints = {str(_cell(row, rest_uid)): tuple(
        str(_cell(row, key) or "").lower() == "yes" for key in keys)
        for row in restraints_table.rows}
    support_ids = {uid for uid, values in restraints.items() if any(values)}
    all_coords = dict(coords)
    coords = {uid: xyz for uid, xyz in coords.items() if uid in support_ids}

    columns = _etabs_column_info(tables)
    conn = tables.get("Column Object Connectivity")
    found_columns: dict[str, ImportedColumn] = {}
    if conn is not None:
        frame_col = _column(conn, "UniqueName")
        i_col = _column(conn, "UniquePtI")
        j_col = _column(conn, "UniquePtJ")
        for row in conn.rows:
            if frame_col is None or i_col is None or j_col is None:
                break
            frame = str(_cell(row, frame_col))
            for end, other in ((i_col, j_col), (j_col, i_col)):
                uid = str(_cell(row, end))
                other_id = str(_cell(row, other))
                if uid not in coords or other_id not in all_coords:
                    continue
                support_z = coords[uid][2]
                if all_coords[other_id][2] <= support_z:
                    continue
                info = columns.get(frame, {})
                if uid in found_columns:
                    warnings.append(
                        f"joint {uid}: several columns, using frame {found_columns[uid].frame}")
                    continue
                found_columns[uid] = ImportedColumn(
                    frame, info.get("section", ""), info.get("shape", ""),
                    info.get("angle", 0.0), info.get("material", ""),
                    info.get("dimensions", {}))
    if conn is None:
        warnings.append("no 'Column Object Connectivity' data: supports imported without column")

    case_info, _, seismic_names = _etabs_cases(tables)
    reactions_uid = _column(reactions_table, "UniqueName")
    output_col = _column(reactions_table, "OutputCase")
    case_type_col = _column(reactions_table, "CaseType")
    step_col = _column(reactions_table, "StepType")
    force_cols = [_column(reactions_table, name) for name in ("FX", "FY", "FZ")]
    moment_cols = [_column(reactions_table, name) for name in ("MX", "MY", "MZ")]
    if None in (reactions_uid, output_col) or None in force_cols or None in moment_cols:
        raise ValueError("Joint Reactions needs UniqueName, OutputCase, FX/FY/FZ and MX/MY/MZ")
    force = [_converter(reactions_table, col, Kind.FORCE) for col in force_cols]
    moment = [_converter(reactions_table, col, Kind.MOMENT) for col in moment_cols]
    cases: dict[str, ImportedCase] = {}
    forces: dict[str, dict[str, Forces]] = {uid: {} for uid in coords}
    skipped: set[str] = set()
    step_cases: set[str] = set()
    for row in reactions_table.rows:
        uid = str(_cell(row, reactions_uid))
        output = str(_cell(row, output_col) or "")
        if uid not in forces:
            continue
        step = str(_cell(row, step_col) or "")
        if step == "Mode" or step not in ("", "Max", "Min", "Step By Step"):
            skipped.add(f"{output} ({step})")
            continue
        label = f"{output} ({step})" if step in ("Max", "Min") else output
        if step == "Step By Step":
            if label in forces[uid]:
                step_cases.add(output)
                continue
        if label not in cases:
            case_type = str(_cell(row, case_type_col) or "")
            design, load_type = case_info.get(output, ("", None))
            kind = (CaseKind.ENVELOPE if step in ("Max", "Min") else
                    CaseKind.COMBINATION if case_type == "Combination" else
                    CaseKind.LOAD_CASE)
            cases[label] = ImportedCase(label, output, case_type, kind, load_type, design,
                                        output in seismic_names)
        angle = found_columns[uid].angle if uid in found_columns else 0.0
        forces[uid][label] = _plate_forces(
            *(conv(_cell(row, col)) for conv, col in zip(force, force_cols, strict=True)),
            *(conv(_cell(row, col)) for conv, col in zip(moment, moment_cols, strict=True)),
            angle)
    if skipped:
        warnings.append("output cases skipped (not a single set of forces): "
                        + ", ".join(sorted(skipped)))
    if step_cases:
        warnings.append("Step By Step cases use the first output step: "
                        + ", ".join(sorted(step_cases)))
    supports = [Support(uid, *coords[uid], restraints[uid], found_columns.get(uid),
                        forces[uid]) for uid in sorted(coords, key=_natural)]
    return CsiImport(supports, cases, warnings)


def import_supports(source: str | Path | dict[str, Table]) -> CsiImport:
    """Supports, their column and reactions from exported SAP2000 / ETABS tables."""
    tables = ({t.name: t for t in (_normalize_table(table) for table in source.values())}
              if isinstance(source, dict) else read_tables(source))
    warnings: list[str] = []
    if _is_etabs(tables):
        return _import_etabs(tables, warnings)
    missing = [t for t in REQUIRED if t not in tables]
    if missing:
        raise ValueError("missing tables: " + ", ".join(missing))
    coords = _coordinates(tables["Joint Coordinates"])
    restraints = {j: r for j, r in _restraints(tables["Joint Restraint Assignments"]).items()
                  if any(r)}
    coords = {j: xyz for j, xyz in coords.items() if j in restraints}
    columns = _columns(tables, coords, warnings)
    case_info = _cases(tables)
    seismic = _seismic_cases(tables)

    reactions = tables["Joint Reactions"]
    force = {k: _converter(reactions, k, Kind.FORCE) for k in ("F1", "F2", "F3")}
    moment = {k: _converter(reactions, k, Kind.MOMENT) for k in ("M1", "M2", "M3")}
    cases: dict[str, ImportedCase] = {}
    forces: dict[str, dict[str, Forces]] = {j: {} for j in coords}
    skipped: set[str] = set()
    for r in reactions.rows:
        joint, output = str(r["Joint"]), str(r["OutputCase"])
        case_type, step = str(r.get("CaseType") or ""), str(r.get("StepType") or "")
        if joint not in forces:
            continue
        if step not in ("", "Max", "Min"):  # modes, steps of nonlinear or time history
            skipped.add(f"{output} ({case_type}, {step})")
            continue
        label = f"{output} ({step})" if step else output
        if label not in cases:
            design_type, load_type = case_info.get(output, ("", None))
            if step:
                kind = CaseKind.ENVELOPE
            elif case_type == "Combination":
                kind = CaseKind.COMBINATION
            else:
                kind = CaseKind.LOAD_CASE
            cases[label] = ImportedCase(label, output, case_type, kind, load_type, design_type,
                                        output in seismic)
        angle = columns[joint].angle if joint in columns else 0.0
        forces[joint][label] = _plate_forces(*(force[k](r[k]) for k in ("F1", "F2", "F3")),
                                             *(moment[k](r[k]) for k in ("M1", "M2", "M3")),
                                             angle)
    if skipped:
        warnings.append("output cases skipped (not a single set of forces): "
                        + ", ".join(sorted(skipped)))
    supports = [Support(j, *coords[j], restraints[j], columns.get(j), forces[j])
                for j in sorted(coords, key=_natural)]
    return CsiImport(supports, cases, warnings)


def _natural(label: str):
    return (0, int(label), "") if label.isdigit() else (1, 0, label)
