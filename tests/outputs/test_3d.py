# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
import math

import pytest

from openconex.geometry3d.base_plate import occ_available
from openconex.io.project import HSSSectionInput

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
    expected = (24 * 22 * 2 - 4 * 3.14159265 * (1.8125 / 2) ** 2 * 2) * 25.4**3
    assert props.Mass() == pytest.approx(expected, rel=1e-4)
    step = write_step(parts, tmp_path / "bp.step")
    assert step.read_text()[:14] == "ISO-10303-21;\n"[:14]
    assert write_stl(parts, tmp_path / "bp.stl").stat().st_size > 10_000


def test_hss_column_volume(project):
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    from openconex.geometry3d.base_plate import base_plate_parts

    project.base_plate.column = HSSSectionInput(
        type="HSS", shape="round", d="12 in", t="0.5 in")
    parts = base_plate_parts(project.base_plate_model())
    column = next(p for p in parts if p.name == "column")
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(column.shape, props)
    d, t, h = 304.8, 12.7, 1.5 * 304.8
    expected = math.pi / 4 * (d**2 - (d - 2 * t) ** 2) * h
    assert props.Mass() == pytest.approx(expected, rel=1e-4)
