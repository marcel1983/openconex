# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""FR moment connections against AISC Design Examples II.B-1, II.B-2 and II.B-3 (v16)."""

import dataclasses

import pytest

from openconex.connections.moment.fr_moment import (
    FlangeDetail,
    FlangePlate,
    MomentConnection,
    WebPlate,
    check_moment_connection,
)
from openconex.core.loads import Method
from openconex.core.model import BoltSpec
from openconex.core.shapes import aisc_shapes
from openconex.units import Kind, from_internal, to_internal


def inch(v):
    return to_internal(v, "in", Kind.LENGTH)


def kip(v):
    return to_internal(v, "kip", Kind.FORCE)


def kip_ft(v):
    return to_internal(v, "kip*ft", Kind.MOMENT)


def ksi(v):
    return to_internal(v, "ksi", Kind.STRESS)


W18X50 = aisc_shapes().get("W18X50")
BEAM = W18X50.to_ishape("ASTM A992")
COLUMN = aisc_shapes().get("W14X99").to_ishape("ASTM A992")
BOLT = BoltSpec(diameter=inch(0.875))
# Single plate PL3/8 x 9, three 7/8 in. bolts at 3 in., lev = 1 1/2 in., leh = 2 in., 1/4 in. welds
WEB = WebPlate(bolt=BOLT, rows=3, spacing=inch(3), length=inch(9), thickness=inch(0.375),
               lev=inch(1.5), leh=inch(2), weld=inch(0.25), Fy=ksi(50), Fu=ksi(65))

# II.B-1: PL3/4 x 7 flange plates, two lines of four 7/8 in. bolts at 3 in. on a 4 in. gage,
# lev = 1 1/2 in. (plate and beam, less 1/4 in. underrun), 3/8 in. welds to the column
B1 = MomentConnection(
    detail=FlangeDetail.BOLTED_FLANGE_PLATE, beam=BEAM, beam_Sx=W18X50["Sx"], column=COLUMN,
    web=WEB, plate_Fy=ksi(50), plate_Fu=ksi(65),
    top=FlangePlate(width=inch(7), thickness=inch(0.75), weld_to_column=inch(0.375),
                    unbraced_length=inch(3)),
    bolt=BOLT, rows=4, spacing=inch(3), gage=inch(4), plate_lev=inch(1.5),
    beam_lev=inch(1.5))

# II.B-2: top PL1 x 6 with 5/16 in. welds (2 x 8.94 in. + 6 in. across), 7/16 in. to the
# column; bottom PL3/4 x 8 3/4 with 2 x 12 1/2 in. of 5/16 in. welds, 5/16 in. to the column
B2 = dataclasses.replace(
    B1, detail=FlangeDetail.WELDED_FLANGE_PLATE, bolt=None, rows=0,
    top=FlangePlate(width=inch(6), thickness=inch(1), weld_to_column=inch(7 / 16),
                    unbraced_length=0.0, weld_to_beam=inch(5 / 16), weld_length=inch(8.94),
                    transverse_weld=True),
    bottom=FlangePlate(width=inch(8.75), thickness=inch(0.75), weld_to_column=inch(5 / 16),
                       unbraced_length=inch(1.75), weld_to_beam=inch(5 / 16),
                       weld_length=inch(12.5)))

LOADS = [(Method.LRFD, 42, 252, 0), (Method.ASD, 28, 168, 1)]

B1_EXPECTED = [  # (id, LRFD, ASD, unit)
    ("beam_flexural_rupture", 318, 211, kip_ft),
    ("web_bolts", 71.2, 47.5, kip),
    ("web_plate_shear_yielding", 101, 67.3, kip),
    ("web_plate_shear_rupture", 65.9, 43.9, kip),
    ("web_plate_block_shear", 82.2, 54.9, kip),
    ("web_weld", 100, 66.8, kip),
    ("web_support_rupture", 410, 273, kip),
    ("flange_bolts", 194, 130, kip),
    ("flange_plate_tension_yielding", 237, 157, kip),
    ("flange_plate_tension_rupture", 183, 122, kip),
    ("flange_plate_block_shear", 300, 200, kip),
    ("beam_flange_block_shear", 294, 197, kip),
    # Dmin = 5.51/5.54 sixteenths for 161/108 kips: 3/8 in. welds give 161 x 6/5.51
    ("flange_plate_weld", 161 * 6 / 5.51, 108 * 6 / 5.54, kip),
    ("flange_plate_compression", 237, 157, kip),
    ("column_flange_local_bending", 171, 114, kip),
    ("column_web_local_yielding", 186, 124, kip),
    ("column_web_crippling", 233, 155, kip),
]
B1_DEMANDS = [("flange_bolts", 168, 112), ("flange_plate_tension_yielding", 161, 108),
              ("beam_flange_block_shear", 168, 112), ("column_web_crippling", 161, 108)]


def by_id(results):
    return {r.id.removeprefix("moment."): r for r in results}


@pytest.mark.parametrize(("method", "V", "M", "col"), LOADS)
def test_example_ii_b_1(method, V, M, col):
    results = by_id(check_moment_connection(B1, kip(V), kip_ft(M), method))
    for key, lrfd, asd, unit in B1_EXPECTED:
        assert results[key].capacity == pytest.approx(unit((lrfd, asd)[col]), rel=0.01), key
    for key, lrfd, asd in B1_DEMANDS:
        assert results[key].demand == pytest.approx(kip((lrfd, asd)[col]), rel=0.01), key
    assert results["beam_flexural_rupture"].applicable
    assert all(r.status.value == "ok" for r in results.values())


B2_EXPECTED = [
    ("flange_plate_tension_yielding", 270, 180, kip),
    ("top_plate_weld_to_beam", 169, 113, kip),
    # Dmin = 6.39/6.41 for 160/107 kips: 7/16 in. welds give 160 x 7/6.39
    ("top_plate_weld_to_column", 160 * 7 / 6.39, 107 * 7 / 6.41, kip),
    ("flange_plate_compression", 295, 196, kip),
    # lmin = 12.1 in. for 168/112 kips: 12 1/2 in. of welds give 168 x 12.5/12.1
    ("bottom_plate_weld_to_beam", 168 * 12.5 / 12.1, 112 * 12.5 / 12.1, kip),
    ("beam_flange_rupture_at_welds", 419, 279, kip),
    # Dmin = 4.38/4.39 for 160/107 kips: 5/16 in. welds give 160 x 5/4.38
    ("bottom_plate_weld_to_column", 160 * 5 / 4.38, 107 * 5 / 4.39, kip),
]


@pytest.mark.parametrize(("method", "V", "M", "col"), LOADS)
def test_example_ii_b_2(method, V, M, col):
    results = by_id(check_moment_connection(B2, kip(V), kip_ft(M), method))
    for key, lrfd, asd, unit in B2_EXPECTED:
        assert results[key].capacity == pytest.approx(unit((lrfd, asd)[col]), rel=0.01), key
    assert results["flange_plate_tension_yielding"].demand == pytest.approx(
        kip((160, 107)[col]), rel=0.01)
    assert results["top_plate_weld_to_beam"].demand == pytest.approx(kip((168, 112)[col]),
                                                                     rel=0.01)
    t_min = from_internal(results["weld_base_metal"].demand, Kind.LENGTH, "in")
    assert t_min == pytest.approx(0.238, rel=0.01)
    assert all(r.status.value == "ok" for r in results.values())


def test_example_ii_b_3_checks_web_and_column_only():
    b3 = dataclasses.replace(B1, detail=FlangeDetail.WELDED_FLANGE, top=None, bottom=None,
                             bolt=None, rows=0)
    results = by_id(check_moment_connection(b3, kip(42), kip_ft(252), Method.LRFD))
    assert not any(k.startswith(("flange_plate", "top_plate", "bottom_plate")) for k in results)
    assert {"web_bolts", "column_flange_local_bending", "column_web_crippling"} <= set(results)


def test_two_sided_and_panel_zone():
    two = dataclasses.replace(B1, two_sided=True)
    results = by_id(check_moment_connection(two, kip(42), kip_ft(252), Method.LRFD,
                                            column_shear=kip(20), column_axial=kip(100)))
    assert "column_web_compression_buckling" in results
    assert results["column_panel_zone"].demand == pytest.approx(kip(2 * 161 - 20), rel=0.01)
