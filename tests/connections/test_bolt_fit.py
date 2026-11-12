# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Bolt-fit validation: holes must stay inside the connected element.

These tests cover the error that stopped a double angle with four rows drawn in
an 8.5 in angle: the last bolt fell outside the angle.  The same rule applies
to every shear connection whose bolt rows are defined by length, rows, spacing
and edge distance.
"""

import dataclasses
import json
from pathlib import Path

import pytest

from openconex.connections.shear.bent_plate import SkewedBentPlate
from openconex.connections.shear.check import (
    check_shear_connection,
    validate_shear_connection,
)
from openconex.core.loads import Forces, Method
from openconex.gui.start_data import FAMILIES, build_project
from openconex.io.project import Project
from openconex.report.shear import build_shear_report
from openconex.units import Kind, to_internal

EXAMPLES = Path(__file__).parents[2] / "examples"


def inch(value: float) -> float:
    return to_internal(value, "in", Kind.LENGTH)


def kip(value: float) -> float:
    return to_internal(value, "kip", Kind.FORCE)


def model(family: str, subtype: str):
    return build_project(family, subtype).shear_model()


@pytest.mark.parametrize(
    "family",
    [family for family in FAMILIES if family.enabled and family.id != "base_plate"],
    ids=lambda family: family.id,
)
def test_starter_projects_have_valid_bolt_groups(family):
    for subtype in family.subtypes:
        validate_shear_connection(model(family.id, subtype.id))


@pytest.mark.parametrize("subtype", [
    "double_angle", "single_plate", "extended_single_plate", "end_plate",
    "skewed_bent_plate",
])
def test_bolt_group_outside_element_is_rejected(subtype):
    conn = model("shear_column", subtype)
    element = conn.element
    if isinstance(element, SkewedBentPlate):
        plate = dataclasses.replace(element.plate_a, rows=element.plate_a.rows + 1)
        element = dataclasses.replace(element, plate_a=plate)
    else:
        element = dataclasses.replace(element, rows=element.rows + 1)
    with pytest.raises(ValueError, match="no caben"):
        validate_shear_connection(dataclasses.replace(conn, element=element))


@pytest.mark.parametrize("subtype", [
    "double_angle", "single_plate", "extended_single_plate", "end_plate",
])
def test_vertical_edge_below_table_j34_is_rejected(subtype):
    conn = model("shear_column", subtype)
    element = dataclasses.replace(conn.element, lev=inch(0.75))
    with pytest.raises(ValueError, match=r"Tabla J3\.4"):
        validate_shear_connection(dataclasses.replace(conn, element=element))


@pytest.mark.parametrize(("subtype", "field"), [
    ("double_angle", "leh_beam"),
    ("single_plate", "leh"),
    ("extended_single_plate", "leh"),
    ("end_plate", "leh"),
])
def test_horizontal_edge_below_table_j34_is_rejected(subtype, field):
    conn = model("shear_column", subtype)
    element = dataclasses.replace(conn.element, **{field: inch(0.75)})
    with pytest.raises(ValueError, match=r"Tabla J3\.4"):
        validate_shear_connection(dataclasses.replace(conn, element=element))


def test_spacing_below_j33_is_rejected():
    conn = model("shear_column", "double_angle")
    element = dataclasses.replace(conn.element, spacing=inch(1.0))
    with pytest.raises(ValueError, match="separación mínima"):
        validate_shear_connection(dataclasses.replace(conn, element=element))


def test_invalid_geometry_stops_the_calculation():
    conn = model("shear_column", "double_angle")
    element = dataclasses.replace(conn.element, rows=4)
    conn = dataclasses.replace(conn, element=element)
    with pytest.raises(ValueError, match="no caben"):
        check_shear_connection(conn, Forces(V2=kip(10)), Method.LRFD)


def test_report_rejects_the_invalid_double_angle():
    data = json.loads((EXAMPLES / "shear_double_angle_coped.ocnx").read_text(
        encoding="utf-8"))
    data["shear_connection"]["rows"] = 4
    with pytest.raises(ValueError, match="no caben"):
        build_shear_report(Project.model_validate(data))
