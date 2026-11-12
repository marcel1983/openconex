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
from openconex.gui.viewer3d import Viewer3D, _explode_meshes, part_color
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
    assert part_color("base_plate").name() == "#ef6c00"
    assert part_color("angle+").name() == "#ef6c00"
    assert part_color("seat").name() == "#ef6c00"
    assert part_color("bolt1").name() == "#ef6c00"


def test_offscreen_viewer_uses_the_painter_canvas(qapp):
    viewer = Viewer3D(lambda: [], use_opengl=False)
    assert type(viewer._canvas).__name__ == "_ViewCanvas"
    viewer.close()


def test_explode_moves_exact_and_prefixed_parts():
    first = MeshPart("beam", (((0.0, 0.0, 0.0), (1.0, 0.0, 0.0),
                               (0.0, 1.0, 0.0)),))
    bolt = MeshPart("support_bolt_1", (((0.0, 0.0, 0.0), (1.0, 0.0, 0.0),
                                        (0.0, 1.0, 0.0)),))
    moved = _explode_meshes([first, bolt], {"beam": (10.0, 0.0, 0.0),
                                            "support_bolt*": (0.0, 5.0, 0.0)})
    assert moved[0].triangles[0][0] == (10.0, 0.0, 0.0)
    assert moved[1].triangles[0][0] == (0.0, 5.0, 0.0)


def test_standard_views_reset_the_camera(qapp):
    mesh = MeshPart("column", (((0, 0, 0), (10, 0, 0), (0, 10, 0)),))
    viewer = Viewer3D(lambda: [], use_opengl=False)
    viewer.set_meshes([mesh])
    viewer._canvas.set_view("top")
    assert viewer._canvas._yaw == 0.0
    assert viewer._canvas._pitch == 89.0
    viewer._canvas.set_view("side")
    assert viewer._canvas._yaw == 90.0
    assert viewer._canvas._pitch == 0.0
    viewer.close()


def test_explode_button_and_prefix_shift(qapp):
    mesh = MeshPart("beam", (((0.0, 0.0, 0.0), (1.0, 0.0, 0.0),
                              (0.0, 1.0, 0.0)),))
    viewer = Viewer3D(lambda: [], explode={"beam": (5.0, 0.0, 0.0)},
                      use_opengl=False)
    viewer.set_meshes([mesh])
    assert viewer._explode_button is not None
    viewer._explode_button.setChecked(True)
    assert viewer._canvas._meshes[0].triangles[0][0] == (5.0, 0.0, 0.0)
    viewer.close()


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

    from openconex.gui.viewer3d import _normal

    box = BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 10, 20, 30).Shape()
    meshes = tessellate_parts([Part("box", box)])
    assert len(meshes) == 1
    assert meshes[0].name == "box"
    assert len(meshes[0].triangles) > 0
    center = (5.0, 10.0, 15.0)
    for p0, p1, p2 in meshes[0].triangles:
        normal = _normal(p0, p1, p2)
        middle = ((p0[0] + p1[0] + p2[0]) / 3 - center[0],
                  (p0[1] + p1[1] + p2[1]) / 3 - center[1],
                  (p0[2] + p1[2] + p2[2]) / 3 - center[2])
        assert sum(value * value for value in normal) == pytest.approx(1.0)
        assert normal[0] * middle[0] + normal[1] * middle[1] \
            + normal[2] * middle[2] > 0


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
