# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from openconex.units import (
    CHOICES,
    PRESETS,
    Kind,
    UnitError,
    UnitSystem,
    format_value,
    from_internal,
    parse,
    to_internal,
)


@pytest.mark.parametrize(
    ("value", "unit", "kind", "expected"),
    [
        (1.0, "in", Kind.LENGTH, 25.4),
        (1.0, "ft", Kind.LENGTH, 304.8),
        (1.0, "kN", Kind.FORCE, 1000.0),
        (1.0, "kip", Kind.FORCE, 4448.2216152605),
        (1.0, "kgf", Kind.FORCE, 9.80665),
        (1.0, "tf", Kind.FORCE, 9806.65),
        (1.0, "ksi", Kind.STRESS, 6.894757293168),
        (1.0, "kgf/cm**2", Kind.STRESS, 0.0980665),
        (1.0, "ksf", Kind.STRESS, 0.04788025898),
        (1.0, "kN*m", Kind.MOMENT, 1.0e6),
        (1.0, "kip*ft", Kind.MOMENT, 1355817.948),
        (1.0, "in**2", Kind.AREA, 645.16),
        (1.0, "kip/in", Kind.FORCE_PER_LENGTH, 175.1268352),
    ],
)
def test_to_internal(value, unit, kind, expected):
    assert to_internal(value, unit, kind) == pytest.approx(expected, rel=1e-9)


@pytest.mark.parametrize(
    ("text", "kind", "expected_mm_or_n"),
    [
        ("25 mm", Kind.LENGTH, 25.0),
        ("25mm", Kind.LENGTH, 25.0),
        ("2,5 cm", Kind.LENGTH, 25.0),
        ("3/4 in", Kind.THICKNESS, 19.05),
        ('3/4"', Kind.THICKNESS, 19.05),
        ("1-1/2 in", Kind.LENGTH, 38.1),
        ("1 1/2 in", Kind.LENGTH, 38.1),
        ("-1-1/2 in", Kind.LENGTH, -38.1),
        ("2'", Kind.LENGTH, 609.6),
        ("1e3 N", Kind.FORCE, 1000.0),
        ("10 kip", Kind.FORCE, 44482.216152605),
        ("4 ksi", Kind.STRESS, 27.579029172673),
    ],
)
def test_parse(text, kind, expected_mm_or_n):
    assert parse(text, kind) == pytest.approx(expected_mm_or_n, rel=1e-9)


def test_parse_bare_number_uses_default():
    assert parse("2", Kind.LENGTH, PRESETS["SI_kN_m"]) == pytest.approx(2000.0)
    assert parse("2", Kind.LENGTH, "in") == pytest.approx(50.8)
    with pytest.raises(UnitError):
        parse("2", Kind.LENGTH)


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("25 kN", Kind.LENGTH),
        ("3 mm", Kind.STRESS),
        ("abc", Kind.LENGTH),
        ("5 furlongz", Kind.LENGTH),
    ],
)
def test_parse_rejects_wrong_or_unknown_units(text, kind):
    with pytest.raises(UnitError):
        parse(text, kind)


def test_unit_system_validates_kind():
    with pytest.raises(ValueError):
        UnitSystem(force="mm")
    custom = PRESETS["SI_kN_m"].with_unit(Kind.STRESS, "kgf/cm**2")
    assert custom.stress == "kgf/cm**2"
    assert custom.force == "kN"
    assert custom.name == "custom"


def test_every_offered_unit_is_valid():
    for kind, units in CHOICES.items():
        for unit in units:
            assert math.isfinite(to_internal(1.0, unit, kind))


def test_format_value():
    assert format_value(12500.0, Kind.FORCE, PRESETS["SI_kN_m"]) == "12.5 kN"
    assert format_value(25.4, Kind.THICKNESS, PRESETS["US"]) == "1 in"


@given(
    value=st.floats(min_value=-1e9, max_value=1e9, allow_nan=False),
    kind=st.sampled_from([k for k in Kind if k is not Kind.DIMENSIONLESS]),
    data=st.data(),
)
def test_round_trip(value, kind, data):
    unit = data.draw(st.sampled_from(CHOICES[kind]))
    back = from_internal(to_internal(value, unit, kind), kind, unit)
    assert back == pytest.approx(value, rel=1e-12, abs=1e-9)


@given(
    fy_ksi=st.floats(min_value=30, max_value=120),
    area_in2=st.floats(min_value=0.1, max_value=100),
    load_kip=st.floats(min_value=0.0, max_value=5000),
    system=st.sampled_from(list(PRESETS.values())),
)
def test_ratio_is_unit_invariant(fy_ksi, area_in2, load_kip, system):
    """A check ratio must not depend on the unit system the user works in."""
    reference = load_kip / (0.9 * fy_ksi * area_in2)

    def in_system(v, unit, kind):
        # value as the user would type it in the chosen system, then back to internal
        shown = from_internal(to_internal(v, unit, kind), kind, system)
        return to_internal(shown, system.unit(kind), kind)

    fy = in_system(fy_ksi, "ksi", Kind.STRESS)
    area = in_system(area_in2, "in**2", Kind.AREA)
    load = in_system(load_kip, "kip", Kind.FORCE)
    assert load / (0.9 * fy * area) == pytest.approx(reference, rel=1e-12)
