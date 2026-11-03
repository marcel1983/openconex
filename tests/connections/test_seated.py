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
