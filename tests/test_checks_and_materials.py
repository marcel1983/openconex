# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
import pytest

from openconex.core.checks import CheckResult, Status, TraceStep, governing
from openconex.core.materials import BOLTS, ELECTRODES, STEELS
from openconex.units import Kind, from_internal


def _check(demand, capacity, **kw):
    return CheckResult(id="t", text_id="check.t", clause="X", demand=demand,
                       capacity=capacity, kind=Kind.FORCE, **kw)


def test_ratio_and_status():
    assert _check(50.0, 100.0).ratio == pytest.approx(0.5)
    assert _check(50.0, 100.0).status is Status.OK
    assert _check(-150.0, 100.0).status is Status.NG
    assert _check(1.0, 0.0).ratio == float("inf")
    assert _check(0.0, 0.0).ratio == 0.0
    assert _check(99.0, 100.0, ratio_limit=0.95).status is Status.NG
    assert _check(500.0, 100.0, applicable=False).status is Status.NOT_APPLICABLE


def test_governing_ignores_not_applicable():
    a, b, c = _check(10, 100), _check(80, 100), _check(900, 100, applicable=False)
    assert governing([a, b, c]) is b
    assert governing([]) is None


def test_result_serializes_with_trace():
    step = TraceStep(symbol=r"\phi R_n", expression=r"0.75 F_u A_e", value=1.0e5,
                     kind=Kind.FORCE, clause="AISC 360-22 Eq. J4-2")
    data = _check(5.0e4, 1.0e5, steps=(step,)).model_dump(mode="json")
    assert data["ratio"] == pytest.approx(0.5)
    assert data["status"] == "ok"
    assert data["steps"][0]["clause"] == "AISC 360-22 Eq. J4-2"


@pytest.mark.parametrize(
    ("table", "name", "attr", "ksi"),
    [
        (STEELS, "ASTM A992", "Fy", 50),
        (STEELS, "ASTM A36", "Fu", 58),
        (STEELS, "ASTM A53 Gr. B", "Fy", 35),
        (STEELS, "ASTM A572 Gr. 60", "Fu", 75),
        (STEELS, "ASTM A913 Gr. 70", "Fy", 70),
        (STEELS, "ASTM A1065 Gr. 50W", "Fu", 70),
        (STEELS, "ASTM A1085", "Fu", 65),
        (BOLTS, "ASTM F3125 Gr. A325", "Fnv_N", 54),
        (BOLTS, "ASTM F3125 Gr. A490", "Fnt", 113),
        (BOLTS, "ASTM F1554 Gr. 36", "Fnt", 43.5),
        (BOLTS, "ASTM F1554 Gr. 55", "Fy", 55),
        (ELECTRODES, "E70XX", "FEXX", 70),
    ],
)
def test_material_values(table, name, attr, ksi):
    value = getattr(table[name], attr)
    assert from_internal(value, Kind.STRESS, "ksi") == pytest.approx(ksi)


def test_steel_library_is_consistent():
    assert len(STEELS) >= 25
    assert all(g.Fy > 0 and g.Fu >= g.Fy and g.E > 0 for g in STEELS.values())
