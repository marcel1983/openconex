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
}


@dataclass(frozen=True)
class Table:
    name: str
    columns: list[str]
    units: list[str]
    rows: list[dict[str, Any]]

    def unit(self, column: str) -> str:
        return self.units[self.columns.index(column)]


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
            tables[name] = Table(name, columns, units, data)
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


def import_supports(source: str | Path | dict[str, Table]) -> CsiImport:
    """Supports, their column and reactions from exported SAP2000 / ETABS tables."""
    tables = source if isinstance(source, dict) else read_tables(source)
    missing = [t for t in REQUIRED if t not in tables]
    if missing:
        raise ValueError("missing tables: " + ", ".join(missing))
    warnings: list[str] = []
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
