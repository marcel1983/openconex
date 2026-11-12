# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Report content of a beam-to-column moment connection project."""

from __future__ import annotations

import datetime as dt

from openconex import __version__
from openconex.connections.moment.fr_moment import FlangeDetail, check_moment_envelope
from openconex.core.checks import CheckResult, Status
from openconex.i18n import tr
from openconex.io.project import Project
from openconex.report.builder import Report, Row, _block, factor_expression, fmt
from openconex.units import Kind, UnitSystem

__all__ = ["MOMENT_CODES", "build_moment_report", "moment_figures"]

MOMENT_CODES = [
    "ANSI/AISC 360-22, Specification for Structural Steel Buildings",
    "AISC Steel Construction Manual, 16th ed., Parts 7 to 12",
    "ASCE/SEI 7-22, Minimum Design Loads and Associated Criteria, Chapter 2",
]


def _inputs(project: Project, lang: str, units: UnitSystem) -> list[Row]:
    mc = project.moment_connection
    model = project.moment_model()

    def q(value, kind=Kind.LENGTH):
        return fmt(project.quantity(value, kind), kind, units)

    rows = [
        Row([tr("input.mc_type", lang), tr(f"moment.type.{mc.type.value}", lang)]),
        Row([tr("input.beam", lang), f"{model.beam.name} ({model.beam.grade})"]),
        Row([tr("input.column", lang), f"{model.column.name} ({model.column.grade})"]),
        Row([tr("input.grade", lang), mc.grade]),
        Row([tr("input.electrode", lang), mc.electrode]),
    ]
    w = mc.web
    rows.append(Row([tr("input.web_plate", lang),
                     f"PL {q(w.thickness, Kind.THICKNESS)} × {q(w.length)}; {w.rows} × Ø "
                     f"{q(w.bolt.diameter)} {w.bolt.grade} @ {q(w.spacing)}; l_ev {q(w.lev)}, "
                     f"l_eh {q(w.leh)}; {q(w.weld, Kind.THICKNESS)}"]))
    for key, plate in (("top_plate", mc.top), ("bottom_plate", mc.bottom)):
        if plate is None:
            continue
        text = (f"PL {q(plate.thickness, Kind.THICKNESS)} × {q(plate.width)}; "
                f"{q(plate.weld_to_column, Kind.THICKNESS)} → {tr('input.column', lang)}")
        if plate.weld_to_beam is not None:
            text += (f"; {q(plate.weld_to_beam, Kind.THICKNESS)} × "
                     f"{q(plate.weld_length)} → {tr('input.beam', lang)}")
        rows.append(Row([tr(f"input.{key}", lang), text]))
    if mc.type is FlangeDetail.BOLTED_FLANGE_PLATE:
        rows.append(Row([tr("input.flange_bolts", lang),
                         f"2 × {mc.rows} × Ø {q(mc.bolt.diameter)} {mc.bolt.grade} @ "
                         f"{q(mc.spacing)}, g = {q(mc.gage)}, l_ev {q(mc.plate_lev)} / "
                         f"{q(mc.beam_lev)}"]))
    return rows


def moment_figures(project: Project, lang: str, units: UnitSystem) -> list:
    from openconex.drawing.moment import MomentDrawing, moment_dxf
    from openconex.report.figures import Figure, dxf_to_svg, svg_to_png

    info = project.info
    options = MomentDrawing(title=info.name, number=info.number, revision=info.revision,
                            date=info.date)
    svg = dxf_to_svg(moment_dxf(project.moment_model(), units, lang, options))
    figures = [Figure("elevation", tr("report.figure_elevation", lang), svg,
                      png=svg_to_png(svg))]
    from openconex.geometry3d.base_plate import isometric_svg, occ_available
    if occ_available():
        from openconex.geometry3d.moment import moment_parts
        svg = isometric_svg(moment_parts(project.moment_model()))
        if svg:
            figures.append(Figure("isometric", tr("report.figure_isometric", lang), svg,
                                  png=svg_to_png(svg)))
    return figures


def build_moment_report(project: Project, today: dt.date | None = None) -> Report:
    info = project.info
    lang, units = info.language, info.unit_system()
    model = project.moment_model()
    combos = project.load_combinations()
    results = check_moment_envelope(model, combos, project.case_forces())
    governing: dict[str, CheckResult] = {}
    for r in results:
        if r.applicable and (r.id not in governing or r.ratio > governing[r.id].ratio):
            governing[r.id] = r
    ok = all(r.status is not Status.NG for r in results if r.applicable)

    def q(value, kind):
        return fmt(value, kind, units)

    forces = project.case_forces()
    cases = [Row([c.name, tr(f"load.{c.type.value}", lang), q(f.V2, Kind.FORCE),
                  q(f.M3, Kind.MOMENT)])
             for c, f in zip(project.cases, forces.values(), strict=True)]
    combinations = [Row([c.name, c.method.value, factor_expression(c.factors),
                         tr("report.custom_source", lang) if c.source == "custom" else c.source])
                    for c in combos]
    summary = [Row([tr(r.text_id, lang), r.combo, q(r.demand, r.kind), q(r.capacity, r.kind),
                    f"{r.ratio:.3f}"], r.status.value) for r in governing.values()]
    mc = project.moment_connection
    assumptions = [tr("report.assumption_moment_force", lang),
                   tr("report.assumption_moment_scope", lang)]
    if mc.type is FlangeDetail.WELDED_FLANGE:
        assumptions.append(tr("report.assumption_moment_cjp", lang))
    today = today or dt.date.today()
    return Report(
        language=lang, units=units, title=tr("report.title", lang),
        subtitle=f"{tr('report.subtitle_moment', lang)}: "
                 f"{tr(f'moment.type.{mc.type.value}', lang)}",
        info=[(tr("report.project", lang), info.name or "—")] + [
            (tr(f"report.{k}", lang), getattr(info, k) or "—")
            for k in ("number", "client", "engineer", "revision", "date")],
        codes=MOMENT_CODES, assumptions=assumptions, inputs=_inputs(project, lang, units),
        cases=cases, case_headers=["ID", tr("report.item", lang), "V", "M"],
        combinations=combinations, summary=summary,
        checks=[_block(r, lang, units) for r in governing.values()], ok=ok,
        footer=tr("report.generated", lang, generator=f"OpenConex {__version__}",
                  date=today.isoformat()),
        disclaimer=tr("report.disclaimer", lang), results=results,
        figures=moment_figures(project, lang, units))
