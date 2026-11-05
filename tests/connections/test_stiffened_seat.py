# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Stiffened seat against AISC Design Examples II.A-14 and II.A-15 (v16.1)."""

import dataclasses

import pytest

from openconex.connections.shear.stiffened_seat import StiffenedSeat, check_stiffened_seat
from openconex.core.loads import Method
from openconex.units import Kind, to_internal


def inch(v):
    return to_internal(v, "in", Kind.LENGTH)


def kip(v):
    return to_internal(v, "kip", Kind.FORCE)


def ksi(v):
    return to_internal(v, "ksi", Kind.STRESS)


# W21x68 beam on a PL5/8x7x15 stiffener with 5/16 in. welds, A572 Gr. 50; II.A-15 welds it
# to a W14x90 column web (tw = 0.440 in.)
EX = StiffenedSeat(width=inch(7), length=inch(15), thickness=inch(0.625), stiffener_Fy=ksi(50),
                   weld=inch(5 / 16), beam_d=inch(21.1), beam_tw=inch(0.430),
                   beam_tf=inch(0.685), beam_kdes=inch(1.19), beam_Fy=ksi(50),
                   support_t=inch(0.440), support_Fu=ksi(65))


def step(check, symbol):
    return next(s.value for s in check.steps if s.symbol == symbol)


@pytest.mark.parametrize(("method", "R", "col"), [(Method.LRFD, 125, 0), (Method.ASD, 83.5, 1)])
def test_example_ii_a_14_15(method, R, col):
    results = {r.id: r for r in check_stiffened_seat(EX, kip(R), method)}
    width = results["stiffened_seat.width"]
    assert step(width, r"W_{min,crippling}") == pytest.approx(inch((6.93, 6.96)[col]), rel=0.01)
    assert step(width, r"W_{min,yielding}") == pytest.approx(inch((3.59, 3.61)[col]), rel=0.01)
    assert results["stiffened_seat.weld"].capacity == pytest.approx(kip((139, 93.0)[col]),
                                                                     rel=0.01)
    assert results["stiffened_seat.stiffener_thickness"].demand == pytest.approx(inch(0.469),
                                                                                  rel=0.01)
    assert results["stiffened_seat.support_thickness"].demand == pytest.approx(inch(0.238),
                                                                                rel=0.01)
    assert results["stiffened_seat.seat_plate_bearing"].capacity == pytest.approx(
        kip((295, 197)[col]), rel=0.01)
    assert results["stiffened_seat.seat_plate_width"].demand == pytest.approx(inch(8))
    assert results["stiffened_seat.seat_plate_thickness"].demand == pytest.approx(inch(3 / 8))
    assert results["stiffened_seat.seat_plate_weld_length"].demand == pytest.approx(inch(3))
    assert results["seated.top_angle_thickness"].demand == pytest.approx(inch(1 / 4))
    assert all(r.status.value == "ok" for r in results.values())


def test_seat_plate_below_the_standard_detail_fails():
    small = dataclasses.replace(EX, seat_plate_thickness=inch(1 / 4))
    results = {r.id: r for r in check_stiffened_seat(small, kip(125), Method.LRFD)}
    assert results["stiffened_seat.seat_plate_thickness"].status.value == "ng"


def test_two_sided_web_is_too_thin():
    support = check_stiffened_seat(dataclasses.replace(EX, two_sided=True), kip(125),
                                   Method.LRFD)[-1]
    assert support.demand == pytest.approx(inch(0.476), rel=0.01)
    assert support.status.value == "ng"
