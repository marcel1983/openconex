# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Bolt checks against AISC Manual tables and AISC Design Guide 1 examples."""

import pytest

from openconex.core.bolting import HoleType, min_pretension
from openconex.core.loads import Method
from openconex.core.model import BoltSpec, Threads
from openconex.kernel.bolts import (
    SlipClass,
    bolt_bearing,
    bolt_shear,
    bolt_slip,
    bolt_spacing_checks,
    bolt_tearout,
    bolt_tension,
    bolt_tension_shear,
    clear_distance,
)
from openconex.units import Kind, from_internal, to_internal

A325, A490, F1554_36 = "ASTM F3125 Gr. A325", "ASTM F3125 Gr. A490", "ASTM F1554 Gr. 36"
LRFD, ASD = Method.LRFD, Method.ASD


def inch(v):
    return to_internal(v, "in", Kind.LENGTH)


def ksi(v):
    return to_internal(v, "ksi", Kind.STRESS)


def kips(force):
    return from_internal(force, Kind.FORCE, "kip")


def bolt(d_in, grade=A325, threads=Threads.INCLUDED, hole=HoleType.STANDARD):
    return BoltSpec(diameter=inch(d_in), grade=grade, threads=threads, hole=hole)


@pytest.mark.parametrize(
    ("d", "grade", "threads", "phi_rn"),
    [  # AISC Manual Table 7-1, single shear, LRFD
        (0.75, A325, Threads.INCLUDED, 17.9),
        (0.75, A325, Threads.EXCLUDED, 22.5),
        (0.75, A490, Threads.INCLUDED, 22.5),
        (0.75, A490, Threads.EXCLUDED, 27.8),
        (0.875, A325, Threads.INCLUDED, 24.3),
        (1.0, A325, Threads.INCLUDED, 31.8),
    ],
)
def test_shear_manual_table_7_1(d, grade, threads, phi_rn):
    r = bolt_shear(bolt(d, grade, threads), 0.0, LRFD)
    assert kips(r.capacity) == pytest.approx(phi_rn, rel=0.005)


def test_shear_double_plane_and_asd():
    b = bolt(0.75)
    single = bolt_shear(b, 0.0, ASD).capacity
    assert kips(single) == pytest.approx(11.9, rel=0.01)  # Table 7-1, ASD
    assert bolt_shear(b, 0.0, ASD, planes=2).capacity == pytest.approx(2 * single)


def test_tension_manual_table_7_2():
    assert kips(bolt_tension(bolt(0.75), 0.0, LRFD).capacity) == pytest.approx(29.8, rel=0.005)
    assert kips(bolt_tension(bolt(1.0, A490), 0.0, LRFD).capacity) == pytest.approx(66.6,
                                                                                     rel=0.005)


def test_shear_dg1_4_7_4():
    """DG1 Example 4.7-4: one 3/4 in. F1554 Gr. 36 rod, Rnv = 11.5 kips, phiRnv = 8.63 kips."""
    r = bolt_shear(bolt(0.75, F1554_36), to_internal(8.0, "kip", Kind.FORCE), LRFD)
    assert kips(r.steps[0].value) == pytest.approx(11.5, rel=0.01)
    assert kips(r.capacity) == pytest.approx(8.63, rel=0.01)
    assert r.status == "ok"


@pytest.mark.parametrize(("method", "shear_kips", "fnt_avail_ksi"), [(LRFD, 9.50, 26.5),
                                                                        (ASD, 5.70, 18.7)])
def test_combined_dg1_4_7_6(method, shear_kips, fnt_avail_ksi):
    """DG1 Example 4.7-6, trial 1-1/8 in. F1554 Gr. 36 rods.

    phi F'nt = 26.5 ksi (LRFD) and F'nt/Omega = 18.7 ksi (ASD).
    """
    b = bolt(1.125, F1554_36)
    r = bolt_tension_shear(b, 0.0, to_internal(shear_kips, "kip", Kind.FORCE), method)
    available_stress = from_internal(r.capacity / b.area, Kind.STRESS, "ksi")
    assert available_stress == pytest.approx(fnt_avail_ksi, rel=0.01)


def test_combined_never_exceeds_tension_strength():
    b = bolt(0.75)
    pure = bolt_tension(b, 0.0, LRFD).capacity
    assert bolt_tension_shear(b, 0.0, 0.0, LRFD).capacity == pytest.approx(pure)
    huge = bolt_tension_shear(b, 0.0, to_internal(1000, "kip", Kind.FORCE), LRFD)
    assert huge.capacity == 0.0


def test_slip_manual_table_7_3():
    b = bolt(0.75)
    tb = min_pretension(0.75)
    assert kips(bolt_slip(b, 0.0, LRFD, tb).capacity) == pytest.approx(9.49, rel=0.005)
    assert kips(bolt_slip(b, 0.0, LRFD, tb, SlipClass.B).capacity) == pytest.approx(15.8,
                                                                                      rel=0.005)
    assert kips(bolt_slip(b, 0.0, ASD, tb).capacity) == pytest.approx(6.33, rel=0.005)
    ovs = bolt(0.75, hole=HoleType.OVERSIZED)
    assert kips(bolt_slip(ovs, 0.0, LRFD, tb).capacity) == pytest.approx(8.07, rel=0.005)


def test_slip_reduced_by_tension():
    b = bolt(0.75)
    tb = min_pretension(0.75)
    full = bolt_slip(b, 0.0, LRFD, tb).capacity
    half = bolt_slip(b, 0.0, LRFD, tb, tension=0.5 * 1.13 * tb).capacity
    assert half == pytest.approx(0.5 * full)


def test_bearing_dg1_4_7_7_setting_plate():
    """DG1 Example 4.7-7: 2.4 d t Fu = 58.5 kips (1-1/2 in. rod, 1/4 in. plate, Fu = 65 ksi)."""
    r = bolt_bearing(bolt(1.5, F1554_36), inch(0.25), ksi(65), 0.0, LRFD)
    assert kips(r.steps[0].value) == pytest.approx(58.5, rel=0.005)
    assert kips(r.capacity) == pytest.approx(43.9, rel=0.005)


def test_bearing_and_tearout_dg1_4_7_6_washer():
    """DG1 Example 4.7-6: 3/8 in. washer, deformation not a design consideration."""
    b = bolt(1.5, F1554_36)
    t, fu = inch(0.375), ksi(65)
    bearing = bolt_bearing(b, t, fu, 0.0, LRFD, deformation_considered=False)
    tearout = bolt_tearout(b, t, fu, inch(1.19), 0.0, LRFD, deformation_considered=False)
    assert kips(bearing.capacity) == pytest.approx(82.5, rel=0.005)
    assert kips(tearout.capacity) == pytest.approx(32.6, rel=0.005)
    asd = bolt_tearout(b, t, fu, inch(1.19), 0.0, ASD, deformation_considered=False)
    assert kips(asd.capacity) == pytest.approx(21.8, rel=0.005)


def test_long_slot_perpendicular_factors():
    b = bolt(0.75, hole=HoleType.LONG_SLOT)
    t, fu = inch(0.5), ksi(58)
    std = bolt_bearing(bolt(0.75), t, fu, 0.0, LRFD).capacity
    slot = bolt_bearing(b, t, fu, 0.0, LRFD, slot_perpendicular=True).capacity
    assert slot == pytest.approx(std * 2.0 / 2.4)


def test_clear_distance():
    b = bolt(0.75)  # 13/16 in. standard hole
    assert from_internal(clear_distance(b, inch(1.25), to_edge=True), Kind.LENGTH, "in") == \
        pytest.approx(1.25 - 13 / 32)
    assert from_internal(clear_distance(b, inch(3.0), to_edge=False), Kind.LENGTH, "in") == \
        pytest.approx(3.0 - 13 / 16)


def test_spacing_checks():
    b = bolt(0.75)
    results = {r.id: r for r in bolt_spacing_checks(b, inch(3.0), inch(1.25), inch(0.5))}
    assert set(results) == {"bolt.min_spacing", "bolt.max_spacing", "bolt.min_edge",
                            "bolt.max_edge"}
    assert all(r.status == "ok" for r in results.values())
    assert from_internal(results["bolt.min_edge"].demand, Kind.LENGTH, "in") == pytest.approx(1.0)
    tight = {r.id: r for r in bolt_spacing_checks(b, inch(1.5), inch(0.75), inch(0.5))}
    assert tight["bolt.min_spacing"].status == "ng"
    assert tight["bolt.min_edge"].status == "ng"
