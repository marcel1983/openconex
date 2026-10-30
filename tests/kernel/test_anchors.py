# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""ACI 318-19 Chapter 17 checks against AISC Design Guide 1 examples (LRFD)."""

import pytest

from openconex.core.loads import Method
from openconex.kernel import anchors as A  # noqa: N812
from openconex.units import Kind, from_internal, to_internal

LRFD = Method.LRFD


def inch(v):
    return to_internal(v, "in", Kind.LENGTH)


def ksi(v):
    return to_internal(v, "ksi", Kind.STRESS)


def kips(v):
    return from_internal(v, Kind.FORCE, "kip")


def in2(v):
    return from_internal(v, Kind.AREA, "in**2")


def step(result, symbol):
    return [s.value for s in result.steps if s.symbol == symbol][-1]


F36 = (ksi(58), ksi(36))


@pytest.mark.parametrize(("d", "ase"), [(0.75, 0.334), (0.875, 0.462), (1.0, 0.606),
                                        (1.5, 1.41), (2.0, 2.50)])
def test_tensile_stress_area_table_4_1(d, ase):
    assert in2(A.tensile_stress_area(inch(d))) == pytest.approx(ase, rel=0.005)


@pytest.mark.parametrize(("d", "abrg"), [(1.0, 1.50), (1.5, 3.12)])
def test_heavy_hex_bearing_area(d, abrg):
    assert in2(A.heavy_hex_bearing_area(inch(d))) == pytest.approx(abrg, rel=0.01)


def test_lrfd_only():
    with pytest.raises(ValueError):
        A.steel_tension(inch(1), *F36, 0.0, Method.ASD)


def test_dg1_4_7_3():
    r = A.breakout_tension(inch(15), ksi(4), 0.0, LRFD, span_x=inch(4), span_y=inch(4))
    assert in2(step(r, "A_{Nc}")) == pytest.approx(2400, rel=0.005)
    assert kips(step(r, "N_b")) == pytest.approx(92.3, rel=0.005)
    assert kips(r.capacity) == pytest.approx(76.3, rel=0.01)
    hook = A.pullout_hook(inch(0.875), inch(2.63), ksi(4), 0.0, LRFD)
    assert kips(step(hook, "N_p")) == pytest.approx(8.28, rel=0.005)
    assert kips(hook.capacity) == pytest.approx(5.80, rel=0.005)


def test_dg1_4_7_4_shear_breakout():
    r = A.breakout_shear(inch(0.75), inch(12), inch(12), ksi(4), 0.0, LRFD, spacing=inch(4))
    assert in2(step(r, "A_{Vc}")) == pytest.approx(720)
    assert kips(step(r, "V_b")) == pytest.approx(23.7, rel=0.005)
    assert kips(r.capacity) == pytest.approx(18.4, rel=0.005)


def test_dg1_4_7_5():
    r = A.breakout_tension(inch(12), ksi(4), 0.0, LRFD, span_x=inch(8.5),
                           edges=A.Edges(bottom=inch(10.8)))
    assert step(r, r"\psi_{ed,N}") == pytest.approx(0.880, rel=0.002)
    assert kips(r.capacity) == pytest.approx(38.6, rel=0.01)
    bearing = A.shear_lug_bearing(inch(8), inch(2), ksi(4), 0.0, LRFD)
    assert kips(bearing.capacity) == pytest.approx(70.9, rel=0.005)
    breakout = A.shear_lug_breakout(inch(8), inch(2), inch(14.5), ksi(4), 0.0, LRFD)
    assert in2(step(breakout, "A_{Vc}")) == pytest.approx(1210, rel=0.005)
    assert kips(step(breakout, "V_b")) == pytest.approx(31.4, rel=0.005)
    assert kips(breakout.capacity) == pytest.approx(26.1, rel=0.005)


def test_dg1_4_7_7():
    d = inch(1.5)
    assert kips(A.steel_tension(d, *F36, 0.0, LRFD).capacity) == pytest.approx(61.4, rel=0.005)
    bo = A.breakout_tension(inch(24), ksi(5), 0.0, LRFD, span_x=inch(28), span_y=inch(6.5))
    assert in2(step(bo, "A_{Nc}")) == pytest.approx(7850, rel=0.005)
    assert kips(step(bo, "N_b")) == pytest.approx(226, rel=0.005)
    assert kips(bo.capacity) == pytest.approx(239, rel=0.005)
    po = A.pullout(A.heavy_hex_bearing_area(d), ksi(5), 0.0, LRFD)
    assert kips(po.capacity) == pytest.approx(87.5, rel=0.01)
    vs = A.steel_shear(d, *F36, 0.0, LRFD, grout_pad=True)
    assert kips(vs.capacity) == pytest.approx(25.5, rel=0.005)
    pr = A.pryout(step(bo, "N_{cbg}"), inch(24), 0.0, LRFD)
    assert kips(pr.capacity) == pytest.approx(479, rel=0.005)
    it = A.tension_shear_interaction(to_internal(138, "kip", Kind.FORCE), bo.capacity,
                                     to_internal(14.5, "kip", Kind.FORCE), vs.capacity)
    assert it.demand == pytest.approx(1.15, abs=0.005)
    assert it.capacity == 1.2 and it.status == "ok"


def test_dg1_4_7_9():
    assert kips(A.steel_tension(inch(1), *F36, 0.0, LRFD).capacity) == pytest.approx(26.3,
                                                                                       rel=0.005)
    bo = A.breakout_tension(inch(12), ksi(4), 0.0, LRFD, span_x=inch(6))
    assert in2(step(bo, "A_{Nc}")) == pytest.approx(1510, rel=0.005)
    assert kips(bo.capacity) == pytest.approx(51.7, rel=0.01)  # DG1 rounds A_Nco to 1,300
    po = A.pullout(A.heavy_hex_bearing_area(inch(1)), ksi(4), 0.0, LRFD)
    assert kips(po.capacity) == pytest.approx(33.6, rel=0.01)


def test_dg1_4_7_11():
    bo = A.breakout_tension(inch(18), ksi(4), 0.0, LRFD, span_x=inch(12))
    assert in2(step(bo, "A_{Nc}")) == pytest.approx(3560, rel=0.005)
    assert kips(step(bo, "N_b")) == pytest.approx(125, rel=0.005)
    assert kips(bo.capacity) == pytest.approx(106, rel=0.01)


def test_dg1_4_7_15_edges_and_reinforcement():
    e = inch(8)
    bo = A.breakout_tension(inch(14), ksi(4), 0.0, LRFD, span_x=inch(4), span_y=inch(4),
                            edges=A.Edges(e, e, e, e))
    assert from_internal(step(bo, "h_{ef}"), Kind.LENGTH, "in") == pytest.approx(5.33, rel=0.005)
    assert in2(step(bo, "A_{Nc}")) == pytest.approx(400, rel=0.005)
    assert kips(step(bo, "N_b")) == pytest.approx(18.7, rel=0.005)
    assert kips(bo.capacity) == pytest.approx(20.4, rel=0.01)
    reinf = A.anchor_reinforcement(to_internal(70, "kip", Kind.FORCE), ksi(60),
                                   to_internal(1.76, "in**2", Kind.AREA), LRFD)
    assert reinf.status == "ok"
    assert kips(reinf.capacity) == pytest.approx(0.75 * 60 * 1.76)


def test_dg1_6_4_1_seismic():
    bo = A.breakout_tension(inch(24), ksi(4), 0.0, LRFD, span_x=inch(16), seismic=True)
    assert in2(step(bo, "A_{Nc}")) == pytest.approx(6340, rel=0.005)
    assert kips(bo.capacity) == pytest.approx(130, rel=0.005)
    washer = to_internal(4.0 - 0.7854, "in**2", Kind.AREA)  # 2 in. square plate minus rod
    po = A.pullout(washer, ksi(4), 0.0, LRFD, seismic=True)
    assert kips(po.capacity) == pytest.approx(53.9, rel=0.005)


def test_side_face_blowout_only_near_edge():
    r = A.side_face_blowout(inch(4), A.heavy_hex_bearing_area(inch(1)), ksi(4), 0.0, LRFD,
                            hef=inch(12))
    expected = 160 * 4 * 1.50**0.5 * 4000**0.5 / 1000 * 0.70
    assert r.applicable and kips(r.capacity) == pytest.approx(expected, rel=0.01)
    far = A.side_face_blowout(inch(8), A.heavy_hex_bearing_area(inch(1)), ksi(4), 0.0, LRFD,
                              hef=inch(12))
    assert not far.applicable
