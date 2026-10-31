# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Connection parts shared by every connection type.

All dimensions are in internal units (mm); materials refer to the library in
:mod:`openconex.core.materials`.
"""

from __future__ import annotations

import math
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from openconex.core.bolting import HoleType, bolt_area, hole_size
from openconex.core.materials import BOLTS, ELECTRODES, STEELS, BoltGrade, SteelGrade, WeldElectrode
from openconex.units import Kind, from_internal

__all__ = [
    "BoltGroup",
    "BoltSpec",
    "ColumnShape",
    "FilletWeld",
    "HSSKind",
    "HSSShape",
    "IShape",
    "SteelPlate",
    "Threads",
]


class _Part(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Threads(StrEnum):
    INCLUDED = "N"
    """Threads included in the shear plane."""
    EXCLUDED = "X"
    """Threads excluded from the shear plane."""


class BoltSpec(_Part):
    """A bolt or anchor rod: diameter, grade, thread condition and hole type."""

    diameter: float = Field(gt=0)
    grade: str = "ASTM F3125 Gr. A325"
    threads: Threads = Threads.INCLUDED
    hole: HoleType = HoleType.STANDARD

    @model_validator(mode="after")
    def _known_grade(self) -> BoltSpec:
        if self.grade not in BOLTS:
            raise ValueError(f"unknown bolt grade: {self.grade}")
        return self

    @property
    def material(self) -> BoltGrade:
        return BOLTS[self.grade]

    @property
    def area(self) -> float:
        return bolt_area(self.diameter)

    @property
    def Fnv(self) -> float:
        g = self.material
        return g.Fnv_X if self.threads is Threads.EXCLUDED else g.Fnv_N

    @property
    def hole_dimensions(self) -> tuple[float, float]:
        """Nominal hole (width, length) [mm], AISC 360-22 Table J3.3."""
        return hole_size(from_internal(self.diameter, Kind.LENGTH, "in"), self.hole)


class BoltGroup(_Part):
    """Bolts on a rectangular grid, coordinates relative to the group centroid."""

    bolt: BoltSpec
    rows: int = Field(ge=1)
    """Number of bolts along the local y axis."""
    columns: int = Field(default=1, ge=1)
    """Number of bolts along the local x axis."""
    pitch: float = Field(default=0.0, ge=0)
    """Spacing between rows (along y) [mm]."""
    gage: float = Field(default=0.0, ge=0)
    """Spacing between columns (along x) [mm]."""

    @model_validator(mode="after")
    def _spacing_required(self) -> BoltGroup:
        if self.rows > 1 and self.pitch <= 0:
            raise ValueError("pitch is required with more than one row")
        if self.columns > 1 and self.gage <= 0:
            raise ValueError("gage is required with more than one column")
        return self

    @property
    def count(self) -> int:
        return self.rows * self.columns

    def coordinates(self) -> list[tuple[float, float]]:
        x0 = (self.columns - 1) * self.gage / 2.0
        y0 = (self.rows - 1) * self.pitch / 2.0
        return [(c * self.gage - x0, r * self.pitch - y0)
                for r in range(self.rows) for c in range(self.columns)]


class SteelPlate(_Part):
    width: float = Field(gt=0)
    length: float = Field(gt=0)
    thickness: float = Field(gt=0)
    grade: str = "ASTM A36"

    @model_validator(mode="after")
    def _known_grade(self) -> SteelPlate:
        if self.grade not in STEELS:
            raise ValueError(f"unknown steel grade: {self.grade}")
        return self

    @property
    def material(self) -> SteelGrade:
        return STEELS[self.grade]


class FilletWeld(_Part):
    size: float = Field(gt=0)
    """Leg size w [mm]."""
    length: float = Field(gt=0)
    electrode: str = "E70XX"

    @model_validator(mode="after")
    def _known_electrode(self) -> FilletWeld:
        if self.electrode not in ELECTRODES:
            raise ValueError(f"unknown electrode: {self.electrode}")
        return self

    @property
    def material(self) -> WeldElectrode:
        return ELECTRODES[self.electrode]

    @property
    def throat(self) -> float:
        """Effective throat of an equal-leg fillet weld, w/√2 [mm]."""
        return self.size / 2.0**0.5


class IShape(_Part):
    """Doubly symmetric I-shape (W, M, S, HP or built-up) by its dimensions."""

    name: str
    d: float = Field(gt=0)
    bf: float = Field(gt=0)
    tf: float = Field(gt=0)
    tw: float = Field(gt=0)
    k_des: float = Field(default=0.0, ge=0)
    """Design distance from outer face of flange to web toe of fillet [mm]."""
    grade: str = "ASTM A992"

    @model_validator(mode="after")
    def _consistent(self) -> IShape:
        if 2 * self.tf >= self.d:
            raise ValueError("flanges thicker than the section depth")
        if self.tw >= self.bf:
            raise ValueError("web thicker than the flange width")
        if self.grade not in STEELS:
            raise ValueError(f"unknown steel grade: {self.grade}")
        return self

    @property
    def material(self) -> SteelGrade:
        return STEELS[self.grade]

    @property
    def area(self) -> float:
        """Area without fillets [mm²]."""
        return 2 * self.bf * self.tf + (self.d - 2 * self.tf) * self.tw


class HSSKind(StrEnum):
    RECTANGULAR = "rectangular"
    SQUARE = "square"
    ROUND = "round"


class HSSShape(_Part):
    """Hollow structural section by outside dimensions and wall thickness.

    ``d`` is the outside depth for rectangular/square HSS or the outside
    diameter for round HSS; ``width`` is the outside width (rectangular) and
    is ignored for round sections. Corner radii are neglected in the area.
    """

    name: str
    kind: HSSKind = HSSKind.RECTANGULAR
    d: float = Field(gt=0)
    width: float | None = Field(default=None, gt=0)
    t: float = Field(gt=0)
    grade: str = "ASTM A500 Gr. C (rectangular)"

    @model_validator(mode="before")
    @classmethod
    def _default_grade(cls, data):
        """Use the A500 Gr. C grade that matches the section shape."""
        if isinstance(data, dict) and not data.get("grade"):
            kind = data.get("kind", HSSKind.RECTANGULAR)
            round_ = kind is HSSKind.ROUND or kind == HSSKind.ROUND.value
            data = {**data, "grade": ("ASTM A500 Gr. C (round)" if round_
                                      else "ASTM A500 Gr. C (rectangular)")}
        return data

    @model_validator(mode="after")
    def _consistent(self) -> HSSShape:
        if self.kind is HSSKind.ROUND:
            if self.width is not None:
                raise ValueError("a round HSS uses its diameter; width is not allowed")
            if 2 * self.t >= self.d:
                raise ValueError("HSS wall thickness is too large for the diameter")
        else:
            if self.kind is HSSKind.RECTANGULAR and self.width is None:
                raise ValueError("a rectangular HSS needs its width")
            if self.kind is HSSKind.SQUARE and self.width is not None \
                    and abs(self.width - self.d) > 1e-9:
                raise ValueError("a square HSS needs equal depth and width")
            if 2 * self.t >= min(self.d, self.bf):
                raise ValueError("HSS wall thickness is too large for the section")
        if self.grade not in STEELS:
            raise ValueError(f"unknown steel grade: {self.grade}")
        return self

    @property
    def bf(self) -> float:
        """Outside width (diameter for round HSS)."""
        if self.kind is HSSKind.ROUND:
            return self.d
        return self.width if self.width is not None else self.d

    @property
    def tf(self) -> float:
        """Wall thickness, named like an I-shape flange for shared checks."""
        return self.t

    @property
    def tw(self) -> float:
        """Wall thickness, named like an I-shape web for shared checks."""
        return self.t

    @property
    def material(self) -> SteelGrade:
        return STEELS[self.grade]

    @property
    def area(self) -> float:
        """Area of the annular wall, neglecting corner radii [mm²]."""
        if self.kind is HSSKind.ROUND:
            return math.pi / 4 * (self.d**2 - (self.d - 2 * self.t) ** 2)
        return 2 * self.t * (self.d + self.bf) - 4 * self.t**2


ColumnShape = IShape | HSSShape
