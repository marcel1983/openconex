# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Quantity helpers shared by the desktop interface."""

from __future__ import annotations

from openconex.io.project import HSSSectionInput, Project, WSectionInput
from openconex.units import Kind, UnitSystem, from_internal, parse

__all__ = [
    "convert_project",
    "convert_section",
    "convert_text",
    "format_quantity",
    "stored_quantity",
    "unit_label",
]

PRECISION = 8


def unit_label(system: UnitSystem, kind: Kind) -> str:
    """A short, readable unit label for form fields (``kip·ft``, ``mm²``…)."""
    text = system.unit(kind)
    return (text.replace("**4", "⁴").replace("**3", "³")
            .replace("**2", "²").replace("*", "·"))


def format_quantity(value: float, kind: Kind, system: UnitSystem,
                    precision: int = PRECISION) -> str:
    """An internal value as a bare number in ``system``."""
    return f"{from_internal(value, kind, system):.{precision}g}"


def convert_text(text: str, kind: Kind, old: UnitSystem, new: UnitSystem,
                 precision: int = PRECISION) -> str:
    """Convert a form value from one unit system to another."""
    return format_quantity(parse(text, kind, old), kind, new, precision)


def stored_quantity(text: str, kind: Kind, system: UnitSystem) -> str:
    """A value with its explicit unit, to keep in the project file."""
    value = parse(text, kind, system)
    return f"{format_quantity(value, kind, system)} {system.unit(kind)}"


def convert_section(section: WSectionInput | HSSSectionInput,
                    old: UnitSystem, new: UnitSystem) -> WSectionInput | HSSSectionInput:
    """Convert the dimensions of a generic section, preserving its name."""
    if isinstance(section, WSectionInput):
        return section.model_copy(update={
            field: convert_text(str(getattr(section, field)), kind, old, new)
            for field, kind in (("d", Kind.LENGTH), ("bf", Kind.LENGTH),
                                ("tf", Kind.THICKNESS), ("tw", Kind.THICKNESS),
                                ("k_des", Kind.LENGTH))
        })
    update = {
        "d": convert_text(str(section.d), Kind.LENGTH, old, new),
        "t": convert_text(str(section.t), Kind.THICKNESS, old, new),
    }
    if section.bf is not None:
        update["bf"] = convert_text(str(section.bf), Kind.LENGTH, old, new)
    return section.model_copy(update=update)


def _convert_field(model: object, field: str, kind: Kind,
                   old: UnitSystem, new: UnitSystem) -> None:
    value = getattr(model, field)
    if value is not None:
        setattr(model, field, convert_text(str(value), kind, old, new))


def _convert_optional_layer(layer: object | None, old: UnitSystem,
                            new: UnitSystem) -> None:
    if layer is None:
        return
    _convert_field(layer, "area", Kind.AREA, old, new)
    _convert_field(layer, "fy", Kind.STRESS, old, new)
    _convert_field(layer, "depth", Kind.LENGTH, old, new)


def convert_project(project: Project, old: UnitSystem, new: UnitSystem) -> Project:
    """Return a copy of ``project`` with every stored quantity in ``new`` units.

    The project file may keep bare numbers (interpreted in ``info.units``), so
    changing the system converts them all, including the blocks that the
    current form does not edit yet.
    """
    data = project.model_copy(deep=True)
    for material in data.materials:
        for field in ("Fy", "Fu", "E"):
            value = parse(str(getattr(material, field)), Kind.STRESS, old)
            setattr(material, field, f"{format_quantity(value, Kind.STRESS, new)} "
                                     f"{new.unit(Kind.STRESS)}")

    data.sections = [convert_section(section, old, new) for section in data.sections]
    bp = data.base_plate
    if not isinstance(bp.column, str):
        bp.column = convert_section(bp.column, old, new)

    for field, kind in (
            ("N", Kind.LENGTH), ("B", Kind.LENGTH), ("tp", Kind.THICKNESS),
            ("rod_bending_lever", Kind.LENGTH), ("fc", Kind.STRESS),
            ("bearing_area", Kind.AREA), ("pedestal_N", Kind.LENGTH),
            ("pedestal_B", Kind.LENGTH), ("grout", Kind.LENGTH),
            ("rod_diameter", Kind.LENGTH), ("f", Kind.LENGTH),
            ("rod_spacing", Kind.LENGTH), ("hef", Kind.LENGTH),
            ("washer_thickness", Kind.THICKNESS), ("flange_weld", Kind.THICKNESS)):
        _convert_field(bp, field, kind, old, new)
    for key in bp.edges:
        bp.edges[key] = convert_text(str(bp.edges[key]), Kind.LENGTH, old, new)
    for bar in bp.pedestal_rebars:
        for field in ("x", "y", "diameter"):
            _convert_field(bar, field, Kind.LENGTH, old, new)
    if bp.reinforcement is not None:
        for field, kind in (
                ("area", Kind.AREA), ("fy", Kind.STRESS), ("db", Kind.LENGTH),
                ("clear_cover", Kind.LENGTH), ("anchor_to_bar", Kind.LENGTH),
                ("le", Kind.LENGTH)):
            _convert_field(bp.reinforcement, field, kind, old, new)
    if bp.weak_base is not None:
        _convert_field(bp.weak_base, "reduced_diameter", Kind.LENGTH, old, new)
        _convert_field(bp.weak_base, "stretch_length", Kind.LENGTH, old, new)
    if bp.embedded_base is not None:
        embedded = bp.embedded_base
        for field, kind in (
                ("embedment", Kind.LENGTH), ("foundation_width", Kind.LENGTH),
                ("face_plate_thickness", Kind.THICKNESS),
                ("base_plate_width", Kind.LENGTH),
                ("base_plate_thickness", Kind.THICKNESS)):
            _convert_field(embedded, field, kind, old, new)
        _convert_optional_layer(embedded.rebar_top, old, new)
        _convert_optional_layer(embedded.rebar_bottom, old, new)
    if bp.shear_lug is not None:
        lug = bp.shear_lug
        for field, kind in (("width", Kind.LENGTH), ("embedment", Kind.LENGTH),
                            ("thickness", Kind.THICKNESS), ("weld", Kind.THICKNESS),
                            ("ca1", Kind.LENGTH)):
            _convert_field(lug, field, kind, old, new)
        lug.ca2 = [None if value is None else
                   convert_text(str(value), Kind.LENGTH, old, new)
                   for value in lug.ca2]

    for case in data.cases:
        for field, kind in (("P", Kind.FORCE), ("V", Kind.FORCE),
                            ("V_weak", Kind.FORCE), ("M", Kind.MOMENT),
                            ("M_weak", Kind.MOMENT)):
            _convert_field(case, field, kind, old, new)

    data.info.units = new.name
    return data
