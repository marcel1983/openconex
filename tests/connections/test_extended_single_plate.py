# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Extended single plate against AISC Design Example II.A-19A (v16.1)."""

import pytest

from openconex.connections.shear.extended_single_plate import (
    ExtendedSinglePlate,
    check_extended_single_plate,
)
from openconex.core.loads import Method
from openconex.core.model import BoltSpec
from openconex.units import Kind, from_internal, to_internal


def inch(v):
    return to_internal(v, "in", Kind.LENGTH)


def kip(v):
    return to_internal(v, "kip", Kind.FORCE)


def kip_in(v):
    return to_internal(v, "kip*in", Kind.MOMENT)


def ksi(v):
    return to_internal(v, "ksi", Kind.STRESS)


# W16x36 beam (tw = 0.295 in.) to a W14x90 column web (tw = 0.440 in.);
# PL1/2x12 A572 Gr. 50, two lines of four 3/4 in. Group 120-N bolts, s = g = 3 in.,
# a = 9 in. to the first line, lev = 1-1/2 in., leh = 1-1/4 in., 5/16 in. welds
EX = ExtendedSinglePlate(bolt=BoltSpec(diameter=inch(0.75)), rows=4, spacing=inch(3),
                         length=inch(12), thickness=inch(0.5), lev=inch(1.5), leh=inch(1.25),
                         a=inch(9), plate_Fy=ksi(50), plate_Fu=ksi(65), beam_tw=inch(0.295),
                         beam_Fu=ksi(65), weld=inch(5 / 16), support_t=inch(0.440),
                         support_Fu=ksi(65), lines=2, gage=inch(3))

EXPECTED = [  # (id, LRFD, ASD, unit, tolerance)
    ("extended_plate.bolts", 41.7, 27.7, kip, 0.01),
    ("extended_plate.shear_yielding", 180, 120, kip, 0.01),
    ("extended_plate.shear_rupture", 125, 83.0, kip, 0.01),
    ("extended_plate.block_shear", 145, 96.5, kip, 0.01),
    ("extended_plate.flexural_yielding", 810, 539, kip_in, 0.01),
    ("extended_plate.flexural_ltb", 810, 539, kip_in, 0.01),
    # Znet = 12.75 in.3 from the holes against 12.8 in.3 from Manual Table 15-2
    ("extended_plate.flexural_rupture", 624, 416, kip_in, 0.01),
]


@pytest.mark.parametrize(("method", "R", "col"), [(Method.LRFD, 36, 0), (Method.ASD, 24, 1)])
def test_example_ii_a_19a(method, R, col):
    results = {r.id: r for r in check_extended_single_plate(EX, kip(R), method)}
    for key, lrfd, asd, unit, tol in EXPECTED:
        assert results[key].capacity == pytest.approx(unit((lrfd, asd)[col]), rel=tol), key
    assert results["extended_plate.interaction"].demand == pytest.approx((0.200, 0.201)[col],
                                                                         abs=0.003)
    t_max = from_internal(results["extended_plate.max_thickness"].capacity, Kind.LENGTH, "in")
    assert t_max == pytest.approx(0.575, rel=0.01)
    assert results["extended_plate.support_thickness"].demand == pytest.approx(inch(0.238),
                                                                                rel=0.01)
    assert all(r.status.value == "ok" for r in results.values())
