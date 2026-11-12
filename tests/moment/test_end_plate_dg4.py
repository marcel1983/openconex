# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Moment end plates against AISC Design Guide 4, 2nd ed. (2004), Chapter 4.

W21x55 beam to a W14x109 column (A992), A572 Gr. 50 end plate, 9 in. wide on a
5 1/2 in. gage. LRFD values, kips and kip-in.
"""

import dataclasses

import pytest

from openconex.connections.moment.end_plate import (
    EndPlate,
    EndPlateLayout,
    end_plate_strength,
)
from openconex.connections.moment.fr_moment import (
    FlangeDetail,
    MomentConnection,
    check_moment_connection,
)
from openconex.core.loads import Method
from openconex.core.model import BoltSpec
from openconex.core.shapes import aisc_shapes
from openconex.units import Kind, from_internal, to_internal

BEAM = aisc_shapes().get("W21X55")
COLUMN = aisc_shapes().get("W14X109").to_ishape("ASTM A992")


def inch(v):
    return to_internal(v, "in", Kind.LENGTH)


def kip(f):
    return from_internal(f, Kind.FORCE, "kip")


def connection(layout, tp, db, grade, pf, pfo, pext, pb=0.0, reinforcement=0.0,
               flange_weld=0.0, plates=0.0):
    plate = EndPlate(layout=layout, bolt=BoltSpec(diameter=inch(db), grade=grade),
                     width=inch(9), thickness=inch(tp), gage=inch(5.5), pf=inch(pf),
                     Fy=to_internal(50, "ksi", Kind.STRESS),
                     Fu=to_internal(65, "ksi", Kind.STRESS), pb=inch(pb), pf_o=inch(pfo),
                     pext=inch(pext), weld_reinforcement=inch(reinforcement),
                     flange_weld=inch(flange_weld))
    return MomentConnection(detail=FlangeDetail.END_PLATE,
                            beam=BEAM.to_ishape("ASTM A992"), beam_Sx=BEAM["Sx"],
                            column=COLUMN, end_plate=plate, plate_Fy=plate.Fy,
                            plate_Fu=plate.Fu, continuity_plate=inch(plates))


A490 = "ASTM F3125 Gr. A490"
A325 = "ASTM F3125 Gr. A325"
# 4E Example A: 1 1/4 in. plate, 1 1/4 in. A490 bolts, CJP welds with 5/16 in. reinforcement
EX_A = connection(EndPlateLayout.EXTENDED_4, 1.25, 1.25, A490, 2, 2, 3.625,
                  reinforcement=5 / 16)
# 4E Example B: 7/8 in. plate, 1 in. A325 bolts, 3/8 in. fillet welds at the flanges
EX_B = connection(EndPlateLayout.EXTENDED_4, 0.875, 1.0, A325, 2, 2, 3.625, flange_weld=3 / 8)
# 8ES Example: 7/8 in. plate, 1 in. A325 bolts, p_b = 3 in., d_e = 1 1/4 in.
EX_8ES = connection(EndPlateLayout.EXTENDED_8_STIFFENED, 0.875, 1.0, A325, 1.75, 1.75, 6.0,
                    pb=3, reinforcement=5 / 16)


def results(mc, M, V=40.0):
    return {r.id: r for r in check_moment_connection(
        mc, to_internal(V, "kip", Kind.FORCE), to_internal(M, "kip*in", Kind.MOMENT),
        Method.LRFD)}


def steps(result):
    return {s.symbol: s.value for s in result.steps}


@pytest.mark.parametrize(("mc", "M", "Ffu", "Yc", "treq", "flange", "yielding", "buckling",
                          "crippling"), [
    (EX_A, 8039, 396, 170.1, 1.10, 279, 326, 330, 284),
    (EX_8ES, 8083, 399, 224.6, 0.97, 369, 306, 330, 284),
], ids=["4E-A", "8ES"])
def test_column_side(mc, M, Ffu, Yc, treq, flange, yielding, buckling, crippling):
    r = results(mc, M)
    bending = r["moment.column_flange_bending"]
    assert from_internal(steps(bending)["Y_c"], Kind.LENGTH, "in") == pytest.approx(Yc, rel=2e-3)
    assert from_internal(bending.demand, Kind.LENGTH, "in") == pytest.approx(treq, abs=0.01)
    assert kip(r["moment.column_flange_strength"].demand) == pytest.approx(Ffu, rel=2e-3)
    assert kip(r["moment.column_flange_strength"].capacity) == pytest.approx(flange, rel=5e-3)
    assert kip(r["moment.column_web_local_yielding"].capacity) == pytest.approx(yielding,
                                                                                rel=5e-3)
    assert kip(r["moment.column_web_compression_buckling"].capacity) == pytest.approx(
        buckling, rel=5e-3)
    assert kip(r["moment.column_web_crippling"].capacity) == pytest.approx(crippling, rel=5e-3)


def test_example_b_wind_column_side():
    """4E Example B: t_fc,req = 0.790 in. < 0.860 in. The Guide takes N = t_fb = 0.522 in.
    for web yielding (289 kips) and N = t_fb + 0.707(3/8) = 0.787 in. for crippling
    (275 kips); OpenConex uses N = 0.787 in. for both (296 kips)."""
    r = results(EX_B, 4000)
    assert from_internal(r["moment.column_flange_bending"].demand, Kind.LENGTH,
                         "in") == pytest.approx(0.790, abs=0.005)
    assert kip(r["moment.column_web_crippling"].capacity) == pytest.approx(275, rel=5e-3)
    yielding = r["moment.column_web_local_yielding"].capacity
    assert kip(yielding) == pytest.approx(289 + 0.707 * 0.375 * 50 * 0.525, rel=5e-3)
    assert all(v.ratio <= 1 for v in r.values() if v.applicable)


@pytest.mark.parametrize(("mc", "M", "plates", "Yc", "treq"), [
    (EX_A, 8039, 0.5, 309.1, 0.82),
    (EX_8ES, 8083, 0.5, 377.7, 0.75),
], ids=["4E-A", "8ES"])
def test_stiffened_column_flange(mc, M, plates, Yc, treq):
    """With 1/2 in. continuity plates. The 8ES Example writes h_2 = 22.24 in. for 22.29 in."""
    r = results(dataclasses.replace(mc, continuity_plate=inch(plates)), M)
    bending = r["moment.column_flange_bending"]
    assert from_internal(steps(bending)["Y_c"], Kind.LENGTH, "in") == pytest.approx(Yc, rel=2e-3)
    assert from_internal(bending.demand, Kind.LENGTH, "in") == pytest.approx(treq, abs=0.01)
    assert bending.ratio <= 1
    for key in ("column_flange_strength", "column_web_local_yielding",
                "column_web_compression_buckling", "column_web_crippling"):
        assert not r[f"moment.{key}"].applicable
    # Eq. 3.32 with the strengths the examples compute in Steps 15 to 18
    force = r["moment.continuity_plates"]
    expected = {"4E-A": 396 - 279, "8ES": 399 - 284}["4E-A" if mc is EX_A else "8ES"]
    assert kip(force.demand) == pytest.approx(expected, rel=1e-2)
    # two 1/2 in. plates, (14.6 - 0.525)/2 wide: 0.9(50)(2)(7.04)(0.5)
    assert kip(force.capacity) == pytest.approx(0.9 * 50 * 2 * 7.0375 * 0.5, rel=1e-3)


def test_8es_end_plate():
    """8ES Example: Y_p = 277.6 in. (Case 1, d_e = 1.25 in. < s = 3.52 in.),
    M_np = 11 470 k-in., t_p,req = 0.87 in. < 7/8 in."""
    cy, _, cb, rupture = end_plate_strength(EX_8ES, Method.LRFD)
    values = {s.symbol: s.value for s in cy.steps + cb.steps}
    assert from_internal(values["Y"], Kind.LENGTH, "in") == pytest.approx(277.6, rel=2e-3)
    mnp = from_internal(values["M_{np}"], Kind.MOMENT, "kip*in")
    assert mnp == pytest.approx(11470, rel=2e-3)
    assert from_internal(rupture, Kind.MOMENT, "kip*in") == pytest.approx(0.75 * 11470,
                                                                          rel=2e-3)
    assert any("thick plate" in s.clause for s in cb.steps)


def test_8es_thin_plate_is_not_covered():
    thin = dataclasses.replace(EX_8ES, end_plate=dataclasses.replace(
        EX_8ES.end_plate, thickness=inch(0.625)))
    _, _, cb, rupture = end_plate_strength(thin, Method.LRFD)
    assert rupture == 0.0
    assert any("8ES" in s.clause for s in cb.steps)


@pytest.mark.parametrize(("mc", "plate", "column"), [
    (EX_A, 503, 503), (EX_B, 314, 402), (EX_8ES, 646, 805)], ids=["4E-A", "4E-B", "8ES"])
def test_compression_bolt_bearing(mc, plate, column):
    """Eq. 3.18 and 3.19, with the AISC 360-22 Table J3.3 holes (1 3/8 in. for 1 1/4 in.
    bolts and 1 1/8 in. for 1 in. bolts; the Guide uses 1 5/16 and 1 1/16 in.).

    4E Example A: outer bolts tear out to the plate edge, l_c = 1 5/8 - 1 3/8 / 2 =
    0.9375 in. (91.4 kips; 94.5 kips with the Guide's hole), inner bolts bear (244 kips):
    0.75[2(91.4) + 2(244)] = 503 kips (508 in the Guide). Examples B and 8ES take tearout
    only toward the adjacent bolts (411 and 807 kips); OpenConex also checks the edge of the
    outermost row, as Example A does, because the shear can act either way. Column flange:
    2.4 d t_fc F_u per bolt."""
    r = results(mc, 4000)["moment.end_plate_bolt_shear"]
    values = steps(r)
    assert kip(values[r"\sum r_{n,plate}"]) == pytest.approx(plate, rel=1e-2)
    assert kip(values[r"\sum r_{n,col}"]) == pytest.approx(column, rel=1e-2)


def test_example_a_bearing_with_the_guide_hole():
    """With the 1 5/16 in. hole of the Guide: l_c = 0.969 in., 94.5 kips per outer bolt."""
    from openconex.kernel import bolts
    b = EX_A.end_plate.bolt
    rn = bolts.bolt_tearout(b, inch(1.25), to_internal(65, "ksi", Kind.STRESS),
                            inch(1.625 - 1.3125 / 2), 0.0, Method.LRFD).capacity
    assert kip(rn) / 0.75 == pytest.approx(94.5, rel=2e-3)
    assert 0.75 * (2 * kip(rn) / 0.75 + 2 * 244) == pytest.approx(508, rel=2e-3)
