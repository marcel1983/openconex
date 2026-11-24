# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Reusable DXF and 3D export helpers for GUI and batch runs.

Each family writes its own outputs (:mod:`openconex.families`); these helpers
only pick the family of the project.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from openconex.families import family_of
from openconex.io.project import Project

if TYPE_CHECKING:
    from openconex.geometry3d.base_plate import Part

__all__ = ["parts_3d", "write_3d", "write_dxf"]


def write_dxf(project: Project, path: str | Path) -> None:
    """Write the drawing of ``project`` (any connection family)."""
    family_of(project).write_dxf(project, path)


def parts_3d(project: Project) -> list[Part]:
    """Solids of ``project`` for the viewer and the STEP/STL writers."""
    return family_of(project).parts(project)


def write_3d(project: Project, path: str | Path, kind: str) -> None:
    """Write a STEP or STL model of ``project``."""
    family_of(project).write_3d(project, path, kind)
