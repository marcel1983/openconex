# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
import math
from fractions import Fraction as Fr

import pytest
from pydantic import ValidationError

from openconex.core.bolting import (
    HoleType,
    base_plate_hole,
    bolt_area,
    hole_size,
    min_edge_distance,
    min_pretension,
    min_spacing,
)
from openconex.core.model import (
    BoltGroup,
    BoltSpec,
    FilletWeld,
    HSSKind,
    HSSShape,
    IShape,
    SteelPlate,
    Threads,
)
from openconex.units import Kind, from_internal, to_internal


def _in(mm: float) -> float:
    return from_internal(mm, Kind.LENGTH, "in")


@pytest.mark.parametrize(
    ("d", "hole", "width", "length"),
    [
        (Fr(3, 4), HoleType.STANDARD, 13 / 16, 13 / 16),
        (Fr(7, 8), HoleType.OVERSIZED, 17 / 16, 17 / 16),
        (Fr(1), HoleType.SHORT_SLOT, 9 / 8, 21 / 16),
        (Fr(5, 8), HoleType.LONG_SLOT, 11 / 16, 25 / 16),
        (Fr(5, 4), HoleType.STANDARD, 11 / 8, 11 / 8),  # d + 1/8
        (Fr(5, 4), HoleType.OVERSIZED, 25 / 16, 25 / 16),  # d + 5/16
        (Fr(3, 2), HoleType.LONG_SLOT, 13 / 8, 15 / 4),  # (d + 1/8) x 2.5d
    ],
)
def test_hole_size_table_j3_3(d, hole, width, length):
    w, ln = hole_size(d, hole)
    assert _in(w) == pytest.approx(width)
    assert _in(ln) == pytest.approx(length)


def test_hole_size_accepts_float_diameter():
    assert hole_size(0.75) == hole_size(Fr(3, 4))


@pytest.mark.parametrize(("d", "edge"), [(0.75, 1.0), (1.0, 1.25), (1.25, 1.625), (1.5, 1.875)])
def test_min_edge_distance_table_j3_4(d, edge):
    assert _in(min_edge_distance(d)) == pytest.approx(edge)


@pytest.mark.parametrize(("d", "group", "kips"), [(0.75, 120, 28), (1.0, 150, 64), (1.5, 120, 118)])
def test_min_pretension_table_j3_1(d, group, kips):
    assert from_internal(min_pretension(d, group), Kind.FORCE, "kip") == pytest.approx(kips)


def test_area_and_spacing():
    d = to_internal(0.75, "in", Kind.LENGTH)
    assert from_internal(bolt_area(d), Kind.AREA, "in**2") == pytest.approx(0.4418, abs=1e-4)
    assert _in(min_spacing(d)) == pytest.approx(2.0)


def test_unknown_sizes_raise():
    with pytest.raises(ValueError):
        hole_size(Fr(3, 8))
    with pytest.raises(ValueError):
        min_pretension(2.0)


def test_bolt_spec():
    bolt = BoltSpec(diameter=to_internal(0.875, "in", Kind.LENGTH), threads=Threads.EXCLUDED)
    assert from_internal(bolt.Fnv, Kind.STRESS, "ksi") == pytest.approx(68)
    assert _in(bolt.hole_dimensions[0]) == pytest.approx(15 / 16)
    with pytest.raises(ValidationError):
        BoltSpec(diameter=20, grade="ASTM X999")


def test_bolt_group_coordinates_are_centered():
    group = BoltGroup(bolt=BoltSpec(diameter=19.05), rows=3, columns=2, pitch=76.2, gage=140)
    coords = group.coordinates()
    assert group.count == len(coords) == 6
    assert sum(x for x, _ in coords) == pytest.approx(0)
    assert sum(y for _, y in coords) == pytest.approx(0)
    assert max(y for _, y in coords) == pytest.approx(76.2)
    with pytest.raises(ValidationError):
        BoltGroup(bolt=group.bolt, rows=2)


def test_parts_validate():
    assert SteelPlate(width=300, length=400, thickness=25).material.name == "ASTM A36"
    assert FilletWeld(size=8, length=200).throat == pytest.approx(5.657, abs=1e-3)
    w = IShape(name="W14X90", d=356, bf=368, tf=18.0, tw=11.2)
    assert w.area == pytest.approx(2 * 368 * 18 + (356 - 36) * 11.2)
    with pytest.raises(ValidationError):
        IShape(name="bad", d=20, bf=100, tf=12, tw=5)
    with pytest.raises(ValidationError):
        SteelPlate(width=300, length=400, thickness=25, extra=1)


@pytest.mark.parametrize(
    ("d", "hole", "washer", "t_min"),
    [  # AISC Manual 16th ed., Table 14-2
        (Fr(3, 4), 21 / 16, 2.0, 1 / 4),
        (Fr(7, 8), 25 / 16, 2.5, 5 / 16),
        (Fr(1), 15 / 8, 3.0, 3 / 8),
        (Fr(5, 4), 17 / 8, 3.5, 1 / 2),
        (Fr(3, 2), 19 / 8, 4.0, 1 / 2),
        (Fr(7, 4), 23 / 8, 4.5, 5 / 8),
        (Fr(2), 13 / 4, 5.0, 3 / 4),
        (Fr(5, 2), 15 / 4, 5.5, 7 / 8),
    ],
)
def test_base_plate_holes_table_14_2(d, hole, washer, t_min):
    values = [_in(v) for v in base_plate_hole(d)]
    assert values == pytest.approx([hole, washer, t_min])


def test_base_plate_hole_outside_table():
    with pytest.raises(ValueError, match="14-2"):
        base_plate_hole(Fr(5, 8))


def test_hss_shapes():
    rect = HSSShape(name="HSS 12x8x1/2", d=304.8, width=203.2, t=12.7)
    assert rect.kind is HSSKind.RECTANGULAR
    assert rect.bf == pytest.approx(203.2)
    assert rect.tf == rect.tw == pytest.approx(12.7)
    assert rect.area == pytest.approx(2 * 12.7 * (304.8 + 203.2) - 4 * 12.7**2)
    assert rect.grade == "ASTM A500 Gr. C (rectangular)"
    square = HSSShape(name="HSS 12x12x1/2", kind=HSSKind.SQUARE, d=304.8, t=12.7)
    assert square.bf == pytest.approx(304.8)
    round_ = HSSShape(name="HSS 12x1/2", kind=HSSKind.ROUND, d=304.8, t=12.7)
    assert round_.bf == pytest.approx(304.8)
    assert round_.grade == "ASTM A500 Gr. C (round)"
    assert round_.area == pytest.approx(math.pi / 4 * (304.8**2 - (304.8 - 25.4) ** 2))
    with pytest.raises(ValidationError):
        HSSShape(name="bad", kind=HSSKind.ROUND, d=300, width=200, t=10)
    with pytest.raises(ValidationError):
        HSSShape(name="bad", d=300, t=10)  # rectangular needs width
    with pytest.raises(ValidationError):
        HSSShape(name="bad", kind=HSSKind.SQUARE, d=300, width=200, t=10)
    with pytest.raises(ValidationError):
        HSSShape(name="bad", kind=HSSKind.ROUND, d=300, t=160)
    with pytest.raises(ValidationError):
        HSSShape(name="bad", d=300, width=200, t=10, grade="ASTM X999")
