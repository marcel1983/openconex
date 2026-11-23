# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Report content of a beam or column splice project."""

from __future__ import annotations

import datetime as dt

from openconex import __version__
from openconex.connections.splice.splice import ColumnSplice, check_splice_envelope
from openconex.core.checks import CheckResult, Status
from openconex.i18n import tr
from openconex.io.project import Project
from openconex.report.builder import Report, Row, _block, factor_expression, fmt
from openconex.units import Kind, UnitSystem

__all__ = ["SPLICE_CODES", "build_splice_report", "splice_figures"]

SPLICE_CODES = [
    "ANSI/AISC 360-22, Specification for Structural Steel Buildings",
    "AISC Steel Construction Manual, 16th ed., Parts 7, 9 and 14",
    "ASCE/SEI 7-22, Minimum Design Loads and Associated Criteria, Chapter 2",
]


def _inputs(project: Project, lang: str, units: UnitSystem) -> list[Row]:
    sp = project.splice
    model = project.splice_model()

    def q(value, kind=Kind.LENGTH):
        return fmt(project.quantity(value, kind), kind, units)

    def length(value):
        return fmt(value, Kind.LENGTH, units)

    rows = [Row([tr("input.splice_type", lang), tr(f"splice.type.{sp.type.value}", lang)])]
    if isinstance(model, ColumnSplice):
        rows += [Row([tr("input.upper_column", lang),
                      f"{model.upper.name} ({model.upper.grade})"]),
                 Row([tr("input.lower_column", lang),
                      f"{model.lower.name} ({model.lower.grade})"]),
                 Row([tr("input.filler", lang), fmt(model.filler, Kind.THICKNESS, units)
                      + (f" ({tr('input.filler_developed', lang)})"
                         if sp.filler_developed else "")]),
                 Row([tr("input.finished_ends", lang),
                      tr("report.yes" if sp.finished_ends else "report.no", lang)])]
    else:
        rows.append(Row([tr("input.beam", lang), f"{model.beam.name} ({model.beam.grade})"]))
    rows += [Row([tr("input.gap", lang), length(model.gap)]),
             Row([tr("input.grade", lang), sp.grade])]
    f = sp.flange
    text = (f"PL {q(f.thickness, Kind.THICKNESS)} × {q(f.width)} × "
            f"{length(2 * model.flange.length + model.gap)}")
    if f.inner_width is not None:
        text += (f" + 2 PL {q(f.inner_thickness, Kind.THICKNESS)} × {q(f.inner_width)}")
    rows.append(Row([tr("input.flange_plates", lang), text]))
    rows.append(Row([tr("input.flange_bolts", lang),
                     f"2 × 2 × {f.rows} × Ø {q(f.bolt.diameter)} {f.bolt.grade} @ "
                     f"{q(f.spacing)}, g = {q(f.gage)}; l_e {q(f.lev_member)} / "
                     f"{q(f.lev_plate)}"]))
    w = sp.web
    if w is not None:
        rows.append(Row([tr("input.web_plates", lang),
                         f"2 PL {q(w.thickness, Kind.THICKNESS)} × {q(w.height)} × "
                         f"{length(2 * model.web.length + model.gap)}"]))
        lines = f"{w.columns} × " if w.columns > 1 else ""
        rows.append(Row([tr("input.web_bolts", lang),
                         f"2 × {lines}{w.rows} × Ø {q(w.bolt.diameter)} {w.bolt.grade} @ "
                         f"{q(w.spacing)}; l_e {q(w.lev_member)} / {q(w.leh_plate)}"]))
    return rows


def splice_figures(project: Project, lang: str, units: UnitSystem) -> list:
    from openconex.drawing.splice import SpliceDrawing, splice_dxf
    from openconex.report.figures import Figure, dxf_to_svg, svg_to_png

    info = project.info
    options = SpliceDrawing(title=info.name, number=info.number, revision=info.revision,
                            date=info.date)
    svg = dxf_to_svg(splice_dxf(project.splice_model(), units, lang, options))
    figures = [Figure("elevation", tr("report.figure_elevation", lang), svg,
                      png=svg_to_png(svg))]
    from openconex.geometry3d.base_plate import isometric_svg, occ_available
    if occ_available():
        from openconex.geometry3d.splice import splice_parts
        svg = isometric_svg(splice_parts(project.splice_model()))
        if svg:
            figures.append(Figure("isometric", tr("report.figure_isometric", lang), svg,
                                  png=svg_to_png(svg)))
    return figures


def build_splice_report(project: Project, today: dt.date | None = None) -> Report:
    info = project.info
    lang, units = info.language, info.unit_system()
    model = project.splice_model()
    combos = project.load_combinations()
    results = check_splice_envelope(model, combos, project.case_forces())
    governing: dict[str, CheckResult] = {}
    for r in results:
        if r.applicable and (r.id not in governing or r.ratio > governing[r.id].ratio):
            governing[r.id] = r
    ok = all(r.status is not Status.NG for r in results if r.applicable)

    def q(value, kind):
        return fmt(value, kind, units)

    sp = project.splice
    column = isinstance(model, ColumnSplice)
    forces = project.case_forces()
    cases = [Row([c.name, tr(f"load.{c.type.value}", lang), q(f.P, Kind.FORCE),
                  q(f.V2, Kind.FORCE), q(f.M3, Kind.MOMENT)]
                 + ([q(f.V3, Kind.FORCE)] if column else []))
             for c, f in zip(project.cases, forces.values(), strict=True)]
    combinations = [Row([c.name, c.method.value, factor_expression(c.factors),
                         tr("report.custom_source", lang) if c.source == "custom" else c.source])
                    for c in combos]
    summary = [Row([tr(r.text_id, lang), r.combo, q(r.demand, r.kind), q(r.capacity, r.kind),
                    f"{r.ratio:.3f}"], r.status.value) for r in governing.values()]
    assumptions = [tr(f"report.assumption_splice_{sp.type.value}", lang),
                   tr("report.assumption_splice_scope", lang)]
    if column and sp.finished_ends:
        assumptions.append(tr("report.assumption_splice_bearing", lang))
    today = today or dt.date.today()
    return Report(
        language=lang, units=units, title=tr("report.title", lang),
        subtitle=f"{tr('report.subtitle_splice', lang)}: "
                 f"{tr(f'splice.type.{sp.type.value}', lang)}",
        info=[(tr("report.project", lang), info.name or "—")] + [
            (tr(f"report.{k}", lang), getattr(info, k) or "—")
            for k in ("number", "client", "engineer", "revision", "date")],
        codes=SPLICE_CODES, assumptions=assumptions, inputs=_inputs(project, lang, units),
        cases=cases,
        case_headers=["ID", tr("report.item", lang), "P", "V", "M"]
        + (["V_weak"] if column else []),
        combinations=combinations, summary=summary,
        checks=[_block(r, lang, units) for r in governing.values()], ok=ok,
        footer=tr("report.generated", lang, generator=f"OpenConex {__version__}",
                  date=today.isoformat()),
        disclaimer=tr("report.disclaimer", lang), results=results,
        figures=splice_figures(project, lang, units))
