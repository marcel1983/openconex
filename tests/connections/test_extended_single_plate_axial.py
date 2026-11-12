# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Extended single plate under shear and axial tension (AISC II.A-19B)."""

from pathlib import Path

import pytest

from openconex.connections.shear.check import ShearConnection, ShearType, check_shear_connection
from openconex.connections.shear.extended_single_plate import ExtendedSinglePlate
from openconex.connections.shear.extended_single_plate_axial import (
    check_extended_single_plate_axial,
)
from openconex.core.loads import Forces, Method
from openconex.core.model import BoltSpec
from openconex.io.project import load_project
from openconex.units import Kind, from_internal, to_internal

EXAMPLES = Path(__file__).parents[2] / "examples"


def inch(value):
    return to_internal(value, "in", Kind.LENGTH)


def kip(value):
    return to_internal(value, "kip", Kind.FORCE)


def ksi(value):
    return to_internal(value, "ksi", Kind.STRESS)


def by_id(results):
    return {result.id: result for result in results}


def _plate():
    """AISC II.A-19B: PL 3/4 x 15, 2 x 5 - 1 in. bolts, lev = 1 1/2 in., leh = 2 in.

    The beam web edge distance is 2 in.; the code subtracts the 1/4 in. underrun.
    """
    return ExtendedSinglePlate(
        bolt=BoltSpec(diameter=inch(1)), rows=5, spacing=inch(3), length=inch(15),
        thickness=inch(0.75), lev=inch(1.5), leh=inch(2), a=inch(9.75),
        plate_Fy=ksi(50), plate_Fu=ksi(65), beam_tw=inch(0.415), beam_Fu=ksi(65),
        weld=inch(0.5), support_t=inch(0.440), support_Fu=ksi(65), lines=2,
        gage=inch(3), beam_leh=inch(2), deformation_considered=False)


# (id, LRFD, ASD, unit) published in II.A-19B; the bolt group uses C from Table 7-7 at 30°
PUBLISHED = [
    ("bolts", 112, 74.8, "kip"),
    ("shear_yielding", 339, 226, "kip"),
    ("tension_yielding", 509, 338, "kip"),
    ("tension_rupture", 332, 221, "kip"),
    ("shear_rupture", 199, 133, "kip"),
    ("flexural_yielding", 1900, 1260, "kip*in"),
    ("flexural_rupture", 1260, 840, "kip*in"),
    ("block_shear", 237, 158, "kip"),
    ("block_shear_axial", 369, 246, "kip"),
    ("support_shear_rupture", 386, 258, "kip"),
]
RATIOS = [("interaction_yielding", 0.246, 0.248), ("interaction_rupture", 0.592, 0.592),
          ("block_shear_interaction", 0.127, 0.127)]


@pytest.mark.parametrize(("method", "V", "N", "col"),
                         [(Method.LRFD, 75, 60, 0), (Method.ASD, 50, 40, 1)])
def test_ii_a_19b_plate_capacities(method, V, N, col):
    checks = by_id(check_extended_single_plate_axial(
        _plate(), kip(V), kip(N), method, angle=30))
    for key, lrfd, asd, unit in PUBLISHED:
        kind = Kind.MOMENT if unit == "kip*in" else Kind.FORCE
        assert from_internal(checks[f"extended_plate.{key}"].capacity, kind, unit) == \
            pytest.approx((lrfd, asd)[col], rel=0.01), key
    for key, lrfd, asd in RATIOS:
        assert checks[f"extended_plate.{key}"].demand == \
            pytest.approx((lrfd, asd)[col], abs=0.003), key
    assert from_internal(checks["extended_plate.max_thickness"].capacity,
                         Kind.LENGTH, "in") == pytest.approx(0.971, rel=0.01)


@pytest.mark.parametrize(("method", "V", "N", "expected"),
                         [(Method.LRFD, 75, 60, 410), (Method.ASD, 50, 40, 272)])
def test_ii_a_19b_compression_comments(method, V, N, expected):
    """II.A-19B Comments: K = 1.2, L = a = 9 3/4 in., Lc/r = 54.0, φFcr = 36.4 ksi."""
    checks = by_id(check_extended_single_plate_axial(
        _plate(), kip(V), kip(N), method, compression=True))
    comp = checks["extended_plate.compression"]
    assert from_internal(comp.capacity, Kind.FORCE, "kip") == pytest.approx(expected, rel=0.01)
    slenderness = next(s.value for s in comp.steps if s.symbol == r"\frac{L_c}{r}")
    assert slenderness == pytest.approx(54.0, rel=0.001)
    assert not {"extended_plate.tension_yielding", "extended_plate.tension_rupture",
                "extended_plate.block_shear_axial"} & set(checks)
    assert checks["extended_plate.interaction_yielding"].status.value == "ok"


def test_ii_a_19b_through_the_connection_dispatcher():
    conn = ShearConnection(type=ShearType.EXTENDED_SINGLE_PLATE, element=_plate())
    checks = by_id(check_shear_connection(
        conn, Forces(V2=kip(75), P=-kip(60)), Method.LRFD, "II.A-19B"))
    assert "extended_plate.bolts" in checks
    assert "shear_connection.axial_unsupported" not in checks
    assert checks["extended_plate.bolts"].status.value == "ok"


def test_compression_through_the_dispatcher():
    conn = ShearConnection(type=ShearType.EXTENDED_SINGLE_PLATE, element=_plate())
    checks = by_id(check_shear_connection(
        conn, Forces(V2=kip(75), P=kip(60)), Method.LRFD, "C"))
    assert "extended_plate.compression" in checks
    assert "shear_connection.axial_compression" not in checks


def test_project_example_matches_the_published_case():
    project = load_project(EXAMPLES / "shear_extended_single_plate_axial.ocnx")
    conn = project.shear_model()
    checks = by_id(check_shear_connection(conn, project.case_forces()["S1"],
                                          Method.LRFD, "S1"))
    # The example uses the conservative Table 7-7 value at 30° (112 kips); the project
    # analyses the group at the actual resultant angle, 38.7°, and gets more.
    bolts = from_internal(checks["extended_plate.bolts"].capacity, Kind.FORCE, "kip")
    assert bolts == pytest.approx(119.8, rel=0.01)
    assert bolts > 112
    assert from_internal(checks["extended_plate.flexural_yielding"].demand,
                         Kind.MOMENT, "kip*in") == pytest.approx(731.25, rel=0.01)
