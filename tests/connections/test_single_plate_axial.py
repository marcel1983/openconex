# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Single plate under shear and axial tension against AISC Design Example II.A-17B (v16.1)."""

import pytest

from openconex.connections.shear.single_plate import SinglePlate
from openconex.connections.shear.single_plate_axial import check_single_plate_axial
from openconex.core.loads import Method
from openconex.core.model import BoltSpec
from openconex.units import Kind, to_internal


def inch(v):
    return to_internal(v, "in", Kind.LENGTH)


def kip(v):
    return to_internal(v, "kip", Kind.FORCE)


def kip_in(v):
    return to_internal(v, "kip*in", Kind.MOMENT)


def ksi(v):
    return to_internal(v, "ksi", Kind.STRESS)


# W18x50 beam (tw = 0.355 in.) to W14x90 column flange (tf = 0.710 in.), A992;
# PL1/2x14-1/2 A572 Gr. 50, five 7/8 in. Group 120-N bolts at 3 in., a = 2-1/2 in.,
# lev = 1-1/4 in., leh = 2-1/2 in. (plate), 1-3/4 in. (beam web), 5/16 in. welds
EX = SinglePlate(bolt=BoltSpec(diameter=inch(0.875)), rows=5, spacing=inch(3),
                 length=inch(14.5), thickness=inch(0.5), lev=inch(1.25), leh=inch(2.5),
                 a=inch(2.5), plate_Fy=ksi(50), plate_Fu=ksi(65), beam_tw=inch(0.355),
                 beam_Fu=ksi(65), weld=inch(5 / 16), support_t=inch(0.710),
                 support_Fu=ksi(65), deformation_considered=False, beam_leh=inch(1.75))

# (id, LRFD, ASD, unit)
EXPECTED = [
    ("single_plate.bolts", 98.9, 65.9, kip),
    ("single_plate.shear_yielding", 218, 145, kip),
    ("single_plate.tension_yielding", 327, 217, kip),
    ("single_plate.flexural_yielding", 1180, 784, kip_in),
    ("single_plate.flexural_ltb", 1190, 790, kip_in),
    ("single_plate.shear_rupture", 139, 92.5, kip),
    ("single_plate.tension_rupture", 232, 155, kip),
    ("single_plate.flexural_rupture", 840, 560, kip_in),
    ("single_plate.block_shear", 177, 118, kip),
    ("single_plate.block_shear_axial", 242, 161, kip),
    ("single_plate.support_shear_rupture", 602, 402, kip),
]
RATIOS = [("single_plate.interaction_yielding", 0.181, 0.182),
          ("single_plate.interaction_rupture", 0.500, 0.501),
          ("single_plate.block_shear_interaction", 0.241, 0.241)]


@pytest.mark.parametrize(("method", "V", "N", "col"),
                         [(Method.LRFD, 75, 60, 0), (Method.ASD, 50, 40, 1)])
def test_example_ii_a_17b(method, V, N, col):
    # the example takes C from Table 7-6 at 30° (conservative)
    results = {r.id: r for r in check_single_plate_axial(EX, kip(V), kip(N), method, angle=30)}
    for key, lrfd, asd, unit in EXPECTED:
        assert results[key].capacity == pytest.approx(unit((lrfd, asd)[col]), rel=0.01), key
    for key, lrfd, asd in RATIOS:
        assert results[key].demand == pytest.approx((lrfd, asd)[col], abs=0.005), key
    assert all(r.status.value == "ok" for r in results.values())


def test_the_resultant_angle_is_close_to_the_tabulated_30_degrees():
    exact = check_single_plate_axial(EX, kip(75), kip(60), Method.LRFD)[0]
    table = check_single_plate_axial(EX, kip(75), kip(60), Method.LRFD, angle=30)[0]
    # for one vertical line, C hardly changes between 30° and 45°
    assert exact.capacity == pytest.approx(table.capacity, rel=0.01)
    assert exact.demand == pytest.approx(kip(96.0), rel=0.001)


def test_without_axial_load_it_is_the_shear_only_check():
    ids = {r.id for r in check_single_plate_axial(EX, kip(50), 0.0, Method.LRFD)}
    assert "single_plate.tension_yielding" not in ids and "single_plate.bolts" in ids
