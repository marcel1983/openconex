# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Shear end plate against AISC Design Example II.A-11A (v16.1), Part B."""

import pytest

from openconex.connections.shear.end_plate import EndPlate, check_end_plate
from openconex.core.loads import Method
from openconex.core.model import BoltSpec
from openconex.units import Kind, to_internal


def inch(v):
    return to_internal(v, "in", Kind.LENGTH)


def kip(v):
    return to_internal(v, "kip", Kind.FORCE)


def ksi(v):
    return to_internal(v, "ksi", Kind.STRESS)


# W18x50 beam (tw = 0.355 in.) to a W21x62 girder web (tw = 0.400 in.);
# PL1/4x8-1/2 A572 Gr. 50, three rows of two 3/4 in. Group 120-N bolts at 3 in.,
# lev = leh = 1-1/4 in., 3/16 in. welds
EX = EndPlate(bolt=BoltSpec(diameter=inch(0.75)), rows=3, spacing=inch(3), length=inch(8.5),
              thickness=inch(0.25), lev=inch(1.25), leh=inch(1.25), plate_Fy=ksi(50),
              plate_Fu=ksi(65), weld=inch(3 / 16), beam_tw=inch(0.355), beam_Fu=ksi(65),
              support_t=inch(0.400), support_Fu=ksi(65))

EXPECTED = [
    ("end_plate.bolts", 96.4, 64.1),
    ("end_plate.shear_yielding", 128, 85.3),
    ("end_plate.shear_rupture", 86.3, 57.5),
    ("end_plate.block_shear", 93.8, 62.5),
    ("end_plate.weld", 67.9, 45.3),
]


@pytest.mark.parametrize(("method", "R", "col"), [(Method.LRFD, 60, 0), (Method.ASD, 40, 1)])
def test_example_ii_a_11a(method, R, col):
    results = {r.id: r for r in check_end_plate(EX, kip(R), method)}
    for key, *values in EXPECTED:
        assert results[key].capacity == pytest.approx(kip(values[col]), rel=0.01), key
    assert results["end_plate.beam_web_thickness"].demand == pytest.approx(inch(0.286),
                                                                             rel=0.01)
    assert all(r.status.value == "ok" for r in results.values())
    # the welds govern, as in the example
    assert max(results.values(), key=lambda r: r.ratio).id == "end_plate.weld"
