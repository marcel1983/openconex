# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Shear connection projects for the beam ends imported from SAP2000.

The template project gives the connection (type, plate or angles, bolts,
welds and options). Each beam end gets a copy with its beam, its support (and
whether the connection goes to the flange or the web) and its loads, with the
same two load sources as the base plate import (see :mod:`csi_projects`).

With ``ShearGrouping.SECTION`` the ends with the same beam section, support
section and support element share one project; each case is prefixed with the
end ("B12-J: DEAD") and the combinations are formed end by end.
"""

from __future__ import annotations

from enum import StrEnum

from openconex.core.loads import LoadType, Method
from openconex.io.csi_beams import BeamEnd, CsiBeamImport
from openconex.io.csi_projects import LoadSource, _loads, column_input
from openconex.io.project import (
    CustomCombinationInput,
    LoadCaseInput,
    Project,
    WSectionInput,
)

__all__ = ["ShearGrouping", "shear_projects"]


class ShearGrouping(StrEnum):
    END = "end"
    """One project per beam end."""
    SECTION = "section"
    """One project per beam section, support section and support element."""


def _shear_case(name: str, load_type: LoadType, forces) -> LoadCaseInput:
    return LoadCaseInput(name=name, type=load_type, P=f"{forces.P:.10g} N",
                         V=f"{forces.V2:.10g} N")


def _section(frame, fallback: str):
    """Catalog label or generic W section of an imported I-shape; None otherwise."""
    section, grade, problem = column_input(frame, fallback)
    if section is None or not (isinstance(section, str | WSectionInput)):
        return None, None, problem or f"section {frame.section!r} is not an I-shape"
    if isinstance(section, str) and not section.upper().startswith(("W", "M", "S", "HP")):
        return None, None, f"section {frame.section!r} is not an I-shape"
    return section, grade, problem


def _end_project(end: BeamEnd, data: CsiBeamImport, template: Project, source, include,
                 envelopes, method, warnings: list[str]) -> Project | None:
    tag = f"beam {end.label}"
    sc = template.shear_connection
    beam, beam_grade, problem = _section(end.beam, sc.beam_grade)
    if beam is None:
        warnings.append(f"{tag}: beam {problem}, skipped")
        return None
    if problem:
        warnings.append(f"{tag}: beam {problem}")
    support, support_grade, problem = _section(end.support, sc.support_grade)
    if support is None:
        warnings.append(f"{tag}: support {problem}, skipped")
        return None
    if problem:
        warnings.append(f"{tag}: support {problem}")
    notes: list[str] = []
    cases, combinations, _ = _loads(end, data, template, source, include, envelopes, method,
                                    notes, case=_shear_case)
    warnings += [f"{tag}: {n}" for n in notes]
    if not cases:
        warnings.append(f"{tag}: no load cases selected, skipped")
        return None
    connection = sc.model_copy(update={
        "beam": beam, "beam_grade": beam_grade or sc.beam_grade, "support": support,
        "support_grade": support_grade or sc.support_grade,
        "support_element": end.support_element})
    info = template.info.model_copy(update={
        "name": f"{template.info.name} - {tag} ({end.beam.section} → "
                f"{end.support.section} {end.support_element})".strip(" -")})
    project = template.model_copy(update={"info": info, "shear_connection": connection,
                                          "cases": cases, "combinations": combinations})
    return Project.model_validate(project.model_dump())


def _merge(template: Project, key: str, projects: dict[str, Project]) -> Project:
    cases, custom = [], []
    for label, project in projects.items():
        prefix = f"{label}: "
        cases += [c.model_copy(update={"name": prefix + c.name}) for c in project.cases]
        custom += [CustomCombinationInput(
            name=prefix + c.name, method=c.method,
            factors={prefix + k: v for k, v in c.factors.items()}, seismic=c.seismic,
            overstrength=c.overstrength, allowable_increase=c.allowable_increase,
            source=c.source) for c in project.load_combinations()]
    first = next(iter(projects.values()))
    info = template.info.model_copy(update={
        "name": f"{template.info.name} - {key} (ends {', '.join(projects)})".strip(" -")})
    combinations = template.combinations.model_copy(update={"include_code": False,
                                                            "custom": custom})
    merged = template.model_copy(update={"info": info,
                                         "shear_connection": first.shear_connection,
                                         "cases": cases, "combinations": combinations})
    return Project.model_validate(merged.model_dump())


def shear_projects(data: CsiBeamImport, template: Project,
                   source: LoadSource = LoadSource.CASES, include: str | None = None,
                   envelopes: bool = False, method: Method | None = None,
                   group: ShearGrouping = ShearGrouping.END,
                   ) -> tuple[dict[str, Project], list[str]]:
    """Shear connection projects for the imported beam ends, from ``template``.

    Returns ({beam end or group key: project}, warnings).
    """
    if template.shear_connection is None:
        raise ValueError("the template must be a shear connection project "
                         "(shear_connection)")
    from openconex.io.csi import CaseKind

    if (source is LoadSource.CASES and template.combinations.SDS is None
            and any(c.load_type is LoadType.SEISMIC and c.kind is CaseKind.LOAD_CASE
                    for c in data.cases.values())):
        raise ValueError("the model has seismic load cases: set combinations.SDS in the "
                         "template (SDS = 0 omits the vertical effect Ev)")
    warnings: list[str] = []
    projects: dict[str, Project] = {}
    keys: dict[str, str] = {}
    for end in data.ends:
        project = _end_project(end, data, template, source, include, envelopes, method,
                               warnings)
        if project is not None:
            projects[end.label] = project
            keys[end.label] = (f"{end.beam.section}_{end.support.section}_"
                               f"{end.support_element}")
    if group is ShearGrouping.END:
        return projects, warnings
    groups: dict[str, list[str]] = {}
    for label, key in keys.items():
        groups.setdefault(key, []).append(label)
    return {key: _merge(template, key, {label: projects[label] for label in labels})
            for key, labels in groups.items()}, warnings
