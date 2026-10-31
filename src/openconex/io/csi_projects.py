# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Base plate projects for the supports imported from SAP2000 / ETABS.

A template project gives what the analysis model does not have: plate, concrete,
anchor rods and options. Each support gets a copy with its column and loads:

* ``cases``: the unfactored load cases with a known type (D, L, Lr, S, W, E);
  OpenConex generates the ASCE 7-22 combinations of the template.
* ``combinations``: the combinations of the analysis program, already factored,
  each one entered as a case with a custom combination of factor 1.0.

With ``Grouping.COLUMN`` the supports with the same column section share one
project: each case is prefixed with its joint ("50: DEAD") and the combinations
are formed joint by joint, so loads of different supports are never added.

Each case keeps the column-axis components: P, V = V2 and M = M3 (strong axis),
V_weak = V3 and M_weak = M2 (weak axis, checked for biaxial bending).
"""

from __future__ import annotations

import math
import re
from enum import StrEnum

from openconex.core.loads import LoadType, Method
from openconex.core.model import HSSKind
from openconex.core.shapes import ShapeDatabaseError, aisc_shapes
from openconex.io.csi import CaseKind, CsiImport, ImportedColumn, Support
from openconex.io.project import (
    CustomCombinationInput,
    HSSSectionInput,
    LoadCaseInput,
    Project,
    WSectionInput,
)

__all__ = ["Grouping", "LoadSource", "base_plate_projects", "column_input"]

class Grouping(StrEnum):
    JOINT = "joint"
    """One project per support."""
    COLUMN = "column"
    """One project per column section with the loads of all its supports."""


class LoadSource(StrEnum):
    CASES = "cases"
    COMBINATIONS = "combinations"


# CSI material name -> OpenConex steel grade (rectangular HSS / round HSS / other)
_GRADES = (
    (r"A992", "ASTM A992"),
    (r"A913.*GR\.?\s*70", "ASTM A913 Gr. 70"),
    (r"A913.*GR\.?\s*65", "ASTM A913 Gr. 65"),
    (r"A913.*GR\.?\s*60", "ASTM A913 Gr. 60"),
    (r"A913.*GR\.?\s*50", "ASTM A913 Gr. 50"),
    (r"A572.*GR\.?\s*65", "ASTM A572 Gr. 65"),
    (r"A572.*GR\.?\s*60", "ASTM A572 Gr. 60"),
    (r"A572.*GR\.?\s*55", "ASTM A572 Gr. 55"),
    (r"A572.*GR\.?\s*50", "ASTM A572 Gr. 50"),
    (r"A572.*GR\.?\s*42", "ASTM A572 Gr. 42"),
    (r"A529.*GR\.?\s*55", "ASTM A529 Gr. 55"),
    (r"A529.*GR\.?\s*50", "ASTM A529 Gr. 50"),
    (r"A709.*GR\.?\s*50W", "ASTM A709 Gr. 50W"),
    (r"A709.*GR\.?\s*50", "ASTM A709 Gr. 50"),
    (r"A709.*GR\.?\s*36", "ASTM A709 Gr. 36"),
    (r"A1043.*GR\.?\s*50", "ASTM A1043 Gr. 50"),
    (r"A1043.*GR\.?\s*36", "ASTM A1043 Gr. 36"),
    (r"A1065.*GR\.?\s*50W", "ASTM A1065 Gr. 50W"),
    (r"A1065.*GR\.?\s*50", "ASTM A1065 Gr. 50"),
    (r"A500.*GR\.?\s*B", "ASTM A500 Gr. B"),
    (r"A500.*GR\.?\s*C", "ASTM A500 Gr. C"),
    (r"A501.*GR\.?\s*A", "ASTM A501 Gr. A"),
    (r"A501.*GR\.?\s*B", "ASTM A501 Gr. B"),
    (r"A53.*GR\.?\s*B", "ASTM A53 Gr. B"),
    (r"A1085", "ASTM A1085"),
    (r"A847", "ASTM A847"),
    (r"A588", "ASTM A588"),
    (r"A36", "ASTM A36"),
)


def _grade(material: str, hss: HSSKind | None) -> str | None:
    for pattern, grade in _GRADES:
        if re.search(pattern, material, re.IGNORECASE):
            if grade.startswith("ASTM A500"):
                if hss is None:
                    return None
                return f"{grade} ({'round' if hss is HSSKind.ROUND else 'rectangular'})"
            return grade
    return None


def _mm(value: float) -> str:
    return f"{value:.4g} mm"


def column_input(column: ImportedColumn, fallback_grade: str | None = None):
    """Project column (AISC label or generic section) and steel grade for a CSI section.

    Returns (column, grade, warning). When the CSI material is not in the
    OpenConex library, ``fallback_grade`` is used and a warning is returned;
    with no fallback the column is rejected.
    """
    dims, shape = column.dimensions, column.shape.lower()
    grade = _grade(column.material, None)
    used = grade or fallback_grade
    if shape in ("i/wide flange", "steel i/wide flange") or "wide flange" in shape:
        warning = (None if grade else
                   f"unknown material {column.material!r}, using {used}")
        if used is None:
            return None, None, f"unknown material {column.material!r} and no fallback"
        try:
            aisc_shapes().get(column.section)
            return column.section, used, warning
        except ShapeDatabaseError:
            pass
        section = WSectionInput(type="W", name=column.section, d=_mm(dims["t3"]),
                                bf=_mm(dims["t2"]), tf=_mm(dims["tf"]), tw=_mm(dims["tw"]),
                                grade=used)
        return section, used, warning
    if shape in ("box/tube", "steel tube") or "tube" in shape:
        kind = HSSKind.SQUARE if math.isclose(dims["t3"], dims["t2"]) else HSSKind.RECTANGULAR
        grade = _grade(column.material, kind)
        used = grade or fallback_grade
        if used is None:
            return None, None, f"unknown material {column.material!r} and no fallback"
        section = HSSSectionInput(type="HSS", name=column.section, shape=kind,
                                  d=_mm(dims["t3"]),
                                  bf=None if kind is HSSKind.SQUARE else _mm(dims["t2"]),
                                  t=_mm(dims["tf"]), grade=used)
        return section, used, (None if grade else
                               f"unknown material {column.material!r}, using {used}")
    if shape in ("pipe", "steel pipe"):
        grade = _grade(column.material, HSSKind.ROUND)
        used = grade or fallback_grade
        if used is None:
            return None, None, f"unknown material {column.material!r} and no fallback"
        section = HSSSectionInput(type="HSS", name=column.section, shape=HSSKind.ROUND,
                                  d=_mm(dims["t3"]), t=_mm(dims["tw"]), grade=used)
        return section, used, (None if grade else
                               f"unknown material {column.material!r}, using {used}")
    return None, None, f"section {column.section!r} ({column.shape}) is not supported"


def _case(name: str, load_type: LoadType, forces) -> LoadCaseInput:
    return LoadCaseInput(name=name, type=load_type, P=f"{forces.P:.10g} N",
                         V=f"{forces.V2:.10g} N", M=f"{forces.M3:.10g} N*mm",
                         V_weak=f"{forces.V3:.10g} N", M_weak=f"{forces.M2:.10g} N*mm")


def _loads(support: Support, data: CsiImport, template: Project, source: LoadSource,
           include: str | None, envelopes: bool, method: Method | None, warnings: list[str]):
    pattern = re.compile(include) if include else None
    if source is LoadSource.CASES:
        names = [c.name for c in data.cases.values() if c.kind is CaseKind.LOAD_CASE
                 and (pattern is None or pattern.search(c.name))]
        untyped = [n for n in names if data.cases[n].load_type is None]
        if untyped:
            warnings.append(f"load cases without a design type, not used: {', '.join(untyped)}")
        cases = [_case(n, data.cases[n].load_type, support.forces[n])
                 for n in names if data.cases[n].load_type is not None and n in support.forces]
        combinations = template.combinations.model_copy(update={"include_code": True,
                                                                "custom": []})
        return cases, combinations, [n for n in names if n in support.forces]
    kinds = {CaseKind.COMBINATION} | ({CaseKind.ENVELOPE} if envelopes else set())
    names = [c.name for c in data.cases.values() if c.kind in kinds
             and (pattern is None or pattern.search(c.name)) and c.name in support.forces]
    method = method or (template.combinations.methods or [Method.LRFD])[0]
    cases = [_case(n, LoadType.DEAD, support.forces[n]) for n in names]
    custom = [CustomCombinationInput(
        name=n, method=method, factors={n: 1.0}, seismic=data.cases[n].seismic,
        source=f"{data.cases[n].case_type} {data.cases[n].output_case}") for n in names]
    combinations = template.combinations.model_copy(update={"include_code": False,
                                                            "custom": custom})
    return cases, combinations, names


def base_plate_projects(data: CsiImport, template: Project,
                        source: LoadSource = LoadSource.CASES, include: str | None = None,
                        envelopes: bool = False, method: Method | None = None,
                        group: Grouping = Grouping.JOINT,
                        ) -> tuple[dict[str, Project], list[str]]:
    """Base plate projects for the supports with a column, from ``template``.

    ``include`` is a regular expression on the case or combination names;
    ``envelopes`` adds the Max/Min envelopes in ``combinations`` mode, and
    ``method`` sets the method of those combinations (template's first by default).
    Returns ({joint or column section: project}, warnings).
    """
    projects, warnings = _joint_projects(data, template, source, include, envelopes, method)
    warnings = _merge_warnings(warnings)
    if group is Grouping.JOINT:
        return projects, warnings
    sections: dict[str, list[str]] = {}
    for support in data.supports:
        if support.joint in projects:
            sections.setdefault(support.column.section, []).append(support.joint)
    return {section: _merge(template, section, {j: projects[j] for j in joints})
            for section, joints in sections.items()}, warnings


def _merge_warnings(warnings: list[str]) -> list[str]:
    """Join "joint X: message" lines that repeat the same message."""
    joints: dict[str, list[str]] = {}
    for warning in warnings:
        tag, sep, message = warning.partition(": ")
        if sep and tag.startswith("joint "):
            joints.setdefault(message, []).append(tag.removeprefix("joint "))
        else:
            joints.setdefault(warning, [])
    return [f"joint{'s' if len(j) > 1 else ''} {', '.join(j)}: {m}" if j else m
            for m, j in joints.items()]


def _merge(template: Project, section: str, projects: dict[str, Project]) -> Project:
    """One project with the cases of several supports, combined support by support."""
    cases, custom = [], []
    for joint, project in projects.items():
        prefix = f"{joint}: "
        cases += [c.model_copy(update={"name": prefix + c.name}) for c in project.cases]
        custom += [CustomCombinationInput(
            name=prefix + c.name, method=c.method,
            factors={prefix + k: v for k, v in c.factors.items()}, seismic=c.seismic,
            overstrength=c.overstrength, allowable_increase=c.allowable_increase,
            source=c.source) for c in project.load_combinations()]
    first = next(iter(projects.values()))
    info = template.info.model_copy(update={
        "name": f"{template.info.name} - {section} "
                f"(joints {', '.join(projects)})".strip(" -")})
    combinations = template.combinations.model_copy(update={"include_code": False,
                                                            "custom": custom})
    merged = template.model_copy(update={"info": info, "base_plate": first.base_plate,
                                         "cases": cases, "combinations": combinations})
    return Project.model_validate(merged.model_dump())


def _joint_projects(data, template, source, include, envelopes, method):
    projects: dict[str, Project] = {}
    warnings: list[str] = []
    for support in data.supports:
        tag = f"joint {support.joint}"
        if support.column is None:
            warnings.append(f"{tag}: no column, skipped")
            continue
        column, grade, problem = column_input(support.column,
                                              template.base_plate.column_grade)
        if column is None:
            warnings.append(f"{tag}: {problem}, skipped")
            continue
        if problem:
            warnings.append(f"{tag}: {problem}")
        notes: list[str] = []
        cases, combinations, _ = _loads(support, data, template, source, include,
                                           envelopes, method, notes)
        if not cases:
            warnings.append(f"{tag}: no load cases selected, skipped")
            continue
        warnings += [f"{tag}: {n}" for n in notes]
        base_plate = template.base_plate.model_copy(update={
            "column": column, "column_grade": grade or template.base_plate.column_grade})
        info = template.info.model_copy(update={
            "name": f"{template.info.name} - {tag} ({support.column.section})".strip(" -")})
        project = template.model_copy(update={"info": info, "base_plate": base_plate,
                                              "cases": cases, "combinations": combinations})
        projects[support.joint] = Project.model_validate(project.model_dump())
    return projects, warnings
