# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""All-bolted double angle against AISC Design Example II.A-1A (v16.0), Part B."""

import pytest

from openconex.connections.shear.double_angle import DoubleAngle, check_double_angle
from openconex.core.loads import Method
from openconex.core.model import BoltSpec
from openconex.units import Kind, to_internal


def inch(v):
    return to_internal(v, "in", Kind.LENGTH)


def kip(v):
    return to_internal(v, "kip", Kind.FORCE)


def ksi(v):
    return to_internal(v, "ksi", Kind.STRESS)


# W36x231 beam (tw = 0.760 in.) to W14x90 column flange (tf = 0.710 in.), A992;
# 2L5x3-1/2x5/16 A572 Gr. 50, l = 23-1/2 in., eight 3/4 in. Group 120-N bolts at 3 in.,
# lev = 1-1/4 in., leh = 1-3/8 in. at the beam web
EX = DoubleAngle(bolt=BoltSpec(diameter=inch(0.75)), rows=8, spacing=inch(3),
                 length=inch(23.5), thickness=inch(5 / 16), lev=inch(1.25),
                 leh_beam=inch(1.375), leh_support=inch(1.75), angle_Fy=ksi(50),
                 angle_Fu=ksi(65), beam_tw=inch(0.760), beam_Fu=ksi(65),
                 support_t=inch(0.710), support_Fu=ksi(65))

# (check id, LRFD φRn, ASD Rn/Ω) [kips]
EXPECTED = [
    ("double_angle.bolts_beam", 282, 187),
    ("double_angle.bolts_support", 282, 187),
    ("double_angle.angle_shear_yielding", 441, 294),
    ("double_angle.angle_shear_rupture", 302, 201),
    ("double_angle.block_shear_beam", 315, 210),
]


@pytest.mark.parametrize(("method", "R", "column"), [(Method.LRFD, 226, 1), (Method.ASD, 151, 2)])
def test_example_ii_a_1a(method, R, column):
    results = {r.id: r for r in check_double_angle(EX, kip(R), method)}
    for key, *values in EXPECTED:
        assert results[key].capacity == pytest.approx(kip(values[column - 1]), rel=0.01), key
        assert results[key].demand == pytest.approx(kip(R))
    assert all(r.status.value == "ok" for r in results.values())
    # the bolt holes govern, as in the example
    governing = max(results.values(), key=lambda r: r.ratio)
    assert governing.id.startswith("double_angle.bolts_")


def test_block_shear_governs_on_the_narrower_leg():
    results = {r.id: r for r in check_double_angle(EX, kip(100), Method.LRFD)}
    assert results["double_angle.block_shear_beam"].capacity < \
        results["double_angle.block_shear_support"].capacity


# II.A-2A: same beam and column, 2L4x3-1/2x3/8 (l = 23-1/2 in.) bolted to the beam web
# (eight 3/4 in. bolts, leh = 1-3/8 in.) and welded to the column flange with 5/16 in.
# fillet welds B (e = 4 in.)
WELDED = DoubleAngle(bolt=BoltSpec(diameter=inch(0.75)), rows=8, spacing=inch(3),
                     length=inch(23.5), thickness=inch(0.375), lev=inch(1.25),
                     leh_beam=inch(1.375), leh_support=inch(0), angle_Fy=ksi(50),
                     angle_Fu=ksi(65), beam_tw=inch(0.760), beam_Fu=ksi(65),
                     support_t=inch(0.710), support_Fu=ksi(65), support_weld=inch(5 / 16),
                     weld_e=inch(4))

EXPECTED_2A = [
    ("double_angle.bolts_beam", 286, 190),
    ("double_angle.angle_shear_yielding", 528, 352),
    ("double_angle.angle_shear_rupture", 363, 242),
    ("double_angle.block_shear_beam", 380, 253),
    ("double_angle.weld_support", 318, 212),
]


@pytest.mark.parametrize(("method", "R", "col"), [(Method.LRFD, 226, 0), (Method.ASD, 151, 1)])
def test_example_ii_a_2a_welded_support(method, R, col):
    results = {r.id: r for r in check_double_angle(WELDED, kip(R), method)}
    for key, *values in EXPECTED_2A:
        assert results[key].capacity == pytest.approx(kip(values[col]), rel=0.01), key
    assert results["double_angle.support_thickness"].demand == pytest.approx(inch(0.238),
                                                                               rel=0.01)
    assert "double_angle.bolts_support" not in results
    assert all(r.status.value == "ok" for r in results.values())


# II.A-3: all-welded 2L4x3-1/2x5/16 (SLBB), l = 24 in., 3/16 in. welds A on the 3-1/2 in.
# legs and 1/4 in. welds B on the 4 in. legs
ALL_WELDED = DoubleAngle(bolt=BoltSpec(diameter=inch(0.75)), rows=0, spacing=inch(3),
                         length=inch(24), thickness=inch(5 / 16), lev=inch(0), leh_beam=inch(0),
                         leh_support=inch(0), angle_Fy=ksi(50), angle_Fu=ksi(65),
                         beam_tw=inch(0.760), beam_Fu=ksi(65), support_t=inch(0.710),
                         support_Fu=ksi(65), support_weld=inch(0.25), weld_e=inch(4),
                         beam_weld=inch(3 / 16), beam_leg=inch(3.5))

EXPECTED_3 = [
    ("double_angle.weld_beam", 257, 171),
    ("double_angle.weld_support", 260, 173),
    ("double_angle.angle_shear_yielding", 450, 300),
    ("double_angle.angle_shear_rupture", 439, 293),
]


@pytest.mark.parametrize(("method", "R", "col"), [(Method.LRFD, 226, 0), (Method.ASD, 151, 1)])
def test_example_ii_a_3_all_welded(method, R, col):
    results = {r.id: r for r in check_double_angle(ALL_WELDED, kip(R), method)}
    for key, *values in EXPECTED_3:
        assert results[key].capacity == pytest.approx(kip(values[col]), rel=0.01), key
    assert results["double_angle.beam_web_thickness"].demand == pytest.approx(inch(0.286),
                                                                               rel=0.01)
    assert results["double_angle.support_thickness"].demand == pytest.approx(inch(0.190),
                                                                              rel=0.01)
    assert not {"double_angle.bolts_beam", "double_angle.bolts_support"} & set(results)
    assert all(r.status.value == "ok" for r in results.values())
