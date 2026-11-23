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
from openconex.gui.viewer3d import (
    Viewer3D,
    _explode_meshes,
    _opengl_available,
    part_color,
    view_angles,
)
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


def test_explode_moves_exact_and_prefixed_parts():
    first = MeshPart("beam", (((0.0, 0.0, 0.0), (1.0, 0.0, 0.0),
                               (0.0, 1.0, 0.0)),))
    bolt = MeshPart("support_bolt_1", (((0.0, 0.0, 0.0), (1.0, 0.0, 0.0),
                                        (0.0, 1.0, 0.0)),))
    moved = _explode_meshes([first, bolt], {"beam": (10.0, 0.0, 0.0),
                                            "support_bolt*": (0.0, 5.0, 0.0)})
    assert moved[0].triangles[0][0] == (10.0, 0.0, 0.0)
    assert moved[1].triangles[0][0] == (0.0, 5.0, 0.0)


def test_viewer_lists_and_hides_parts(qapp):
    mesh = MeshPart("column", (((0, 0, 0), (10, 0, 0), (0, 10, 0)),))
    viewer = Viewer3D(lambda: [])
    viewer.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    viewer.set_meshes([mesh])
    assert viewer._list.count() == 1
    assert viewer._list.item(0).text() == "column"
    viewer._list.item(0).setCheckState(Qt.CheckState.Unchecked)
    assert "column" in viewer._canvas._hidden
    assert not viewer._canvas.grab().isNull()
    viewer.close()


def test_standard_view_angles():
    assert view_angles("iso") == (35.0, 25.0)
    assert view_angles("front") == (0.0, 0.0)
    assert view_angles("top") == (0.0, 89.0)
    assert view_angles("side") == (90.0, 0.0)


def test_opengl_is_disabled_offscreen(qapp):
    from PySide6.QtWidgets import QApplication
    if QApplication.platformName() == "offscreen":
        assert not _opengl_available()


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


def test_y_up_rotation_keeps_the_handedness():
    from openconex.gui.viewer3d import _normal, y_up_to_z_up

    # Counter-clockwise seen from +z: the normal is +z (a face looking at +z).
    face = MeshPart("plate", (((0.0, 0.0, 1.0), (1.0, 0.0, 1.0), (0.0, 1.0, 1.0)),),
                    (((0.0, 0.0, 1.0), (1.0, 0.0, 1.0)),))
    turned = y_up_to_z_up([face])[0]
    assert turned.triangles[0][1] == (1.0, -1.0, 0.0)
    assert turned.edges[0][1] == (1.0, -1.0, 0.0)
    # A rotation (not a mirror): the face that looked at +z now looks at -y,
    # where (x, y, z) → (x, -z, y) sends the +z axis.
    assert _normal(*turned.triangles[0]) == pytest.approx((0.0, -1.0, 0.0))


def test_feature_edges_of_a_triangulated_square():
    from openconex.geometry3d.mesh import feature_edges

    a, b, c, d = (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)
    edges = feature_edges([(a, b, c), (a, c, d)])
    # The four sides of the open square, not its diagonal.
    assert len(edges) == 4
    assert all({tuple(e[0]), tuple(e[1])} != {a, c} for e in edges)


@pytest.mark.skipif(not occ_available(), reason="OpenCASCADE is not installed")
def test_box_and_cylinder_outline():
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Pnt

    box = BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 100, 200, 300).Shape()
    raw = tessellate_parts([Part("box", box)], max_edge=None, edges=True)[0]
    assert len(raw.triangles) == 12  # the OpenGL canvas gets OCC's triangles
    assert len(raw.edges) == 12  # the 12 edges of the box, no diagonals
    split = tessellate_parts([Part("box", box)])[0]
    assert len(split.triangles) > len(raw.triangles)  # painter's subdivision
    rod = BRepPrimAPI_MakeCylinder(10.0, 100.0).Shape()
    mesh = tessellate_parts([Part("rod", rod)], max_edge=None, edges=True)[0]
    facets = sum(1 for p0, p1 in mesh.edges if abs(p0[2] - p1[2]) > 50)
    assert facets == 0  # the facets of the round side are not outlined
    # Two circles: the round outline is fine (≥ 20 segments) but drawn once.
    assert len(mesh.edges) >= 40


def _wait(viewer, condition, timeout=20.0):
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        QApplication.processEvents()
        if condition():
            return True
        time.sleep(0.005)
    return False


def _box_builder(calls):
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt

    def build(size):
        calls.append(size)
        return [Part("plate", BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), size, 50, 10).Shape()),
                Part("bolt", BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 10), 5, 5, 5).Shape())]
    return build


@pytest.mark.skipif(not occ_available(), reason="OpenCASCADE is not installed")
def test_viewer_follows_the_snapshot_with_debounce_and_cache(qapp):
    calls: list[float] = []
    state = {"size": 100.0}
    viewer = Viewer3D(_box_builder(calls), snapshot=lambda: state["size"], delay_ms=20)
    viewer.show()
    assert _wait(viewer, lambda: viewer._model is not None and not viewer.is_busy)
    assert calls == [100.0]
    # The user hides a part; later edits keep that choice.
    viewer._list.item(1).setCheckState(Qt.CheckState.Unchecked)
    assert viewer._hidden == {"bolt"}
    # A burst of edits builds once, with the last value.
    for size in (110.0, 120.0, 130.0):
        state["size"] = size
        viewer.schedule_update()
    assert _wait(viewer, lambda: calls[-1] == 130.0 and not viewer.is_busy)
    assert calls == [100.0, 130.0]
    assert viewer._hidden == {"bolt"}
    assert viewer._list.item(1).checkState() == Qt.CheckState.Unchecked
    # Undo: the previous model comes back from the cache, without meshing.
    state["size"] = 100.0
    viewer.update_model()
    assert calls == [100.0, 130.0]
    assert "caché" in viewer._status.text()
    # Same value again: nothing to do. Actualizar forces a rebuild.
    viewer.update_model()
    assert calls == [100.0, 130.0]
    viewer.load_model()
    assert _wait(viewer, lambda: len(calls) == 3 and not viewer.is_busy)
    viewer.close()


@pytest.mark.skipif(not occ_available(), reason="OpenCASCADE is not installed")
def test_viewer_coalesces_edits_while_meshing(qapp):
    calls: list[float] = []
    state = {"size": 100.0}
    viewer = Viewer3D(_box_builder(calls), snapshot=lambda: state["size"], delay_ms=10)
    viewer.show()
    viewer.update_model()
    assert viewer._running
    for size in (101.0, 102.0, 103.0):
        state["size"] = size
        viewer.update_model()  # queued: only one worker at a time
    assert _wait(viewer, lambda: not viewer.is_busy and viewer._model is not None)
    assert calls[0] == 100.0 and calls[-1] == 103.0 and len(calls) <= 3
    viewer.close()


@pytest.mark.skipif(not occ_available(), reason="OpenCASCADE is not installed")
def test_viewer_keeps_the_last_model_when_the_form_is_invalid(qapp):
    calls: list[float] = []
    state: dict = {"size": 100.0}

    def snapshot():
        if state["size"] is None:
            raise ValueError("espesor no válido")
        return state["size"]

    viewer = Viewer3D(_box_builder(calls), snapshot=snapshot, delay_ms=10)
    viewer.show()
    assert _wait(viewer, lambda: viewer._model is not None and not viewer.is_busy)
    state["size"] = None
    viewer.update_model()
    assert viewer._model is not None
    assert "espesor no válido" in viewer._status.text()
    viewer.close()


def test_viewer_waits_while_hidden(qapp):
    calls: list[int] = []
    viewer = Viewer3D(lambda value: calls.append(value) or [], snapshot=lambda: 1,
                      delay_ms=1)
    viewer.schedule_update()
    assert _wait(viewer, lambda: not viewer._timer.isActive(), timeout=2)
    assert calls == [] and viewer._stale  # not visible: rebuilt when shown
    viewer.set_auto_update(False)
    viewer.schedule_update()
    assert not viewer._timer.isActive()
    viewer.close()


@pytest.mark.skipif(not occ_available(), reason="OpenCASCADE is not installed")
def test_shear_window_3d_follows_the_form(qapp):
    from openconex.gui.shear import ShearWindow

    window = ShearWindow(load_project(EXAMPLE.with_name("shear_single_plate.ocnx")))
    viewer = window.viewer
    viewer.update_model()
    assert _wait(viewer, lambda: viewer._model is not None and not viewer.is_busy)
    before = next(m for m in viewer._model if m.name == "plate")
    window._fields["thickness"].setText("1/2 in")
    assert viewer._stale  # the edit was seen without pressing Calcular
    viewer.update_model()
    assert _wait(viewer, lambda: not viewer.is_busy)
    after = next(m for m in viewer._model if m.name == "plate")
    span = (max(p[2] for t in after.triangles for p in t)
            - max(p[2] for t in before.triangles for p in t))
    assert span == pytest.approx(25.4 / 4, abs=1e-6)
    window.close()
