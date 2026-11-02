# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Generic Excel/CSV import for base plate projects.

The first row is a header; each following row is one load case of one support:

``support``, ``case``, ``type``, ``column``, ``P``, ``V``, ``M``, ``V_weak``,
``M_weak``. ``support`` and ``case`` are required. Numeric cells use the selected
unit system; text cells may carry their own unit (``"25 kN"``).
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from openconex.core.loads import LoadType
from openconex.core.shapes import ShapeDatabaseError, aisc_shapes
from openconex.io.project import ColumnSectionInput, LoadCaseInput, Project
from openconex.units import PRESETS, Kind, UnitSystem, from_internal, parse

__all__ = ["projects_from_table", "read_table"]

HEADERS = {
    "support": "support",
    "apoyo": "support",
    "joint": "support",
    "nodo": "support",
    "case": "case",
    "caso": "case",
    "type": "type",
    "tipo": "type",
    "column": "column",
    "columna": "column",
    "p": "P",
    "v": "V",
    "m": "M",
    "v_weak": "V_weak",
    "v debil": "V_weak",
    "m_weak": "M_weak",
    "m debil": "M_weak",
}


def _key(value: object) -> str:
    return str(value or "").strip().casefold()


def _normalise(row: Mapping[Any, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for raw_key, value in row.items():
        key = HEADERS.get(_key(raw_key))
        if key is not None:
            out[key] = value
    return out


def read_table(path: str | Path) -> list[dict[str, Any]]:
    """Read the first sheet of an ``.xlsx`` or the rows of a ``.csv``."""
    path = Path(path)
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return [_normalise(row) for row in csv.DictReader(handle)]
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = workbook.active
        rows = sheet.iter_rows(values_only=True)
        try:
            headers = next(rows)
        except StopIteration:
            return []
        return [_normalise(dict(zip(headers, row, strict=False))) for row in rows]
    finally:
        workbook.close()


def _stored(value: float, kind: Kind, units: UnitSystem) -> str:
    return f"{from_internal(value, kind, units):.10g}"


def _quantity(row: Mapping[str, Any], key: str, kind: Kind,
              units: UnitSystem) -> float:
    raw = row.get(key)
    if raw is None or str(raw).strip() == "":
        return 0.0
    try:
        return parse(str(raw).strip(), kind, units)
    except Exception as exc:
        raise ValueError(f"{key}: {exc}") from exc


def _column(value: str, template: Project) -> tuple[ColumnSectionInput | str, str]:
    if not value:
        return template.base_plate.column, template.base_plate.column_grade
    for section in template.sections:
        if section.label() == value:
            return section, section.grade
    try:
        return aisc_shapes().get(value).label, template.base_plate.column_grade
    except ShapeDatabaseError as exc:
        raise ValueError(f"unknown column {value!r}") from exc


def projects_from_table(rows: Iterable[Mapping[str, Any]], template: Project,
                        units: UnitSystem) -> tuple[dict[str, Project], list[str]]:
    """Create one project per support from a normalised table."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    warnings: list[str] = []
    for index, raw in enumerate(rows, start=2):
        row = dict(raw)
        support = str(row.get("support") or "").strip()
        case = str(row.get("case") or "").strip()
        if not support or not case:
            warnings.append(f"fila {index}: faltan support o case")
            continue
        type_text = str(row.get("type") or "D").strip()
        try:
            row["_type"] = LoadType(type_text)
        except ValueError:
            warnings.append(f"fila {index}: tipo de caso desconocido {type_text!r}")
            continue
        row["_support"], row["_case"] = support, case
        grouped.setdefault(support, []).append(row)

    projects: dict[str, Project] = {}
    for support, rows in grouped.items():
        cases: list[LoadCaseInput] = []
        names: set[str] = set()
        column_text = ""
        skipped = False
        for row in rows:
            case = row["_case"]
            if case in names:
                warnings.append(f"support {support}: caso repetido {case!r}")
                continue
            names.add(case)
            if row.get("column"):
                candidate = str(row["column"]).strip()
                if column_text and candidate != column_text:
                    warnings.append(f"support {support}: columnas distintas; se usa "
                                    f"{column_text!r}")
                column_text = column_text or candidate
            try:
                p = _quantity(row, "P", Kind.FORCE, units)
                v = _quantity(row, "V", Kind.FORCE, units)
                m = _quantity(row, "M", Kind.MOMENT, units)
                v_weak = _quantity(row, "V_weak", Kind.FORCE, units)
                m_weak = _quantity(row, "M_weak", Kind.MOMENT, units)
            except ValueError as exc:
                warnings.append(f"support {support}, caso {case}: {exc}")
                skipped = True
                continue
            cases.append(LoadCaseInput(
                name=case, type=row["_type"],
                P=_stored(p, Kind.FORCE, units), V=_stored(v, Kind.FORCE, units),
                M=_stored(m, Kind.MOMENT, units),
                V_weak=_stored(v_weak, Kind.FORCE, units),
                M_weak=_stored(m_weak, Kind.MOMENT, units)))
        if skipped and not cases:
            continue
        if not cases:
            warnings.append(f"support {support}: sin casos válidos")
            continue
        try:
            column, grade = _column(column_text, template)
        except ValueError as exc:
            warnings.append(f"support {support}: {exc}")
            continue
        project = template.model_copy(deep=True)
        project.info.name = (f"{template.info.name} - {support}"
                             if template.info.name else support)
        project.info.units = units.name if units.name in PRESETS else units
        project.base_plate.column = column
        project.base_plate.column_grade = grade
        project.cases = cases
        project.combinations = template.combinations.model_copy(
            update={"include_code": True, "custom": []})
        try:
            projects[support] = Project.model_validate(project.model_dump())
        except Exception as exc:
            warnings.append(f"support {support}: {exc}")
    return projects, warnings
