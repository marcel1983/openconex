# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Command-line entry point (``openconex``)."""

from __future__ import annotations

import argparse
import sys

from openconex import __version__
from openconex.units import CHOICES, PRESETS, Kind, UnitError, format_value, parse


def _convert(args: argparse.Namespace) -> int:
    kind = Kind(args.kind)
    try:
        value = parse(args.value, kind)
        system = PRESETS[args.system] if args.system else None
        if system is None:
            system = next(iter(PRESETS.values())).with_unit(kind, args.to)
    except UnitError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(format_value(value, kind, system, precision=args.precision))
    return 0


def _units(_: argparse.Namespace) -> int:
    for kind, choices in CHOICES.items():
        print(f"{kind.value:18} {', '.join(choices)}")
    return 0


def _baseplate(args: argparse.Namespace) -> int:
    """Check a base plate project and write the requested outputs."""
    from pathlib import Path

    from openconex.drawing.base_plate import BasePlateDrawing, write_base_plate_dxf
    from openconex.io.project import load_project
    from openconex.report.builder import build_base_plate_report

    project = load_project(args.project)
    if args.lang:
        project.info.language = args.lang
    if args.units:
        project.info.units = args.units
    report = build_base_plate_report(project)
    out = Path(args.output or Path(args.project).with_suffix(""))
    out.parent.mkdir(parents=True, exist_ok=True)
    written = []
    if args.html:
        from openconex.report.html import write_html
        written.append(write_html(report, out.with_suffix(".html")))
    if args.docx:
        from openconex.report.docx import write_docx
        written.append(write_docx(report, out.with_suffix(".docx")))
    if args.pdf:
        from openconex.report.pdf import write_pdf
        written.append(write_pdf(report, out.with_suffix(".pdf")))
    bp, data, info = project.base_plate_model(), project.base_plate, project.info

    def q(value):
        return None if value is None else project.quantity(value, Kind.LENGTH)

    if args.dxf:
        options = BasePlateDrawing(
            pedestal_N=q(data.pedestal_N), pedestal_B=q(data.pedestal_B), grout=q(data.grout),
            title=info.name, number=info.number, revision=info.revision, date=info.date)
        written.append(write_base_plate_dxf(bp, out.with_suffix(".dxf"), info.unit_system(),
                                            info.language, options))
    if args.step or args.stl:
        from openconex.geometry3d.base_plate import base_plate_parts, write_step, write_stl
        parts = base_plate_parts(bp, q(data.grout), q(data.pedestal_N), q(data.pedestal_B))
        if args.step:
            written.append(write_step(parts, out.with_suffix(".step")))
        if args.stl:
            written.append(write_stl(parts, out.with_suffix(".stl")))
    for row in report.summary:
        print(f"{row.status.upper():4} {row.cells[4]:>7}  {row.cells[0]} ({row.cells[1]})")
    for path in written:
        print(f"-> {path}")
    return 0 if report.ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="openconex", description=__doc__)
    parser.add_argument("--version", action="version", version=f"OpenConex {__version__}")
    sub = parser.add_subparsers(dest="command")

    conv = sub.add_parser("convert", help="convert a quantity between units")
    conv.add_argument("value", help='quantity with unit, e.g. "3/4 in" or "25 kN"')
    conv.add_argument("kind", choices=[k.value for k in Kind])
    target = conv.add_mutually_exclusive_group(required=True)
    target.add_argument("--to", help="target unit, e.g. mm")
    target.add_argument("--system", choices=sorted(PRESETS), help="target preset")
    conv.add_argument("--precision", type=int, default=4)
    conv.set_defaults(func=_convert)

    units = sub.add_parser("units", help="list the units offered for each kind")
    units.set_defaults(func=_units)

    bp = sub.add_parser("baseplate", help="check a base plate project (.ocnx) and write outputs")
    bp.add_argument("project", help="project file (.ocnx)")
    bp.add_argument("-o", "--output", help="output path without extension")
    bp.add_argument("--lang", choices=["es", "en"], help="report language")
    bp.add_argument("--units", choices=sorted(PRESETS), help="unit system of the outputs")
    for flag, text in (("html", "HTML report"), ("docx", "Word report"),
                       ("pdf", "PDF report (needs openconex[pdf])"), ("dxf", "DXF drawing"),
                       ("step", "STEP 3D model (needs openconex[3d])"),
                       ("stl", "STL 3D model (needs openconex[3d])")):
        bp.add_argument(f"--{flag}", action="store_true", help=text)
    bp.set_defaults(func=_baseplate)

    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
