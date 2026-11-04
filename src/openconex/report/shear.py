# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Report content of a beam-end shear connection project."""

from __future__ import annotations

import datetime as dt

from openconex import __version__
from openconex.connections.shear.check import check_shear_envelope
from openconex.core.checks import CheckResult, Status
from openconex.i18n import tr
from openconex.io.project import Project
from openconex.report.builder import Report, Row, _block, factor_expression, fmt
from openconex.units import Kind, UnitSystem

__all__ = ["SHEAR_CODES", "build_shear_report", "shear_figures"]

SHEAR_CODES = [
    "ANSI/AISC 360-22, Specification for Structural Steel Buildings",
    "AISC Steel Construction Manual, 16th ed., Parts 7 to 10 and 12",
    "ASCE/SEI 7-22, Minimum Design Loads and Associated Criteria, Chapter 2",
]

# Input field -> (label key, kind); None for plain values.
FIELDS: list[tuple[str, str, Kind | None]] = [
    ("rows", "rows", None), ("lines", "lines", None), ("spacing", "spacing", Kind.LENGTH),
    ("gage", "gage", Kind.LENGTH), ("length", "length", Kind.LENGTH),
    ("thickness", "thickness", Kind.THICKNESS), ("width", "width", Kind.LENGTH),
    ("lev", "lev", Kind.LENGTH), ("leh", "leh", Kind.LENGTH),
    ("leh_support", "leh_support", Kind.LENGTH), ("a", "a", Kind.LENGTH),
    ("beam_leg", "beam_leg", Kind.LENGTH), ("outstanding_leg", "outstanding_leg", Kind.LENGTH),
    ("beam_leh", "beam_leh", Kind.LENGTH), ("leg", "leg", Kind.LENGTH),
    ("vertical_leg", "vertical_leg", Kind.LENGTH),
    ("bearing_length", "bearing_length", Kind.LENGTH), ("weld", "weld", Kind.THICKNESS),
    ("support_weld", "support_weld", Kind.THICKNESS),
    ("beam_weld", "beam_weld", Kind.THICKNESS), ("beam_area", "beam_area", Kind.AREA),
]


def _inputs(project: Project, lang: str, units: UnitSystem) -> list[Row]:
    sc = project.shear_connection
    conn = project.shear_model()

    def q(value, kind):
        return fmt(project.quantity(value, kind), kind, units)

    rows = [
        Row([tr("input.sc_type", lang), tr(f"shear.type.{sc.type.value}", lang)]),
        Row([tr("input.beam", lang), f"{conn.beam.name} ({conn.beam.grade})"]),
        Row([tr("input.support", lang), f"{conn.support.name} ({conn.support.grade}), "
             + tr(f"input.support_{sc.support_element}", lang)]),
        Row([tr("input.grade", lang), sc.grade]),
    ]
    bolted = sc.type.value != "stiffened_seat"
    if bolted:
        bolt = sc.bolt
        rows.append(Row([tr("input.bolts", lang),
                         f"Ø {q(bolt.diameter, Kind.LENGTH)} {bolt.grade} "
                         f"({bolt.threads.value}, {bolt.hole.value})"]))
    if sc.type.value == "seated" and sc.support_weld is None:
        rows.append(Row([tr("input.seat_bolts", lang), str(sc.bolts)]))
    for name, key, kind in FIELDS:
        value = getattr(sc, name)
        if value is None or (name == "lines" and value == 1):
            continue
        rows.append(Row([tr(f"input.{key}", lang),
                         str(value) if kind is None else q(value, kind)]))
    if any(getattr(sc, n) is not None for n in ("weld", "support_weld", "beam_weld")) or \
            sc.type.value in {"end_plate", "stiffened_seat"}:
        rows.append(Row([tr("input.electrode", lang), sc.electrode]))
    if sc.two_sided:
        rows.append(Row([tr("input.two_sided", lang), "✔"]))
    if sc.cope is not None:
        c = sc.cope
        text = f"c = {q(c.c, Kind.LENGTH)}, d_c = {q(c.dc, Kind.LENGTH)}"
        if project.quantity(c.dc_bottom, Kind.LENGTH):
            text += f", d_c,inf = {q(c.dc_bottom, Kind.LENGTH)}"
        rows.append(Row([tr("input.cope", lang), text]))
    return rows


def shear_figures(project: Project, lang: str, units: UnitSystem) -> list:
    from openconex.drawing.shear import ShearDrawing, shear_dxf
    from openconex.report.figures import Figure, dxf_to_svg, svg_to_png

    info = project.info
    options = ShearDrawing(title=info.name, number=info.number, revision=info.revision,
                           date=info.date, bom=False)
    svg = dxf_to_svg(shear_dxf(project.shear_model(), units, lang, options))
    figures = [Figure("elevation", tr("report.figure_elevation", lang), svg,
                      png=svg_to_png(svg))]
    from openconex.geometry3d.base_plate import isometric_svg, occ_available
    if occ_available():
        from openconex.geometry3d.shear import shear_parts
        svg = isometric_svg(shear_parts(project.shear_model()))
        if svg:
            figures.append(Figure("isometric", tr("report.figure_isometric", lang), svg,
                                  png=svg_to_png(svg)))
    return figures


def build_shear_report(project: Project, today: dt.date | None = None) -> Report:
    info = project.info
    lang, units = info.language, info.unit_system()
    conn = project.shear_model()
    combos = project.load_combinations()
    results = check_shear_envelope(conn, combos, project.case_forces())
    governing: dict[str, CheckResult] = {}
    for r in results:
        if r.applicable and (r.id not in governing or r.ratio > governing[r.id].ratio):
            governing[r.id] = r
    ok = all(r.status is not Status.NG for r in results)

    def q(value, kind):
        return fmt(value, kind, units)

    forces = project.case_forces()
    case_headers = ["ID", tr("report.item", lang), "V", "P"]
    cases = [Row([c.name, tr(f"load.{c.type.value}", lang), q(f.V2, Kind.FORCE),
                  q(f.P, Kind.FORCE)])
             for c, f in zip(project.cases, forces.values(), strict=True)]
    combinations = [Row([c.name, c.method.value, factor_expression(c.factors),
                         tr("report.custom_source", lang) if c.source == "custom" else c.source])
                    for c in combos]
    summary = [Row([tr(r.text_id, lang), r.combo, q(r.demand, r.kind), q(r.capacity, r.kind),
                    f"{r.ratio:.3f}"], r.status.value) for r in governing.values()]
    sc = project.shear_connection
    assumptions = [tr("report.assumption_shear_reaction", lang),
                   tr("report.assumption_shear_beam", lang)]
    if sc.cope is not None:
        assumptions.append(tr("report.assumption_shear_cope", lang))
    if not sc.deformation_considered:
        assumptions.append(tr("report.assumption_shear_deformation", lang))
    today = today or dt.date.today()
    return Report(
        language=lang, units=units, title=tr("report.title", lang),
        subtitle=f"{tr('report.subtitle_shear', lang)}: "
                 f"{tr(f'shear.type.{sc.type.value}', lang)}",
        info=[(tr("report.project", lang), info.name or "—")] + [
            (tr(f"report.{k}", lang), getattr(info, k) or "—")
            for k in ("number", "client", "engineer", "revision", "date")],
        codes=SHEAR_CODES, assumptions=assumptions, inputs=_inputs(project, lang, units),
        cases=cases, case_headers=case_headers, combinations=combinations, summary=summary,
        checks=[_block(r, lang, units) for r in governing.values()], ok=ok,
        footer=tr("report.generated", lang, generator=f"OpenConex {__version__}",
                  date=today.isoformat()),
        disclaimer=tr("report.disclaimer", lang), results=results,
        figures=shear_figures(project, lang, units))
