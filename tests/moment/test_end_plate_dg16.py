# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Moment end plates against the examples of AISC Design Guide 16 (2002, rev. 2016).

Each example is checked twice, with the plate and bolts of Design Procedure 1
(thick plate) and Design Procedure 2 (thin plate), against the connection
strength the Guide reports with the Appendix B flow chart, LRFD, k-in.
Built-up beams of A572 Gr. 50 with an A572 Gr. 50 end plate and A325 bolts.
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
from openconex.core.model import BoltSpec, IShape
from openconex.core.shapes import aisc_shapes
from openconex.units import Kind, from_internal, to_internal

L = EndPlateLayout
COLUMN = aisc_shapes().get("W14X90").to_ishape("ASTM A992")


def inch(v):
    return to_internal(v, "in", Kind.LENGTH)


def kip_in(m):
    return from_internal(m, Kind.MOMENT, "kip*in")


def kip(f):
    return from_internal(f, Kind.FORCE, "kip")


def connection(layout, h, bp, tf, tp, db, g, pf, snug=False, **dims):
    beam = IShape(name="BU", d=inch(h), bf=inch(bp), tf=inch(tf), tw=inch(0.25),
                  k_des=inch(tf + 0.25), grade="ASTM A572 Gr. 50")
    plate = EndPlate(layout=layout, bolt=BoltSpec(diameter=inch(db)), width=inch(bp),
                     thickness=inch(tp), gage=inch(g), pf=inch(pf),
                     Fy=to_internal(50, "ksi", Kind.STRESS), Fu=to_internal(65, "ksi", Kind.STRESS),
                     snug_tight=snug, **{k: inch(v) for k, v in dims.items()})
    return MomentConnection(detail=FlangeDetail.END_PLATE, beam=beam, beam_Sx=1.0,
                            column=COLUMN, end_plate=plate)


def strength(mc):
    cy, yielding, cb, rupture = end_plate_strength(mc, Method.LRFD)
    values = {s.symbol: s.value for s in cy.steps + cb.steps}
    thick = any("thick plate" in s.clause for s in cb.steps)
    return kip_in(yielding), kip_in(rupture), values, thick


EXT = {"pf_o": 2.5, "pext": 5}
# (example, connection, Y [in.], thick plate?, φMn [k-in.] from the Guide)
CASES = [
    ("3.2.1-1", connection(L.FLUSH_2, 18, 6, .25, .5, .625, 2.75, 1.375, True), 100.5, True, 673),
    ("3.2.1-2", connection(L.FLUSH_2, 18, 6, .25, .4375, .75, 2.75, 1.375, True), 100.5, False,
     693),
    ("3.2.2-1", connection(L.FLUSH_4, 18, 6, .25, .4375, .5, 2.75, 1.375, True, pb=3), 127.1,
     True, 783),
    ("3.2.2-2", connection(L.FLUSH_4, 18, 6, .25, .375, .5, 2.75, 1.375, True, pb=3), 127.1,
     False, 643),
    ("3.2.3-1", connection(L.FLUSH_4_STIFFENED_BETWEEN, 16, 6, .25, .5, .625, 3, 1.5, pb=3,
                           ps_o=1.375, stiffener_thickness=.375), 155.1, True, 1045),
    ("3.2.3-2", connection(L.FLUSH_4_STIFFENED_BETWEEN, 16, 6, .25, .4375, .75, 3, 1.5, pb=3,
                           ps_o=1.375, stiffener_thickness=.375), 155.1, False, 1069),
    ("3.2.4-1", connection(L.FLUSH_4_STIFFENED_INSIDE, 16, 6, .25, .5625, .625, 3, 1.5, pb=3,
                           ps=1.5), 105.0, True, 1045),
    ("4.2.1-1", connection(L.EXTENDED_4, 24, 8, .375, .5625, .625, 3, 1.75, True, **EXT), 187.4,
     True, 1987),
    ("4.2.1-2", connection(L.EXTENDED_4, 24, 8, .375, .5, .75, 3, 1.75, True, **EXT), 187.4,
     False, 2108),
    ("4.2.2-1", connection(L.EXTENDED_4_STIFFENED, 24, 8, .375, .4375, .625, 3, 1.75, True,
                           **EXT), 320.1, True, 1987),
    ("4.2.2-2", connection(L.EXTENDED_4_STIFFENED, 24, 8, .375, .375, .75, 3, 1.75, True, **EXT),
     320.1, False, 1824),
    ("4.2.3-2", connection(L.EXTENDED_1_2, 24, 8, .375, .5, .75, 3, 1.75, pb=2.5, **EXT), 216.1,
     False, 2431),
    ("4.2.4-1", connection(L.EXTENDED_1_3, 36, 8, .375, .625, .625, 3, 1.75, pb=2.5, **EXT),
     380.3, True, 5460),
    ("4.2.4-2", connection(L.EXTENDED_1_3, 36, 8, .375, .5625, .75, 3, 1.75, pb=2.5, **EXT),
     380.3, False, 5415),
    ("4.2.5-1", connection(L.EXTENDED_1_3_STIFFENED, 36, 8, .375, .5, .625, 3, 1.75, pb=2.5,
                           **EXT), 573.0, True, 5460),
    ("4.2.5-2", connection(L.EXTENDED_1_3_STIFFENED, 36, 8, .375, .4375, .75, 3, 1.75, pb=2.5,
                           **EXT), 573.0, False, 4935),
]


@pytest.mark.parametrize(("name", "mc", "Y", "thick", "phiMn"), CASES,
                         ids=[c[0] for c in CASES])
def test_design_guide_16_examples(name, mc, Y, thick, phiMn):
    yielding, rupture, values, is_thick = strength(mc)
    # 4.2.4 uses d_3 = 28.6875 in. for h_3 = 28.875 in. in Y: 0.2 % lower
    assert from_internal(values["Y"], Kind.LENGTH, "in") == pytest.approx(Y, rel=3e-3)
    assert is_thick is thick
    # 4.2.2-2 rounds a_i = 0.375 in. up to 0.38 in. (Q_max 1 % lower)
    assert min(yielding, rupture) == pytest.approx(phiMn, rel=1e-2)


# φM_q (k-in.) for the trial bolt of Design Procedure 2, and Q_max,i, Q_max,o (kips)
PRYING = [
    ("3.2.1", connection(L.FLUSH_2, 18, 6, .25, .4375, .75, 2.75, 1.375, True), 788, 7.49, None),
    ("3.2.2", connection(L.FLUSH_4, 18, 6, .25, .375, .5, 2.75, 1.375, True, pb=3), 658, 2.83,
     None),
    ("3.2.3", connection(L.FLUSH_4_STIFFENED_BETWEEN, 16, 6, .25, .4375, .75, 3, 1.5, pb=3,
                         ps_o=1.375, stiffener_thickness=.375), 1220, 7.59, None),
    ("4.2.1", connection(L.EXTENDED_4, 24, 8, .375, .5, .75, 3, 1.75, True, **EXT), 2175, 9.48,
     9.69),
    ("4.2.2", connection(L.EXTENDED_4_STIFFENED, 24, 8, .375, .375, .75, 3, 1.75, True, **EXT),
     1824, 14.3, 14.6),
    ("4.2.3", connection(L.EXTENDED_1_2, 24, 8, .375, .5, .75, 3, 1.75, pb=2.5, **EXT), 2981,
     9.48, 9.68),
    ("4.2.4", connection(L.EXTENDED_1_3, 36, 8, .375, .5625, .75, 3, 1.75, pb=2.5, **EXT), 6074,
     8.18, 8.39),
    ("4.2.5", connection(L.EXTENDED_1_3_STIFFENED, 36, 8, .375, .4375, .75, 3, 1.75, pb=2.5,
                         **EXT), 5588, 11.4, 11.6),
]


@pytest.mark.parametrize(("name", "mc", "phiMq", "Qi", "Qo"), PRYING, ids=[c[0] for c in PRYING])
def test_prying_forces(name, mc, phiMq, Qi, Qo):
    _, rupture, values, thick = strength(mc)
    assert not thick
    assert rupture == pytest.approx(phiMq, rel=1e-2)
    # the Guide rounds a_i to two decimals (0.38 for 0.375 in 4.2.2)
    assert kip(values["Q_{max,i}"]) == pytest.approx(Qi, rel=1.6e-2)
    if Qo is not None:
        assert kip(values["Q_{max,o}"]) == pytest.approx(Qo, rel=1e-2)


def test_appendix_b_classification_differs_from_reported_value():
    """3.2.4, Design Procedure 2: φM_np = 1045 ≤ φ_bM_pl/1.11 = 1064 k-in., so the corrected
    Appendix B flow chart (2016 errata) treats the plate as thick and gives
    min(φM_np, φ_bM_pl/γ_r) = 945 k-in.; the Guide reports φM_q = 901 k-in."""
    mc = connection(L.FLUSH_4_STIFFENED_INSIDE, 16, 6, .25, .5, .625, 3, 1.5, pb=3, ps=1.5)
    yielding, rupture, _, thick = strength(mc)
    assert thick
    assert yielding == pytest.approx(945, rel=2e-3)
    assert rupture == pytest.approx(1045, rel=2e-3)


def test_example_4_2_3_thick_plate_limit():
    """4.2.3, Design Procedure 1: φM_np = 2782 k-in. exceeds φ_bM_pl/1.11 = 2772 k-in. by
    0.4 %, so the flow chart takes the thin plate branch (prying with T_b = 19 k for the
    5/8 in. bolts) where the Guide reports the thick plate strength 2782 k-in."""
    mc = connection(L.EXTENDED_1_2, 24, 8, .375, .5625, .625, 3, 1.75, pb=2.5, **EXT)
    yielding, rupture, values, thick = strength(mc)
    assert kip_in(0.75 * values["M_{np}"]) == pytest.approx(2782, rel=1e-3)
    assert yielding / 1.11 == pytest.approx(2772, rel=1e-3)
    assert not thick
    assert rupture < yielding


def test_axial_tension_adds_to_the_moment():
    """4.2.3: T_u = 16.9 kips adds 16.9/2 × 23.625 = 200 k-in. to M_u = 2200 k-in."""
    mc = connection(L.EXTENDED_1_2, 24, 8, .375, .5, .75, 3, 1.75, pb=2.5, **EXT)
    results = check_moment_connection(mc, 0.0, to_internal(2200, "kip*in", Kind.MOMENT),
                                      Method.LRFD, P=-to_internal(16.9, "kip", Kind.FORCE))
    by_id = {r.id: r for r in results}
    yielding = by_id["moment.end_plate_yielding"]
    assert kip_in(yielding.demand) == pytest.approx(2400, rel=1e-3)
    assert kip_in(yielding.capacity) == pytest.approx(2431, rel=1e-3)
    assert yielding.ratio <= 1.0


def test_full_check_list_and_asd():
    mc = connection(L.EXTENDED_4, 24, 8, .375, .5, .75, 3, 1.75, True, **EXT)
    mc = dataclasses.replace(mc, end_plate=dataclasses.replace(
        mc.end_plate, web_weld=inch(0.25), flange_weld=inch(0.3125)))
    M = to_internal(1750, "kip*in", Kind.MOMENT)
    V = to_internal(30, "kip", Kind.FORCE)
    lrfd = {r.id: r for r in check_moment_connection(mc, V, M, Method.LRFD)}
    assert set(lrfd) == {
        "moment.end_plate_yielding", "moment.end_plate_bolt_rupture",
        "moment.end_plate_shear_yielding", "moment.end_plate_shear_rupture",
        "moment.end_plate_bolt_shear", "moment.end_plate_web_weld_shear",
        "moment.end_plate_web_weld_tension", "moment.end_plate_flange_weld",
        "moment.column_web_local_yielding", "moment.column_web_crippling",
        "moment.column_web_compression_buckling", "moment.column_flange_bending",
        "moment.column_flange_strength"}
    # flange force M/(d - t_f) = 1750/23.625 = 74.1 kips; half on each side of the flange
    shear = lrfd["moment.end_plate_shear_yielding"]
    assert kip(shear.demand) == pytest.approx(74.07 / 2, rel=1e-3)
    assert kip(shear.capacity) == pytest.approx(0.6 * 50 * 8 * 0.5, rel=1e-3)  # φ = 1.0
    # four 3/4 in. A325-N bolts at the compression flange: 4 × 17.9 kips
    assert kip(lrfd["moment.end_plate_bolt_shear"].capacity) == pytest.approx(4 * 17.9, rel=1e-2)
    asd = {r.id: r for r in check_moment_connection(mc, V / 1.5, M / 1.5, Method.ASD)}
    assert asd["moment.end_plate_yielding"].capacity == pytest.approx(
        lrfd["moment.end_plate_yielding"].capacity / 0.9 / 1.67, rel=1e-6)
    assert asd["moment.end_plate_bolt_rupture"].capacity == pytest.approx(
        lrfd["moment.end_plate_bolt_rupture"].capacity / 0.75 / 2.0, rel=1e-6)


def test_snug_tight_pretension_fraction():
    mc = connection(L.EXTENDED_4, 24, 8, .375, .5, .75, 3, 1.75, True, **EXT)
    _, _, values, _ = strength(mc)
    assert kip(values["T_b"]) == pytest.approx(14.0)
    mc = dataclasses.replace(mc, end_plate=dataclasses.replace(mc.end_plate, snug_tight=False))
    _, _, values, _ = strength(mc)
    assert kip(values["T_b"]) == pytest.approx(28.0)
