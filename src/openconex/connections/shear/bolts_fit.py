# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Bolt-fit checks shared by the shear connections.

These are input-geometry checks, not strength limit states.  A bolt row that
falls outside the plate or angle, or an edge distance below AISC 360-22
Table J3.4, cannot be built: the calculation stops with an actionable error
instead of drawing a connection that does not exist.

All lengths are internal millimetres.  Messages show inches because the shear
module follows the U.S. customary tables of the AISC Specification.
"""

from __future__ import annotations

from openconex.core.bolting import min_edge_distance, min_spacing
from openconex.core.model import BoltSpec
from openconex.units import Kind, from_internal, to_internal

__all__ = ["check_edge", "check_rows", "check_spacing", "fail", "fmt_length"]

TOL = to_internal(1e-4, "in", Kind.LENGTH)


def fmt_length(value: float) -> str:
    """Format an internal length in inches for a user message."""
    return f"{from_internal(value, Kind.LENGTH, 'in'):.3f} in"


def fail(message: str) -> None:
    """Raise the user-facing geometry error."""
    raise ValueError(f"Geometría de pernos: {message}")


def check_edge(label: str, value: float, bolt: BoltSpec) -> None:
    """Require an edge distance no smaller than Table J3.4."""
    diameter = from_internal(bolt.diameter, Kind.LENGTH, "in")
    required = min_edge_distance(diameter)
    if value + TOL < required:
        fail(f"{label} = {fmt_length(value)} es menor que el mínimo de la Tabla J3.4 "
             f"para un perno de {fmt_length(bolt.diameter)} ({fmt_length(required)}). "
             "Aumente la distancia al borde.")


def check_spacing(label: str, value: float, bolt: BoltSpec) -> None:
    """Require a centre-to-centre spacing no smaller than §J3.3."""
    required = min_spacing(bolt.diameter)
    if value + TOL < required:
        fail(f"{label} = {fmt_length(value)} es menor que la separación mínima "
             f"2⅔d = {fmt_length(required)}. Aumente la separación.")


def check_rows(element: str, bolt: BoltSpec, length: float, rows: int,
               spacing: float, lev: float) -> None:
    """Require the vertical bolt group to fit inside the element.

    The drawing places the first row at ``lev`` from the top and the remaining
    rows at ``spacing``; the last row must keep ``lev`` from the bottom edge.
    """
    if rows < 1:
        fail(f"{element} no tiene filas de pernos.")
    check_edge("l_ev", lev, bolt)
    if rows > 1:
        check_spacing("s", spacing, bolt)
    required = 2 * lev + (rows - 1) * spacing
    if length + TOL < required:
        subject = ("el perno" if rows == 1
                   else f"los {rows} pernos")
        verb = "no cabe" if rows == 1 else "no caben"
        fail(f"{subject} {verb} en {element}: con l_ev = {fmt_length(lev)} "
             f"y s = {fmt_length(spacing)} necesita{'n' if rows > 1 else ''} "
             f"{fmt_length(required)} de largo y el elemento tiene "
             f"{fmt_length(length)}. Aumente el largo, reduzca filas o "
             "disminuya la separación.")
