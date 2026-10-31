# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Report content, independent of the output format.

The report only renders the trace stored in each CheckResult: it never
recalculates anything.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from openconex import __version__
from openconex.connections.base_plate.check import (
    BearingAreaModel,
    PressureModel,
    check_envelope,
)
from openconex.core.checks import CheckResult, Status
from openconex.core.model import HSSKind, HSSShape
from openconex.i18n import tr
from openconex.io.project import Project
from openconex.report.figures import Figure, base_plate_figures
from openconex.units import Kind, UnitSystem, format_value

__all__ = ["CheckBlock", "Report", "Row", "build_base_plate_report", "factor_expression", "fmt"]

CODES = [
    "ANSI/AISC 360-22, Specification for Structural Steel Buildings",
    "AISC Design Guide 1, Base Connection Design for Steel Structures, 3rd ed. (2024)",
    "ACI 318-19, Building Code Requirements for Structural Concrete, Chapter 17",
    "ASCE/SEI 7-22, Minimum Design Loads and Associated Criteria, Chapter 2",
]


def fmt(value: float, kind: Kind, units: UnitSystem, precision: int = 4) -> str:
    if kind is Kind.DIMENSIONLESS:
        return f"{value:.{precision}g}"
    return format_value(value, kind, units, precision)


def factor_expression(factors: dict[str, float]) -> str:
    """Combination factors with explicit signs, e.g. ``1.2·D - 0.6·W``."""
    terms: list[str] = []
    for name, value in factors.items():
        term = f"{abs(value):g}·{name}"
        if not terms:
            terms.append(f"-{term}" if value < 0 else term)
        else:
            terms.append(f"{'-' if value < 0 else '+'} {term}")
    return " ".join(terms)


@dataclass
class Row:
    cells: list[str]
    status: str = ""


@dataclass
class TraceLine:
    symbol: str
    expression: str
    value: str
    clause: str


@dataclass
class CheckBlock:
    title: str
    check_id: str
    combo: str
    clause: str
    lines: list[TraceLine]
    demand: str
    capacity: str
    ratio: float
    status: str


@dataclass
class Report:
    language: str
    units: UnitSystem
    title: str
    subtitle: str
    info: list[tuple[str, str]]
    codes: list[str]
    assumptions: list[str]
    inputs: list[Row]
    cases: list[Row]
    case_headers: list[str]
    combinations: list[Row]
    summary: list[Row]
    checks: list[CheckBlock]
    ok: bool
    footer: str
    disclaimer: str
    results: list[CheckResult] = field(default_factory=list)
    figures: list[Figure] = field(default_factory=list)


def _block(result: CheckResult, lang: str, units: UnitSystem) -> CheckBlock:
    lines = [TraceLine(s.symbol, s.expression, fmt(s.value, s.kind, units), s.clause)
             for s in result.steps]
    return CheckBlock(
        title=tr(result.text_id, lang), check_id=result.id, combo=result.combo,
        clause=result.clause, lines=lines, demand=fmt(result.demand, result.kind, units),
        capacity=fmt(result.capacity, result.kind, units), ratio=result.ratio,
        status=result.status.value)


def build_base_plate_report(project: Project, today: dt.date | None = None) -> Report:
    info = project.info
    lang, units = info.language, info.unit_system()
    bp = project.base_plate_model()
    combos = project.load_combinations()
    results, _ = check_envelope(bp, combos, project.case_forces())

    # Governing combination of each check, in order of first appearance.
    governing: dict[str, CheckResult] = {}
    for r in results:
        if r.applicable and (r.id not in governing or r.ratio > governing[r.id].ratio):
            governing[r.id] = r
    ok = all(r.status is not Status.NG for r in results)

    def q(value, kind):
        return fmt(value, kind, units)

    L, T = Kind.LENGTH, Kind.THICKNESS
    inputs = [
        Row([tr("input.column", lang), f"{bp.column.name} ({bp.column.grade})"]),
        Row([tr("input.N", lang), q(bp.N, L)]),
        Row([tr("input.B", lang), q(bp.B, L)]),
        Row([tr("input.tp", lang), q(bp.tp, T)]),
        Row([tr("input.grade", lang), bp.plate_grade]),
        Row([tr("input.fc", lang), q(bp.fc, Kind.STRESS)]),
        Row([tr("input.A2_over_A1", lang), f"{bp.A2_over_A1:g}"]),
        Row([tr("input.rods", lang), f"{2 * bp.rods_per_side} × {q(bp.rod.diameter, L)} "
             f"{bp.rod.grade}"]),
        Row([tr("input.f", lang), q(bp.f, L)]),
        Row([tr("input.rod_spacing", lang), q(bp.rod_spacing, L)]),
        Row([tr("input.hef", lang), q(bp.hef, L)]),
    ]
    if bp.flange_weld:
        inputs.append(Row([tr("input.flange_weld", lang), q(bp.flange_weld, T)]))
    if bp.rod_bending_lever is not None:
        inputs.append(Row([tr("input.rod_bending_lever", lang), q(bp.rod_bending_lever, L)]))
    if bp.reinforcement is not None:
        reinforcement = bp.reinforcement
        inputs.append(Row([tr("input.reinforcement", lang),
                           f"{reinforcement.bars or '—'} · "
                           f"{q(reinforcement.area, Kind.AREA)} · "
                           f"{q(reinforcement.fy, Kind.STRESS)}"]))
    if bp.bearing_area is not None:
        inputs.append(Row([tr("input.bearing_area", lang), q(bp.bearing_area, Kind.AREA)]))
    if bp.weak_base is not None:
        weak = bp.weak_base
        inputs.append(Row([tr("input.weak_base", lang),
                           f"Ø {q(weak.reduced_diameter, L)} · "
                           f"L_str {q(weak.stretch_length, L)} · Rt {weak.Rt:g}"]))
    if bp.shear_lug:
        lug = bp.shear_lug
        inputs.append(Row([tr("input.shear_lug", lang),
                           f"{q(lug.width, L)} × {q(lug.thickness, T)}, h_sl = "
                           f"{q(lug.embedment, L)}, {q(lug.weld, T)} {lug.grade}; "
                           + tr(f"input.lug_direction_{lug.direction}", lang)]))
    forces = project.case_forces()
    biaxial = any(f.V3 or f.M2 for f in forces.values())
    case_headers = ["ID", tr("report.item", lang), "P", "V", "M"]
    if biaxial:
        case_headers += [tr("report.v_weak", lang), tr("report.m_weak", lang)]
    cases = [Row([c.name, tr(f"load.{c.type.value}", lang), q(f.P, Kind.FORCE),
                  q(f.V2, Kind.FORCE), q(f.M3, Kind.MOMENT)]
                 + ([q(f.V3, Kind.FORCE), q(f.M2, Kind.MOMENT)] if biaxial else []))
             for c, f in zip(project.cases, forces.values(), strict=True)]
    combinations = [Row([c.name, c.method.value, factor_expression(c.factors),
                         tr("report.custom_source", lang) if c.source == "custom" else c.source])
                    for c in combos]
    summary = [Row([tr(r.text_id, lang), r.combo, q(r.demand, r.kind), q(r.capacity, r.kind),
                    f"{r.ratio:.3f}"], r.status.value) for r in governing.values()]
    assumptions = [tr("report.assumption_rigid", lang), tr("report.assumption_aci_lrfd", lang)]
    if bp.cracked:
        assumptions.append(tr("report.assumption_cracked", lang))
    if bp.seismic:
        assumptions.append(tr("report.assumption_seismic", lang))
    if isinstance(bp.column, HSSShape):
        key = ("report.assumption_hss_round"
               if bp.column.kind is HSSKind.ROUND else "report.assumption_hss_rect")
        assumptions.append(tr(key, lang))
    if bp.pressure_model is PressureModel.TRIANGULAR:
        assumptions.append(tr("report.assumption_triangular", lang))
    if bp.bearing_area_model is BearingAreaModel.EFFECTIVE:
        assumptions.append(tr("report.assumption_effective_area", lang))
    if bp.weak_base is not None:
        assumptions.append(tr("report.assumption_weak_base", lang))
    figures = base_plate_figures(project, bp, lang, units)
    today = today or dt.date.today()
    return Report(
        language=lang, units=units, title=tr("report.title", lang),
        subtitle=tr("report.subtitle_base_plate", lang),
        info=[(tr("report.project", lang), info.name or "—")] + [
            (tr(f"report.{k}", lang), getattr(info, k) or "—")
            for k in ("number", "client", "engineer", "revision", "date")],
        codes=CODES, assumptions=assumptions, inputs=inputs, cases=cases, case_headers=case_headers,
        combinations=combinations, summary=summary,
        checks=[_block(r, lang, units) for r in governing.values()], ok=ok,
        footer=tr("report.generated", lang, generator=f"OpenConex {__version__}",
                  date=today.isoformat()),
        disclaimer=tr("report.disclaimer", lang), results=results, figures=figures)
