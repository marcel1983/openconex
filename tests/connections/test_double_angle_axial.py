# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Double angle under shear and axial tension against AISC Design Example II.A-1B (v16.1)."""

import pytest

from openconex.connections.shear.double_angle import DoubleAngle
from openconex.connections.shear.double_angle_axial import AxialBeam, check_double_angle_axial
from openconex.core.loads import Method
from openconex.core.model import BoltSpec
from openconex.units import Kind, to_internal


def inch(v):
    return to_internal(v, "in", Kind.LENGTH)


def kip(v):
    return to_internal(v, "kip", Kind.FORCE)


def ksi(v):
    return to_internal(v, "ksi", Kind.STRESS)


# W18x50 beam (tw = 0.355 in.); 2L5x3-1/2x5/8 (SLBB), l = 14-1/2 in., five 7/8 in. Group 120-N
# bolts at 3 in., lev = 1-1/4 in., leh = 1-1/4 in. (beam leg) and 1-7/16 in. (outstanding
# legs), gage 7-1/2 in.; beam web leh = 1-3/4 in. less 1/4 in. underrun
EX = DoubleAngle(bolt=BoltSpec(diameter=inch(0.875)), rows=5, spacing=inch(3),
                 length=inch(14.5), thickness=inch(0.625), lev=inch(1.25),
                 leh_beam=inch(1.25), leh_support=inch(1 + 7 / 16), angle_Fy=ksi(50),
                 angle_Fu=ksi(65), beam_tw=inch(0.355), beam_Fu=ksi(65),
                 support_t=inch(0.710), support_Fu=ksi(65))
BEAM = AxialBeam(d=inch(18.0), tf=inch(0.570), Ag=to_internal(14.7, "in**2", Kind.AREA),
                 Fy=ksi(50))

EXPECTED = [
    ("double_angle.bolts_beam", 182, 122),
    ("double_angle.bolts_tension", 98.1, 65.4),
    ("double_angle.angle_shear_yielding", 543, 362),
    ("double_angle.angle_shear_rupture", 348, 232),
    ("double_angle.angle_tension_yielding", 815, 542),
    ("double_angle.angle_tension_rupture", 581, 387),
    ("double_angle.block_shear_beam", 368, 245),
    ("double_angle.block_shear_axial", 542, 362),
    ("double_angle.block_shear_support", 379, 253),
    ("double_angle.beam_shear_yielding", 192, 128),
    ("double_angle.beam_tension_yielding", 662, 440),
    ("double_angle.beam_tension_rupture", 256, 171),
    ("double_angle.beam_block_shear", 159, 106),
]


@pytest.mark.parametrize(("method", "V", "N", "col"),
                         [(Method.LRFD, 75, 60, 0), (Method.ASD, 50, 40, 1)])
def test_example_ii_a_1b(method, V, N, col):
    results = {r.id: r for r in check_double_angle_axial(
        EX, kip(V), kip(N), method, gage=inch(7.5), outstanding_leg=inch(5),
        beam_leh=inch(1.75), beam=BEAM)}
    for key, *values in EXPECTED:
        assert results[key].capacity == pytest.approx(kip(values[col]), rel=0.01), key
    # the example combines with the L-shaped axial block (559/373 kips): 0.0531; the
    # U-shape is lower and gives 0.054
    assert results["double_angle.block_shear_interaction"].demand == pytest.approx(0.0531,
                                                                                   abs=0.002)
    assert all(r.status.value == "ok" for r in results.values())
