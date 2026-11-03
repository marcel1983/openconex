# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Coped beam ends against AISC Design Examples II.A-4, II.A-6 and II.A-7 (v16.1)."""

import pytest

from openconex.connections.shear.coped_beam import CopedBeam, check_coped_beam, tee_properties
from openconex.core.loads import Method
from openconex.units import Kind, from_internal, to_internal


def inch(v):
    return to_internal(v, "in", Kind.LENGTH)


def kip(v):
    return to_internal(v, "kip", Kind.FORCE)


def ksi(v):
    return to_internal(v, "ksi", Kind.STRESS)


def beam(d, tw, bf, tf, **kw):
    return CopedBeam(d=inch(d), tw=inch(tw), bf=inch(bf), tf=inch(tf), Fy=ksi(50), Fu=ksi(65),
                     **kw)


# II.A-6 A: W21x62, 8 in. deep by 9 in. long top cope, welded connection
W21X62 = beam(21.0, 0.400, 8.24, 0.615, c=inch(9), dc=inch(8))
# II.A-6 B: W21x73, same cope
W21X73 = beam(21.2, 0.455, 8.30, 0.740, c=inch(9), dc=inch(8))
# II.A-4: W18x50, 2 in. by 4 in. top cope, three 3/4 in. bolts at 3 in., lev = 1-1/4 in.,
# leh = 1-5/8 in. (1/4 in. underrun)
W18X50 = beam(18.0, 0.355, 7.50, 0.570, c=inch(4), dc=inch(2), rows=3, spacing=inch(3),
              lev=inch(1.25), leh=inch(1.625), hole=inch(0.875))
# II.A-7: W16x40, 3-1/2 in. top and 2 in. bottom copes, 9-1/2 in. long
W16X40 = beam(16.0, 0.305, 7.00, 0.505, c=inch(9.5), dc=inch(3.5), dc_bottom=inch(2))

CASES = [  # (beam, {check: (LRFD, ASD)})
    (W21X62, {"flexure": (116, 77.2), "shear_yielding": (156, 104),
              "shear_rupture": (152, 102)}),
    (W21X73, {"flexure": (150, 100), "shear_yielding": (180, 120),
              "shear_rupture": (176, 117)}),
    (W18X50, {"flexure": (374, 249), "shear_yielding": (170, 113),
              "block_shear": (68.6, 45.8)}),
    (W16X40, {"flexure": (37.9, 25.2)}),
]


@pytest.mark.parametrize(("cb", "expected"), CASES)
@pytest.mark.parametrize(("method", "col"), [(Method.LRFD, 0), (Method.ASD, 1)])
def test_design_examples(cb, expected, method, col):
    results = {r.id: r for r in check_coped_beam(cb, kip(10), method)}
    for key, values in expected.items():
        got = results[f"coped_beam.{key}"].capacity
        assert got == pytest.approx(kip(values[col]), rel=0.01), key


@pytest.mark.parametrize(("cb", "S", "Z"), [(W21X62, 17.8, 32.2), (W18X50, 23.4, 42.5)])
def test_tee_properties_match_table_9_2(cb, S, Z):
    s, z = tee_properties(cb)
    assert from_internal(s, Kind.SECTION_MODULUS, "in**3") == pytest.approx(S, rel=0.01)
    assert from_internal(z, Kind.SECTION_MODULUS, "in**3") == pytest.approx(Z, rel=0.01)
