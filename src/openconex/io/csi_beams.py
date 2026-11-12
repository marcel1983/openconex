# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Beam-end reactions from SAP2000 database tables, for shear connections.

Each horizontal frame whose end is released in M3 (pinned) is a beam end with
a shear connection. The support is the column (vertical frame) at that joint,
or else a horizontal girder that crosses the beam. Tables used:

======================================  ==========================================
Table                                   Use
======================================  ==========================================
Joint Coordinates                       frame directions
Connectivity - Frame                    joints of each frame
Frame Section Assignments               beam and support sections
Frame Section Properties 01 - General   section shape, material and dimensions
Frame Local Axes Assignments 1 - Typical  rotation of the column (flange or web)
Frame Release Assignments 1 - General   pinned ends (M3 released)
Element Forces - Frames                 end forces per output case
Load Case Definitions, Combination Definitions, Load Pattern Definitions,
Case - Static 1 - Load Assignments      case types and seismic cases, as for supports
======================================  ==========================================

Forces of each end, in the convention of the shear connection projects:
``V2`` is the beam shear at the end station (its absolute value is used) and
``P`` the axial force with compression positive (SAP2000 gives tension
positive). ETABS exports are not read yet.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

from openconex.core.loads import Forces
from openconex.io.csi import (
    CaseKind,
    ImportedCase,
    ImportedColumn,
    Table,
    _cases,
    _cell,
    _column,
    _converter,
    _coordinates,
    _first_table,
    _is_etabs,
    _natural,
    _normalize_table,
    _section_props,
    _seismic_cases,
    read_tables,
)
from openconex.units import Kind

__all__ = ["BeamEnd", "CsiBeamImport", "import_beam_ends"]

REQUIRED = ("Joint Coordinates", "Connectivity - Frame", "Frame Section Assignments",
            "Element Forces - Frames")

_FORCES = ("Element Forces - Frames", "Element Forces - Frame", "Frame Element Forces")
_RELEASES = ("Frame Release Assignments 1 - General", "Frame Releases 1 - General",
             "Frame Release Assignments")


@dataclass(frozen=True)
class BeamEnd:
    frame: str
    end: str
    """``I`` or ``J``."""
    joint: str
    beam: ImportedColumn
    """Beam section (the class is shared with the imported columns)."""
    support: ImportedColumn
    support_kind: str
    """``column`` or ``girder``."""
    support_element: str
    """``flange`` or ``web`` of the support that receives the connection."""
    forces: dict[str, Forces] = field(default_factory=dict)

    @property
    def label(self) -> str:
        return f"{self.frame}-{self.end}"


@dataclass(frozen=True)
class CsiBeamImport:
    ends: list[BeamEnd]
    cases: dict[str, ImportedCase]
    warnings: list[str]


def _frame_sections(tables: dict[str, Table]) -> dict[str, ImportedColumn]:
    sections = {str(r["Frame"]): str(r.get("AnalSect") or r.get("DesignSect") or "")
                for r in tables["Frame Section Assignments"].rows}
    angles = {str(r["Frame"]): float(r.get("Angle") or 0.0)
              for r in tables["Frame Local Axes Assignments 1 - Typical"].rows} \
        if "Frame Local Axes Assignments 1 - Typical" in tables else {}
    props = _section_props(tables.get("Frame Section Properties 01 - General"))
    out = {}
    for frame, section in sections.items():
        shape, material, dims = props.get(section, ("", "", {}))
        out[frame] = ImportedColumn(frame, section, shape, angles.get(frame, 0.0), material,
                                    dims)
    return out


def _releases(tables: dict[str, Table]) -> dict[str, tuple[bool, bool]] | None:
    table = _first_table(tables, *_RELEASES)
    if table is None:
        return None
    return {str(_cell(r, "Frame")): (str(_cell(r, "M3I") or "").lower() == "yes",
                                     str(_cell(r, "M3J") or "").lower() == "yes")
            for r in table.rows}


def _support_element(beam_dir: tuple[float, float], column: ImportedColumn) -> str:
    """Flange or web of a vertical I column for a beam along ``beam_dir``.

    For a vertical frame SAP2000 takes local axis 2 along global X rotated by the
    local-axes angle; the web of an I section lies along axis 2, so a beam along
    axis 2 frames into the flange and one along axis 3 into the web.
    """
    a = math.radians(column.angle)
    along_2 = abs(beam_dir[0] * math.cos(a) + beam_dir[1] * math.sin(a))
    along_3 = abs(-beam_dir[0] * math.sin(a) + beam_dir[1] * math.cos(a))
    return "flange" if along_2 >= along_3 else "web"


def import_beam_ends(source: str | Path | dict[str, Table],
                     pinned_only: bool = True) -> CsiBeamImport:
    """Beam ends with a shear connection, their support and end forces.

    With ``pinned_only`` (default) only the ends released in M3 are used; when
    the model has no release table every beam end is used, with a warning.
    """
    tables = ({t.name: t for t in (_normalize_table(table) for table in source.values())}
              if isinstance(source, dict) else read_tables(source))
    if _is_etabs(tables):
        raise ValueError("beam-end reactions from ETABS are not supported yet; "
                         "export the model from SAP2000")
    forces_table = _first_table(tables, *_FORCES)
    missing = [t for t in REQUIRED[:3] if t not in tables]
    if forces_table is None:
        missing.append("Element Forces - Frames")
    if missing:
        raise ValueError("missing tables: " + ", ".join(missing))
    warnings: list[str] = []
    coords = _coordinates(tables["Joint Coordinates"])
    sections = _frame_sections(tables)
    releases = _releases(tables)
    if pinned_only and releases is None:
        warnings.append("no frame release table: every beam end is taken as a shear "
                        "connection")

    # Classify the frames: vertical (columns) and horizontal (beams).
    joints_of: dict[str, tuple[str, str]] = {}
    at_joint: dict[str, list[str]] = {}
    vertical: set[str] = set()
    direction: dict[str, tuple[float, float]] = {}
    for r in tables["Connectivity - Frame"].rows:
        frame, i, j = str(r["Frame"]), str(r["JointI"]), str(r["JointJ"])
        if i not in coords or j not in coords:
            continue
        (xi, yi, zi), (xj, yj, zj) = coords[i], coords[j]
        dx, dy, dz = xj - xi, yj - yi, zj - zi
        length = math.sqrt(dx * dx + dy * dy + dz * dz)
        if length == 0.0:
            continue
        joints_of[frame] = (i, j)
        at_joint.setdefault(i, []).append(frame)
        at_joint.setdefault(j, []).append(frame)
        horizontal = math.hypot(dx, dy)
        if horizontal <= 1e-3 * length:
            vertical.add(frame)
        elif abs(dz) <= 1e-3 * length:
            direction[frame] = (dx / horizontal, dy / horizontal)

    # End forces at the first and last output station of each beam.
    case_info = _cases(tables)
    seismic = _seismic_cases(tables)
    t = forces_table
    frame_col, station_col = _column(t, "Frame"), _column(t, "Station")
    output_col, type_col = _column(t, "OutputCase"), _column(t, "CaseType")
    step_col = _column(t, "StepType")
    p_col, v_col = _column(t, "P"), _column(t, "V2")
    if None in (frame_col, station_col, output_col, p_col, v_col):
        raise ValueError("Element Forces - Frames needs Frame, Station, OutputCase, P and V2")
    to_force = {c: _converter(t, c, Kind.FORCE) for c in (p_col, v_col)}
    to_length = _converter(t, station_col, Kind.LENGTH)
    stations: dict[str, tuple[float, float]] = {}
    for r in t.rows:
        frame = str(_cell(r, frame_col))
        if frame not in direction:
            continue
        s = to_length(_cell(r, station_col))
        lo, hi = stations.get(frame, (s, s))
        stations[frame] = (min(lo, s), max(hi, s))
    cases: dict[str, ImportedCase] = {}
    end_forces: dict[tuple[str, str], dict[str, Forces]] = {}
    skipped: set[str] = set()
    for r in t.rows:
        frame = str(_cell(r, frame_col))
        if frame not in stations:
            continue
        s = to_length(_cell(r, station_col))
        lo, hi = stations[frame]
        ends = [e for e, at in (("I", lo), ("J", hi)) if math.isclose(s, at, abs_tol=1e-6)]
        if not ends:
            continue
        output = str(_cell(r, output_col) or "")
        case_type = str(_cell(r, type_col) or "") if type_col else ""
        step = str(_cell(r, step_col) or "") if step_col else ""
        if step not in ("", "Max", "Min"):
            skipped.add(f"{output} ({case_type}, {step})")
            continue
        label = f"{output} ({step})" if step else output
        if label not in cases:
            design_type, load_type = case_info.get(output, ("", None))
            kind = (CaseKind.ENVELOPE if step else
                    CaseKind.COMBINATION if case_type == "Combination" else CaseKind.LOAD_CASE)
            cases[label] = ImportedCase(label, output, case_type, kind, load_type, design_type,
                                        output in seismic)
        value = Forces(P=-to_force[p_col](_cell(r, p_col)),
                       V2=to_force[v_col](_cell(r, v_col)))
        for end in ends:
            end_forces.setdefault((frame, end), {})[label] = value
    if skipped:
        warnings.append("output cases skipped (not a single set of forces): "
                        + ", ".join(sorted(skipped)))

    found: list[BeamEnd] = []
    for frame in sorted(direction, key=_natural):
        released = releases.get(frame, (False, False)) if releases is not None else (True, True)
        for index, end in enumerate(("I", "J")):
            if pinned_only and not released[index]:
                continue
            joint = joints_of[frame][index]
            tag = f"beam {frame}-{end}"
            if (frame, end) not in end_forces:
                warnings.append(f"{tag}: no forces in Element Forces - Frames, skipped")
                continue
            others = [f for f in at_joint.get(joint, []) if f != frame]
            columns = [f for f in others if f in vertical]
            girders = [f for f in others if f in direction and abs(
                direction[f][0] * direction[frame][0]
                + direction[f][1] * direction[frame][1]) < math.cos(math.radians(45))]
            if columns:
                support = sections[columns[0]]
                kind = "column"
                element = _support_element(direction[frame], support)
            elif girders:
                support, kind, element = sections[girders[0]], "girder", "web"
            else:
                warnings.append(f"{tag}: no column or girder at joint {joint}, skipped")
                continue
            found.append(BeamEnd(frame, end, joint, sections[frame], support, kind, element,
                                 end_forces[(frame, end)]))
    if not found:
        warnings.append("no beam ends with a shear connection were found")
    return CsiBeamImport(found, cases, warnings)
