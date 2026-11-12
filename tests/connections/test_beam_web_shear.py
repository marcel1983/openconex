# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Shear yielding of the uncoped beam web (AISC II.A-1B and II.A-17B, W18x50: 192/128 kips)."""

import pytest

from openconex.connections.shear.check import (
    ShearConnection,
    ShearType,
    beam_web_shear,
    check_shear_connection,
)
from openconex.core.loads import Forces, Method
from openconex.core.shapes import aisc_shapes
from openconex.units import Kind, from_internal, to_internal

W18X50 = aisc_shapes().get("W18X50").to_ishape("ASTM A992")


def kip(value):
    return to_internal(value, "kip", Kind.FORCE)


@pytest.mark.parametrize(("method", "expected"), [(Method.LRFD, 192), (Method.ASD, 128)])
def test_published_web_shear(method, expected):
    check = beam_web_shear(W18X50, kip(75), method)
    assert from_internal(check.capacity, Kind.FORCE, "kip") == pytest.approx(expected,
                                                                            rel=0.01)
    assert check.id == "shear_connection.beam_shear_yielding"


def test_added_by_the_dispatcher_once_and_only_without_cope():
    from tests.connections.test_single_plate import EX
    conn = ShearConnection(type=ShearType.SINGLE_PLATE, element=EX, beam=W18X50)
    ids = [r.id for r in check_shear_connection(conn, Forces(V2=kip(50)), Method.LRFD)]
    assert ids.count("shear_connection.beam_shear_yielding") == 1
    no_beam = ShearConnection(type=ShearType.SINGLE_PLATE, element=EX)
    ids = [r.id for r in check_shear_connection(no_beam, Forces(V2=kip(50)), Method.LRFD)]
    assert "shear_connection.beam_shear_yielding" not in ids
