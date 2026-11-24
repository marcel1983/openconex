# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Registry of connection families.

A family is one kind of project block (``base_plate``, ``shear_connection``,
``moment_connection``, ``splice``) with everything the program does with it:
the command, the calculation report, the DXF drawing, the 3D parts, the batch
label and the desktop window. The command, the report builder, the batch
calculation, the exports and the GUI go through :func:`family_of` instead of
asking which block a project has.

Adding a family means writing its engine, its ``io/<family>_project.py``
block and its outputs, and then one :class:`ConnectionFamily` entry here
(see ``docs/tecnico/13-agregar-familia.md``). ``tests/test_families.py`` fails
if an entry is incomplete.

Everything is imported lazily: importing this module loads neither the
outputs nor Qt.
"""

from __future__ import annotations

import datetime as dt
import importlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from openconex.geometry3d.base_plate import Part
    from openconex.io.project import Project
    from openconex.report.builder import Report

__all__ = ["FAMILIES", "KEYS", "ConnectionFamily", "family", "family_of"]


def _call(target: str, *args: Any, **kwargs: Any) -> Any:
    """Call ``module:function`` after importing the module."""
    module, name = target.split(":")
    return getattr(importlib.import_module(module), name)(*args, **kwargs)


def _title_block(project: Project, options: str) -> Any:
    """Drawing options class ``module:Class`` filled with the project title block."""
    info = project.info
    return _call(options, title=info.name, number=info.number, revision=info.revision,
                 date=info.date)


def _label(member: Any) -> str:
    """A section given by name, or the label of a generic section."""
    return member if isinstance(member, str) else member.label()


@dataclass(frozen=True)
class ConnectionFamily:
    """Everything the program needs to handle one kind of connection."""

    key: str
    """Name of the project block (and of the :class:`Project` field)."""
    command: str
    """``openconex`` sub-command that checks it."""
    label: str
    """English name, for command-line messages."""
    name_es: str
    """Spanish name with its article, for the interface (``la conexión de corte``)."""
    report: str
    """``module:function(project, today)`` that builds the calculation report."""
    dxf: Callable[[Project, Path], Path]
    """Writes the DXF drawing of a project and returns the path."""
    parts: Callable[[Project], list[Part]]
    """Solids for the 3D viewer and the STEP/STL writers."""
    members: Callable[[Project], str]
    """Members shown in the batch table (column, beam or spliced members)."""
    window: str | None = None
    """``module:Class`` of the desktop window; ``None`` for the main window."""

    def build_report(self, project: Project, today: dt.date | None = None) -> Report:
        return _call(self.report, project, today)

    def write_dxf(self, project: Project, path: str | Path) -> Path:
        return self.dxf(project, Path(path))

    def write_3d(self, project: Project, path: str | Path, kind: str) -> Path:
        """Write a STEP (``kind == "step"``) or STL model of ``project``."""
        from openconex.geometry3d.base_plate import write_step, write_stl
        writer = write_step if kind == "step" else write_stl
        return writer(self.parts(project), Path(path))

    def window_class(self) -> type:
        """The window class (imports Qt)."""
        if self.window is None:
            raise ValueError(f"{self.label} projects open in the main window")
        module, name = self.window.split(":")
        return getattr(importlib.import_module(module), name)


# --- base plate --------------------------------------------------------------

def _base_plate_options(project: Project) -> dict[str, float | None]:
    from openconex.units import Kind

    data = project.require_base_plate()

    def q(value):
        return None if value is None else project.quantity(value, Kind.LENGTH)

    return {"pedestal_N": q(data.pedestal_N), "pedestal_B": q(data.pedestal_B),
            "grout": q(data.grout)}


def _base_plate_dxf(project: Project, path: Path) -> Path:
    from openconex.drawing.base_plate import BasePlateDrawing, write_base_plate_dxf
    from openconex.drawing.embedded_base import write_embedded_base_dxf

    bp, info = project.base_plate_model(), project.info
    options = BasePlateDrawing(**_base_plate_options(project), title=info.name,
                               number=info.number, revision=info.revision, date=info.date)
    writer = write_embedded_base_dxf if bp.embedded_base is not None else write_base_plate_dxf
    return writer(bp, path, info.unit_system(), info.language, options)


def _base_plate_parts(project: Project) -> list[Part]:
    from openconex.geometry3d.base_plate import base_plate_parts, embedded_base_parts

    bp, q = project.base_plate_model(), _base_plate_options(project)
    if bp.embedded_base is not None:
        return embedded_base_parts(bp, q["pedestal_B"])
    return base_plate_parts(bp, q["grout"], q["pedestal_N"], q["pedestal_B"])


# --- beam-end shear, moment and splice ----------------------------------------

def _dxf(model: str, writer: str, options: str) -> Callable[[Project, Path], Path]:
    def write(project: Project, path: Path) -> Path:
        info = project.info
        return _call(writer, getattr(project, model)(), path, info.unit_system(),
                     info.language, _title_block(project, options))
    return write


def _parts(model: str, builder: str) -> Callable[[Project], list[Part]]:
    def parts(project: Project) -> list[Part]:
        return _call(builder, getattr(project, model)())
    return parts


def _splice_members(project: Project) -> str:
    sp = project.require_splice()
    return " / ".join(_label(m) for m in (sp.beam, sp.upper, sp.lower) if m is not None)


FAMILIES: tuple[ConnectionFamily, ...] = (
    ConnectionFamily(
        key="base_plate", command="baseplate", label="base plate",
        name_es="la placa base",
        report="openconex.report.builder:build_base_plate_report",
        dxf=_base_plate_dxf, parts=_base_plate_parts,
        members=lambda project: _label(project.require_base_plate().column)),
    ConnectionFamily(
        key="shear_connection", command="shear", label="shear connection",
        name_es="la conexión de corte",
        report="openconex.report.shear:build_shear_report",
        dxf=_dxf("shear_model", "openconex.drawing.shear:write_shear_dxf",
                 "openconex.drawing.shear:ShearDrawing"),
        parts=_parts("shear_model", "openconex.geometry3d.shear:shear_parts"),
        members=lambda project: _label(project.require_shear_connection().beam),
        window="openconex.gui.shear:ShearWindow"),
    ConnectionFamily(
        key="moment_connection", command="moment", label="moment connection",
        name_es="la conexión de momento",
        report="openconex.report.moment:build_moment_report",
        dxf=_dxf("moment_model", "openconex.drawing.moment:write_moment_dxf",
                 "openconex.drawing.moment:MomentDrawing"),
        parts=_parts("moment_model", "openconex.geometry3d.moment:moment_parts"),
        members=lambda project: _label(project.require_moment_connection().beam),
        window="openconex.gui.moment:MomentWindow"),
    ConnectionFamily(
        key="splice", command="splice", label="splice",
        name_es="el empalme",
        report="openconex.report.splice:build_splice_report",
        dxf=_dxf("splice_model", "openconex.drawing.splice:write_splice_dxf",
                 "openconex.drawing.splice:SpliceDrawing"),
        parts=_parts("splice_model", "openconex.geometry3d.splice:splice_parts"),
        members=_splice_members,
        window="openconex.gui.splice:SpliceWindow"),
)
"""Every family, in the order of the commands and of the menus."""

KEYS: tuple[str, ...] = tuple(f.key for f in FAMILIES)


def family(key: str) -> ConnectionFamily:
    """The family whose block (or command) is ``key``."""
    for item in FAMILIES:
        if key in (item.key, item.command):
            return item
    raise KeyError(key)


def family_of(project: Project) -> ConnectionFamily:
    """The family of the one connection block that ``project`` holds."""
    present = [f for f in FAMILIES if getattr(project, f.key) is not None]
    if len(present) != 1:
        raise ValueError("a project needs exactly one of " + ", ".join(KEYS))
    return present[0]
