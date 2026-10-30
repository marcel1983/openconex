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

    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
