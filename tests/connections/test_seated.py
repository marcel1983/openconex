# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Unstiffened seated connection against AISC Design Example II.A-12A (v16.1)."""

import dataclasses

import pytest

from openconex.connections.shear.seated import SeatedAngle, check_seated
from openconex.core.loads import Method
from openconex.core.model import BoltSpec
from openconex.units import Kind, to_internal


def inch(v):
    return to_internal(v, "in", Kind.LENGTH)


def kip(v):
    return to_internal(v, "kip", Kind.FORCE)


def ksi(v):
    return to_internal(v, "ksi", Kind.STRESS)


# W16x50 beam on an 8 in. long L6x4x5/8 seat (4 in. outstanding leg), A572 Gr. 50,
# bolted to a W14x90 column web (tw = 0.440 in.) with 3/4 in. Group 120-N bolts
EX = SeatedAngle(length=inch(8), thickness=inch(0.625), leg=inch(4), Fy=ksi(50),
                 bolt=BoltSpec(diameter=inch(0.75)), bolts=4, support_t=inch(0.440),
                 support_Fu=ksi(65), angle_Fu=ksi(65), beam_d=inch(16.3), beam_tw=inch(0.380),
                 beam_tf=inch(0.630), beam_kdes=inch(1.03), beam_Fy=ksi(50))


def step(check, symbol):
    return next(s.value for s in check.steps if s.symbol == symbol)


@pytest.mark.parametrize(("method", "R", "col"), [(Method.LRFD, 54.8, 0), (Method.ASD, 36.5, 1)])
def test_example_ii_a_12a(method, R, col):
    results = {r.id: r for r in check_seated(EX, kip(R), method)}
    bearing = results["seated.bearing_length"]
    assert step(bearing, r"l_{b,yielding}") == pytest.approx(inch((0.309, 0.307)[col]), rel=0.02)
    assert step(bearing, r"l_{b,crippling}") < 0  # negative: k_des governs
    assert bearing.demand == pytest.approx(inch(1.03))
    assert bearing.capacity == pytest.approx(inch(3.25))
    assert results["seated.shear_yielding"].capacity == pytest.approx(kip((150, 100)[col]),
                                                                       rel=0.01)
    assert results["seated.top_angle_leg"].demand == pytest.approx(inch(4))
    assert results["seated.top_angle_thickness"].demand == pytest.approx(inch(1 / 4))
    assert results["seated.top_angle_bolts"].demand == 2
    assert all(r.status.value == "ok" for r in results.values())


def test_flexure_matches_table_10_5():
    # the example enters Manual Table 10-5 with lb = 1-1/8 in.: 113 / 74.9 kips
    seat = dataclasses.replace(EX, bearing_length=inch(1.125))
    for method, expected in ((Method.LRFD, 113), (Method.ASD, 74.9)):
        flexure = {r.id: r for r in check_seated(seat, kip(30), method)}["seated.flexural_yielding"]
        assert flexure.capacity == pytest.approx(kip(expected), rel=0.01)


def test_bearing_on_thin_parts_governs_the_bolts():
    # Manual Table 10-5 footnote: t_min = 0.204 in. for bearing to exceed bolt shear
    thin = dataclasses.replace(EX, support_t=inch(0.18))
    bolts = {r.id: r for r in check_seated(thin, kip(30), Method.LRFD)}["seated.bolts"]
    full = {r.id: r for r in check_seated(EX, kip(30), Method.LRFD)}["seated.bolts"]
    assert bolts.capacity < full.capacity
    assert full.capacity == pytest.approx(kip(4 * 17.9), rel=0.01)


def test_top_angle_below_the_standard_detail_fails():
    small = dataclasses.replace(EX, top_angle_thickness=inch(3 / 16))
    check = {r.id: r for r in check_seated(small, kip(30), Method.LRFD)}
    assert check["seated.top_angle_thickness"].status.value == "ng"


# II.A-13: L8x4x5/8, 8 in. long, welded to a W14x61 column flange with 5/16 in. welds;
# W21x62 beam. II.A-16: L7x4x5/8, 6 in. long, same welds
WELDED = dataclasses.replace(EX, beam_d=inch(21.0), beam_tw=inch(0.400), beam_tf=inch(0.615),
                             beam_kdes=inch(1.12), support_weld=inch(5 / 16),
                             vertical_leg=inch(8), support_t=inch(0.645))


@pytest.mark.parametrize(("seat", "R", "expected"), [
    (WELDED, (54.8, 36.5), (66.7, 44.5)),
    (dataclasses.replace(WELDED, length=inch(6), vertical_leg=inch(7)), (51.4, 34.2),
     (53.4, 35.6)),
])
@pytest.mark.parametrize(("method", "col"), [(Method.LRFD, 0), (Method.ASD, 1)])
def test_welded_seats_ii_a_13_and_16(seat, R, expected, method, col):
    results = {r.id: r for r in check_seated(seat, kip(R[col]), method)}
    assert results["seated.weld"].capacity == pytest.approx(kip(expected[col]), rel=0.01)
    assert "seated.bolts" not in results
    assert "seated.top_angle_weld" in results
    assert "seated.top_angle_bolts" not in results
    assert results["seated.bearing_length"].demand == pytest.approx(inch(1.12))
    assert all(r.status.value == "ok" for r in results.values())
