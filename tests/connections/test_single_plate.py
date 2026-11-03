# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Conventional single plate against AISC Design Example II.A-17A (v16.1)."""

import pytest

from openconex.connections.shear.single_plate import SinglePlate, check_single_plate
from openconex.core.loads import Method
from openconex.core.model import BoltSpec
from openconex.units import Kind, to_internal


def inch(v):
    return to_internal(v, "in", Kind.LENGTH)


def kip(v):
    return to_internal(v, "kip", Kind.FORCE)


def ksi(v):
    return to_internal(v, "ksi", Kind.STRESS)


# W16x50 beam (tw = 0.380 in.) to W14x90 column flange (tf = 0.710 in.);
# PL1/4x11-1/2 A572 Gr. 50, four 3/4 in. Group 120-N bolts at 3 in., a = 3 in., 3/16 in. weld
EX = SinglePlate(bolt=BoltSpec(diameter=inch(0.75)), rows=4, spacing=inch(3),
                 length=inch(11.5), thickness=inch(0.25), lev=inch(1.25), leh=inch(1.5),
                 a=inch(3), plate_Fy=ksi(50), plate_Fu=ksi(65), beam_tw=inch(0.380),
                 beam_Fu=ksi(65), weld=inch(3 / 16), support_t=inch(0.710),
                 support_Fu=ksi(65))

# (check id, LRFD, ASD, tolerance) [kips]; ICR gives C = 3.556 vs 3.54 interpolated
EXPECTED = [
    ("single_plate.bolts", 58.5, 38.9, 0.01),
    ("single_plate.shear_yielding", 86.4, 57.6, 0.01),
    ("single_plate.shear_rupture", 58.5, 39.0, 0.01),
    ("single_plate.block_shear", 65.3, 43.6, 0.01),
]


@pytest.mark.parametrize(("method", "R", "col"), [(Method.LRFD, 49.6, 0), (Method.ASD, 33.0, 1)])
def test_example_ii_a_17a(method, R, col):
    results = {r.id: r for r in check_single_plate(EX, kip(R), method)}
    for key, lrfd, asd, tol in EXPECTED:
        assert results[key].capacity == pytest.approx(kip((lrfd, asd)[col]), rel=tol), key
    assert all(r.status.value == "ok" for r in results.values()), \
        [r.id for r in results.values() if r.status.value != "ok"]
    for key in ("single_plate.max_thickness", "single_plate.leh", "single_plate.lev",
                "single_plate.weld_size", "single_plate.support_thickness"):
        assert key in results
