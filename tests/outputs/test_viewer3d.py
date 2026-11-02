# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""3D tessellation and viewer tests."""

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from openconex.geometry3d.base_plate import Part, occ_available
from openconex.geometry3d.mesh import MeshPart, tessellate_parts
from openconex.gui.exporting import parts_3d
from openconex.gui.viewer3d import Viewer3D, part_color
from openconex.io.project import load_project

EXAMPLE = Path(__file__).parents[2] / "examples" / "base_plate_dg1_4_7_11.ocnx"
EMBEDDED = EXAMPLE.with_name("base_plate_embedded_base.ocnx")


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    return app


def test_part_colors():
    assert part_color("column").name() == "#1565c0"
    assert part_color("shear_lug").name() == "#ef6c00"
    assert part_color("anchor_rod_1").name() == "#c62828"
    assert part_color("foundation").name() == "#8d6e63"


def test_viewer_lists_and_hides_parts(qapp):
    mesh = MeshPart("column", (((0, 0, 0), (10, 0, 0), (0, 10, 0)),))
    viewer = Viewer3D(lambda: [])
    viewer.set_meshes([mesh])
    assert viewer._list.count() == 1
    assert viewer._list.item(0).text() == "column"
    viewer._list.item(0).setCheckState(Qt.CheckState.Unchecked)
    assert "column" in viewer._canvas._hidden
    assert not viewer._canvas.grab().isNull()
    viewer.close()


@pytest.mark.skipif(not occ_available(), reason="OpenCASCADE is not installed")
def test_tessellate_box():
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt

    box = BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 10, 20, 30).Shape()
    meshes = tessellate_parts([Part("box", box)])
    assert len(meshes) == 1
    assert meshes[0].name == "box"
    assert len(meshes[0].triangles) > 0


@pytest.mark.skipif(not occ_available(), reason="OpenCASCADE is not installed")
def test_parts_for_exposed_and_embedded():
    exposed = parts_3d(load_project(EXAMPLE))
    names = {part.name for part in exposed}
    assert {"column", "base_plate", "grout", "pedestal"} <= names
    assert any(name.startswith("anchor_rod") for name in names)
    embedded = parts_3d(load_project(EMBEDDED))
    embedded_names = {part.name for part in embedded}
    assert "foundation" in embedded_names
    assert "column" in embedded_names
