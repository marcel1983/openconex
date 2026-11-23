# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
import math
import re

import pytest

from openconex.geometry3d.base_plate import occ_available
from openconex.io.project import HSSSectionInput, load_project

from .conftest import EXAMPLE

pytestmark = pytest.mark.skipif(not occ_available(), reason="OCP not installed (openconex[3d])")


def test_parts_and_exports(tmp_path, project):
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    from openconex.geometry3d.base_plate import base_plate_parts, write_step, write_stl

    parts = base_plate_parts(project.base_plate_model())
    names = [p.name for p in parts]
    assert names[:4] == ["pedestal", "grout", "base_plate", "column"]
    assert sum(n.startswith("anchor_rod") for n in names) == 4
    plate = next(p for p in parts if p.name == "base_plate")
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(plate.shape, props)
    expected = (24 * 22 * 2 - 4 * 3.14159265 * (1.875 / 2) ** 2 * 2) * 25.4**3
    assert props.Mass() == pytest.approx(expected, rel=1e-4)
    step = write_step(parts, tmp_path / "bp.step")
    assert step.read_text()[:14] == "ISO-10303-21;\n"[:14]
    assert write_stl(parts, tmp_path / "bp.stl").stat().st_size > 10_000


def test_context_column_is_optional():
    from openconex.geometry3d.shear import shear_parts

    project = load_project(EXAMPLE.with_name("shear_single_plate.ocnx"))
    plain = [part.name for part in shear_parts(project.shear_model())]
    context = [part.name for part in shear_parts(project.shear_model(),
                                                 context="column")]
    assert "support_context" not in plain
    assert "support_context" in context
    girder = [part.name for part in shear_parts(project.shear_model(),
                                                context="beam")]
    assert "support_context" in girder


def test_bent_plate_parts():
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    from openconex.geometry3d.shear import shear_parts

    project = load_project(EXAMPLE.with_name("shear_skewed_bent_plate.ocnx"))
    parts = shear_parts(project.shear_model())
    names = [part.name for part in parts]
    assert {"beam", "support", "bent_plate_a", "bent_plate_b"} <= set(names)
    assert sum(name.startswith("bolt_") for name in names) == 6
    for name in ("bent_plate_a", "bent_plate_b"):
        part = next(part for part in parts if part.name == name)
        props = GProp_GProps()
        BRepGProp.VolumeProperties_s(part.shape, props)
        assert props.Mass() > 0.0


def test_shear_lug_volume():
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    from openconex.geometry3d.base_plate import base_plate_parts

    project = load_project(EXAMPLE.with_name("base_plate_shear_lug.ocnx"))
    bp = project.base_plate_model()
    parts = base_plate_parts(bp, grout=bp.shear_lug.grout)
    lug = next(p for p in parts if p.name == "shear_lug")
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(lug.shape, props)
    width, thickness = 8 * 25.4, 1 * 25.4
    height = 2 * 25.4 + 2 * 25.4  # grout + embedment
    assert props.Mass() == pytest.approx(width * thickness * height, rel=1e-4)


def test_isometric_keeps_the_column_vertical():
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt

    from openconex.geometry3d.base_plate import Part, isometric_svg

    column = BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 10, 10, 100).Shape()
    svg = isometric_svg([Part("column", column)])
    points = [tuple(map(float, point.split(",")))
              for group in re.findall(r'points="([^"]+)"', svg)
              for point in group.split()]
    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    assert max(ys) - min(ys) > 2 * (max(xs) - min(xs))


def test_hss_column_volume(project):
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    from openconex.geometry3d.base_plate import base_plate_parts

    project.base_plate.column = HSSSectionInput(
        type="HSS", shape="round", d="12 in", t="0.5 in",
        grade="ASTM A500 Gr. C (round)")
    parts = base_plate_parts(project.base_plate_model())
    column = next(p for p in parts if p.name == "column")
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(column.shape, props)
    d, t, h = 304.8, 12.7, 1.5 * 304.8
    expected = math.pi / 4 * (d**2 - (d - 2 * t) ** 2) * h
    assert props.Mass() == pytest.approx(expected, rel=1e-4)


def _bounds(shape):
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib

    box = Bnd_Box()
    BRepBndLib.Add_s(shape, box)
    return (*box.CornerMin().Coord(), *box.CornerMax().Coord())


def _shear_parts(name: str):
    from openconex.geometry3d.shear import shear_parts

    project = load_project(EXAMPLE.with_name(name))
    return project, {part.name: part for part in shear_parts(project.shear_model())}


def test_seated_angle_bolts_and_angles():
    """II.A-12A: 4 bolts in the seat (2 rows × 2), short bolts, one solid per angle."""
    project, parts = _shear_parts("shear_seated_ii_a_12a.ocnx")
    inch = 25.4
    bolts = [name for name in parts if name.startswith("support_bolt")]
    assert len(bolts) == 4
    seat_t = 5 / 8 * inch
    support_t = project.shear_model().support.tw
    for name in bolts:
        x0, _, _, x1, _, _ = _bounds(parts[name].shape)
        # support + seat leg + about one diameter of head and nut: not the
        # 8 in angle length the layout used to give.
        assert x1 - x0 == pytest.approx(support_t + seat_t + 0.75 * inch, abs=0.01)
    # One solid per angle, with both legs starting at the support face.
    names = list(parts)
    assert names.count("seat") == 1 and names.count("top_angle") == 1
    for name in ("seat", "top_angle"):
        x0, *_ = _bounds(parts[name].shape)
        assert x0 == pytest.approx(0.0, abs=1e-6)
    x0, y0, _, x1, y1, _ = _bounds(parts["top_angle"].shape)
    assert x1 - x0 == pytest.approx(4 * inch, abs=1e-6)  # horizontal leg
    assert y1 - y0 == pytest.approx(4 * inch, abs=1e-6)  # vertical leg


def test_extended_single_plate_beam_clears_the_support():
    """II.A-19A: the beam end is beam_leh from the first bolt line (a − beam_leh)."""
    _, parts = _shear_parts("shear_extended_single_plate_axial.ocnx")
    inch = 25.4
    x0, *_ = _bounds(parts["beam"].shape)
    assert x0 == pytest.approx((9.75 - 2) * inch, abs=1e-6)
    bolt_x0, *_ = _bounds(parts["bolt1"].shape)
    assert bolt_x0 > x0


def test_web_bolts_cross_the_real_plies():
    """A single-plate bolt sticks out by r on each side of web + plate only."""
    project, parts = _shear_parts("shear_single_plate.ocnx")
    model = project.shear_model()
    tw, t, d = model.beam.tw, model.element.thickness, model.element.bolt.diameter
    *_, z0, _, _, z1 = _bounds(parts["bolt1"].shape)
    assert z0 == pytest.approx(-tw / 2 - d / 2, abs=1e-6)
    assert z1 == pytest.approx(tw / 2 + t + d / 2, abs=1e-6)


def test_skewed_beam_does_not_cross_the_support():
    _, parts = _shear_parts("shear_skewed_bent_plate.ocnx")
    beam_x0, *_ = _bounds(parts["beam"].shape)
    assert beam_x0 == pytest.approx(12.7, abs=0.01)  # 1/2 in clear, cut parallel
    for name in ("bent_plate_a", "bent_plate_b"):
        x0, *_ = _bounds(parts[name].shape)
        assert x0 >= -1e-6
