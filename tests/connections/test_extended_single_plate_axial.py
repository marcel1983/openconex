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
    """AISC II.A-19B: PL 3/4 x 14 1/2 x 14 1/2, 2 x 5 - 1 in. bolts."""
    return ExtendedSinglePlate(
        bolt=BoltSpec(diameter=inch(1)), rows=5, spacing=inch(3), length=inch(14.5),
        thickness=inch(0.75), lev=inch(1.25), leh=inch(1.75), a=inch(9.75),
        plate_Fy=ksi(50), plate_Fu=ksi(65), beam_tw=inch(0.415), beam_Fu=ksi(65),
        weld=inch(0.5), support_t=inch(0.440), support_Fu=ksi(65), lines=2,
        gage=inch(3), beam_leh=inch(1.75), deformation_considered=False)


def test_ii_a_19b_plate_capacities():
    checks = by_id(check_extended_single_plate_axial(
        _plate(), kip(75), kip(60), Method.LRFD, angle=30))
    assert from_internal(checks["extended_plate.bolts"].capacity,
                         Kind.FORCE, "kip") == pytest.approx(101, rel=0.01)
    assert from_internal(checks["extended_plate.tension_yielding"].capacity,
                         Kind.FORCE, "kip") == pytest.approx(491, rel=0.01)
    assert from_internal(checks["extended_plate.tension_rupture"].capacity,
                         Kind.FORCE, "kip") == pytest.approx(313, rel=0.01)
    assert from_internal(checks["extended_plate.shear_yielding"].capacity,
                         Kind.FORCE, "kip") == pytest.approx(327, rel=0.01)
    assert from_internal(checks["extended_plate.flexural_yielding"].capacity,
                         Kind.MOMENT, "kip*in") == pytest.approx(1770, rel=0.01)
    assert from_internal(checks["extended_plate.flexural_ltb"].capacity,
                         Kind.MOMENT, "kip*in") == pytest.approx(1770, rel=0.01)
    assert from_internal(checks["extended_plate.block_shear"].capacity,
                         Kind.FORCE, "kip") == pytest.approx(228, rel=0.01)
    assert from_internal(checks["extended_plate.block_shear_axial"].capacity,
                         Kind.FORCE, "kip") == pytest.approx(354, rel=0.01)
    assert from_internal(checks["extended_plate.max_thickness"].capacity,
                         Kind.LENGTH, "in") == pytest.approx(1.04, rel=0.01)
    assert checks["extended_plate.block_shear_interaction"].demand == \
        pytest.approx(0.137, rel=0.01)


def test_ii_a_19b_through_the_connection_dispatcher():
    conn = ShearConnection(type=ShearType.EXTENDED_SINGLE_PLATE, element=_plate())
    checks = by_id(check_shear_connection(
        conn, Forces(V2=kip(75), P=-kip(60)), Method.LRFD, "II.A-19B"))
    assert "extended_plate.bolts" in checks
    assert "shear_connection.axial_unsupported" not in checks
    assert checks["extended_plate.bolts"].status.value == "ok"


def test_project_example_matches_the_published_case():
    project = load_project(EXAMPLES / "shear_extended_single_plate_axial.ocnx")
    conn = project.shear_model()
    checks = by_id(check_shear_connection(conn, project.case_forces()["S1"],
                                          Method.LRFD, "S1"))
    # The example uses the conservative Table 7-7 value at 30°; the direct ICR
    # analysis used by the project is slightly stronger.
    assert from_internal(checks["extended_plate.bolts"].capacity,
                         Kind.FORCE, "kip") == pytest.approx(107.17, rel=0.01)
    assert from_internal(checks["extended_plate.flexural_yielding"].demand,
                         Kind.MOMENT, "kip*in") == pytest.approx(731.25, rel=0.01)
