# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Reusable DXF and 3D export helpers for GUI and batch runs."""

from __future__ import annotations

from pathlib import Path

from openconex.drawing.base_plate import BasePlateDrawing, write_base_plate_dxf
from openconex.drawing.embedded_base import write_embedded_base_dxf
from openconex.geometry3d.base_plate import (
    Part,
    base_plate_parts,
    embedded_base_parts,
    write_step,
    write_stl,
)
from openconex.io.project import Project
from openconex.units import Kind

__all__ = ["parts_3d", "write_3d", "write_dxf"]


def write_dxf(project: Project, path: str | Path) -> None:
    """Write the base plate drawing of ``project``."""
    bp = project.base_plate_model()
    info = project.info
    data = project.base_plate
    options = BasePlateDrawing(
        pedestal_N=(None if data.pedestal_N is None else
                    project.quantity(data.pedestal_N, Kind.LENGTH)),
        pedestal_B=(None if data.pedestal_B is None else
                    project.quantity(data.pedestal_B, Kind.LENGTH)),
        grout=project.quantity(data.grout, Kind.LENGTH),
        title=info.name, number=info.number, revision=info.revision, date=info.date)
    if bp.embedded_base is not None:
        write_embedded_base_dxf(bp, path, info.unit_system(), info.language, options)
    else:
        write_base_plate_dxf(bp, path, info.unit_system(), info.language, options)


def parts_3d(project: Project) -> list[Part]:
    """Solids of ``project`` for the viewer and the STEP/STL writers."""
    bp = project.base_plate_model()
    if bp.embedded_base is not None:
        return embedded_base_parts(bp)
    data = project.base_plate
    return base_plate_parts(
        bp, project.quantity(data.grout, Kind.LENGTH),
        None if data.pedestal_N is None else
        project.quantity(data.pedestal_N, Kind.LENGTH),
        None if data.pedestal_B is None else
        project.quantity(data.pedestal_B, Kind.LENGTH))


def write_3d(project: Project, path: str | Path, kind: str) -> None:
    """Write a STEP or STL model of ``project``."""
    parts = parts_3d(project)
    (write_step if kind == "step" else write_stl)(parts, path)
