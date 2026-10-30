# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Configurable unit system.

All engineering values inside OpenConex are plain ``float`` in a single
coherent internal system: **N, mm, MPa (N/mm²)**. Conversion happens only at
the boundaries (user input, reports, drawings, imports) through this module.

Each physical *kind* of quantity (length, thickness, force, moment, stress…)
has its own display unit, so a user can work e.g. with lengths in m,
thicknesses in mm, forces in tf and stresses in kgf/cm².
"""

from __future__ import annotations

import re
import tokenize
from enum import StrEnum
from fractions import Fraction

import pint
from pydantic import BaseModel, ConfigDict, field_validator

__all__ = [
    "PRESETS",
    "Kind",
    "UnitError",
    "UnitSystem",
    "format_value",
    "from_internal",
    "parse",
    "to_internal",
    "ureg",
]

ureg = pint.UnitRegistry()
ureg.define("tf = metric_ton_force")
ureg.define("ksf = kip / foot ** 2")
ureg.define("psf = lbf / foot ** 2")


class UnitError(ValueError):
    """Raised for unknown units or a unit that does not match the expected kind."""


class Kind(StrEnum):
    """Physical kind of a quantity; each one has its own display unit."""

    LENGTH = "length"
    THICKNESS = "thickness"
    FORCE = "force"
    MOMENT = "moment"
    STRESS = "stress"
    AREA = "area"
    FORCE_PER_LENGTH = "force_per_length"
    SECTION_MODULUS = "section_modulus"
    MOMENT_OF_INERTIA = "moment_of_inertia"
    DIMENSIONLESS = "dimensionless"


# Internal unit for each kind (coherent N–mm–MPa system).
INTERNAL_UNITS: dict[Kind, str] = {
    Kind.LENGTH: "mm",
    Kind.THICKNESS: "mm",
    Kind.FORCE: "N",
    Kind.MOMENT: "N*mm",
    Kind.STRESS: "MPa",
    Kind.AREA: "mm**2",
    Kind.FORCE_PER_LENGTH: "N/mm",
    Kind.SECTION_MODULUS: "mm**3",
    Kind.MOMENT_OF_INERTIA: "mm**4",
    Kind.DIMENSIONLESS: "dimensionless",
}

# Units offered in the UI for each kind (any pint-compatible unit is accepted).
CHOICES: dict[Kind, tuple[str, ...]] = {
    Kind.LENGTH: ("mm", "cm", "m", "in", "ft"),
    Kind.THICKNESS: ("mm", "in"),
    Kind.FORCE: ("N", "kN", "kgf", "tf", "lbf", "kip"),
    Kind.MOMENT: ("N*mm", "kN*m", "kgf*m", "tf*m", "lbf*in", "kip*in", "kip*ft"),
    Kind.STRESS: ("MPa", "kPa", "kgf/cm**2", "tf/m**2", "psi", "ksi", "ksf"),
    Kind.AREA: ("mm**2", "cm**2", "m**2", "in**2"),
    Kind.FORCE_PER_LENGTH: ("N/mm", "kN/m", "kgf/cm", "tf/m", "kip/in", "kip/ft"),
    Kind.SECTION_MODULUS: ("mm**3", "cm**3", "in**3"),
    Kind.MOMENT_OF_INERTIA: ("mm**4", "cm**4", "in**4"),
    Kind.DIMENSIONLESS: ("dimensionless",),
}


def _unit(text: str) -> pint.Unit:
    try:
        return ureg.Unit(text)
    except (pint.UndefinedUnitError, AttributeError, TypeError, ValueError,
            tokenize.TokenError) as exc:
        raise UnitError(f"unknown unit: {text!r}") from exc


def _check_kind(unit: pint.Unit, kind: Kind) -> None:
    expected = _unit(INTERNAL_UNITS[kind]).dimensionality
    if unit.dimensionality != expected:
        raise UnitError(f"unit {unit} is not a valid {kind.value} unit")


class UnitSystem(BaseModel):
    """Display/input unit for every kind of quantity."""

    model_config = ConfigDict(frozen=True)

    name: str = "custom"
    length: str = "mm"
    thickness: str = "mm"
    force: str = "kN"
    moment: str = "kN*m"
    stress: str = "MPa"
    area: str = "mm**2"
    force_per_length: str = "kN/m"
    section_modulus: str = "mm**3"
    moment_of_inertia: str = "mm**4"
    dimensionless: str = "dimensionless"

    @field_validator(*(k.value for k in Kind))
    @classmethod
    def _validate_unit(cls, value: str, info) -> str:
        _check_kind(_unit(value), Kind(info.field_name))
        return value

    def unit(self, kind: Kind) -> str:
        return getattr(self, kind.value)

    def with_unit(self, kind: Kind, unit: str) -> UnitSystem:
        """Return a copy with one kind changed (the system becomes 'custom')."""
        data = self.model_dump()
        data.update({kind.value: unit, "name": "custom"})
        return UnitSystem(**data)


PRESETS: dict[str, UnitSystem] = {
    "SI_kN_m": UnitSystem(name="SI_kN_m", length="m", thickness="mm", force="kN",
                          moment="kN*m", stress="MPa", area="mm**2",
                          force_per_length="kN/m", section_modulus="mm**3",
                          moment_of_inertia="mm**4"),
    "SI_N_mm": UnitSystem(name="SI_N_mm", length="mm", thickness="mm", force="N",
                          moment="N*mm", stress="MPa", area="mm**2",
                          force_per_length="N/mm", section_modulus="mm**3",
                          moment_of_inertia="mm**4"),
    "MKS": UnitSystem(name="MKS", length="m", thickness="mm", force="tf",
                      moment="tf*m", stress="kgf/cm**2", area="cm**2",
                      force_per_length="tf/m", section_modulus="cm**3",
                      moment_of_inertia="cm**4"),
    "US": UnitSystem(name="US", length="in", thickness="in", force="kip",
                     moment="kip*ft", stress="ksi", area="in**2",
                     force_per_length="kip/in", section_modulus="in**3",
                     moment_of_inertia="in**4"),
}


def _factor(unit: str, kind: Kind) -> float:
    """Multiplier from ``unit`` to the internal unit of ``kind``."""
    u = _unit(unit)
    _check_kind(u, kind)
    return float(ureg.Quantity(1.0, u).to(INTERNAL_UNITS[kind]).magnitude)


def to_internal(value: float, unit: str, kind: Kind) -> float:
    """Convert ``value`` expressed in ``unit`` to the internal unit of ``kind``."""
    return value * _factor(unit, kind)


def from_internal(value: float, kind: Kind, unit: str | UnitSystem) -> float:
    """Convert an internal ``value`` of ``kind`` to ``unit`` (or the system's unit)."""
    target = unit.unit(kind) if isinstance(unit, UnitSystem) else unit
    return value / _factor(target, kind)


# Mixed fraction ("1-1/2", "1 1/2"), simple fraction ("3/4") or decimal, then a unit.
_NUMBER = re.compile(
    r"""^\s*(?P<num>[+-]?\d+(?:\s+|-)\d+/\d+
         |[+-]?\d+/\d+
         |[+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+)(?:[eE][+-]?\d+)?)
         \s*(?P<unit>.*?)\s*$""",
    re.VERBOSE,
)
_UNIT_ALIASES = {'"': "in", "''": "in", "'": "ft", "″": "in", "′": "ft", "#": "lbf"}


def _parse_number(text: str) -> float:
    text = text.replace(",", ".")
    parts = re.split(r"\s+|(?<=\d)-(?=\d+/\d+$)", text.strip())
    if len(parts) == 2:  # mixed fraction
        whole = Fraction(parts[0])
        frac = Fraction(parts[1])
        return float(whole - frac if whole < 0 else whole + frac)
    return float(Fraction(parts[0]))


def parse(text: str, kind: Kind, default: str | UnitSystem | None = None) -> float:
    """Parse user input such as ``"25 mm"``, ``'3/4"'`` or ``"1-1/2 in"``.

    Returns the value in the internal unit of ``kind``. A bare number is
    interpreted in ``default`` (a unit or a :class:`UnitSystem`).
    """
    match = _NUMBER.match(text)
    if not match:
        raise UnitError(f"cannot parse quantity: {text!r}")
    value = _parse_number(match["num"])
    unit = match["unit"]
    unit = _UNIT_ALIASES.get(unit, unit)
    if not unit:
        if default is None:
            raise UnitError(f"no unit given in {text!r}")
        unit = default.unit(kind) if isinstance(default, UnitSystem) else default
    return to_internal(value, unit, kind)


def format_value(value: float, kind: Kind, system: UnitSystem, precision: int = 3) -> str:
    """Format an internal value in the system's unit, e.g. ``'12.5 kN'``."""
    unit = system.unit(kind)
    shown = from_internal(value, kind, unit)
    label = f"{_unit(unit):~P}" if kind is not Kind.DIMENSIONLESS else ""
    return f"{shown:.{precision}g} {label}".strip()
