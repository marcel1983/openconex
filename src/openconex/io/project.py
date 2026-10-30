# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""OpenConex project files (``.ocnx``, JSON).

Quantities are written as text with their unit (``"22 in"``, ``"700 kip"``,
``"3 ksi"``); a bare number uses the project unit system. The file keeps what
the user typed, so it stays readable and unit-agnostic.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from openconex import __version__
from openconex.connections.base_plate.check import BasePlate
from openconex.core.loads import (
    Forces,
    LoadCase,
    LoadCombination,
    LoadType,
    Method,
    SeismicParameters,
    asce7_combinations,
)
from openconex.core.model import BoltSpec
from openconex.core.shapes import aisc_shapes
from openconex.kernel.anchors import Edges
from openconex.units import PRESETS, Kind, UnitSystem, parse

__all__ = [
    "FORMAT_VERSION",
    "BasePlateInput",
    "LoadCaseInput",
    "Project",
    "ProjectInfo",
    "load_project",
    "save_project",
]

FORMAT_VERSION = 1
Quantity = str | float


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectInfo(_Input):
    name: str = ""
    number: str = ""
    client: str = ""
    engineer: str = ""
    revision: str = "0"
    date: str = ""
    language: str = "es"
    units: str | UnitSystem = "SI_kN_m"

    def unit_system(self) -> UnitSystem:
        return PRESETS[self.units] if isinstance(self.units, str) else self.units


class BasePlateInput(_Input):
    column: str
    """Shape label in the AISC catalog, e.g. ``W12X96``."""
    column_grade: str = "ASTM A992"
    N: Quantity
    B: Quantity
    tp: Quantity
    plate_grade: str = "ASTM A572 Gr. 50"
    fc: Quantity
    A2_over_A1: float = 1.0
    pedestal_N: Quantity | None = None
    pedestal_B: Quantity | None = None
    grout: Quantity = "1.5 in"
    rod_diameter: Quantity
    rod_grade: str = "ASTM F1554 Gr. 36"
    rods_per_side: int = 2
    f: Quantity
    """Column axis to each anchor row."""
    rod_spacing: Quantity = 0.0
    hef: Quantity = 0.0
    edges: dict[str, Quantity] = Field(default_factory=dict)
    """Distances from the outer anchors to concrete edges: left, right, bottom, top."""
    washer_thickness: Quantity | None = None
    flange_weld: Quantity | None = None
    grout_pad: bool = True
    friction_mu: float = 0.4
    cracked: bool = True
    seismic: bool = False


class LoadCaseInput(_Input):
    name: str
    type: LoadType
    P: Quantity = 0.0
    """Axial force, compression positive."""
    V: Quantity = 0.0
    M: Quantity = 0.0


class CombinationOptions(_Input):
    methods: list[Method] = Field(default_factory=lambda: [Method.LRFD])
    live_factor: float = 1.0
    SDS: float | None = None
    rho: float = 1.0
    omega0: float | None = None


class Project(_Input):
    format_version: int = FORMAT_VERSION
    generator: str = f"OpenConex {__version__}"
    info: ProjectInfo = Field(default_factory=ProjectInfo)
    base_plate: BasePlateInput
    cases: list[LoadCaseInput]
    combinations: CombinationOptions = Field(default_factory=CombinationOptions)

    # -- conversion to the engine model ------------------------------------------------
    def quantity(self, value: Quantity, kind: Kind) -> float:
        """Value typed in the project (text with unit, or number in project units), internal."""
        units = self.info.unit_system()
        if isinstance(value, (int, float)):
            return parse(str(value), kind, units)
        return parse(value, kind, units)

    def base_plate_model(self) -> BasePlate:
        bp = self.base_plate
        L, T = Kind.LENGTH, Kind.THICKNESS
        column = aisc_shapes().get(bp.column).to_ishape(bp.column_grade)
        edges = Edges(**{k: self.quantity(v, L) for k, v in bp.edges.items()})
        return BasePlate(
            column=column, N=self.quantity(bp.N, L), B=self.quantity(bp.B, L),
            tp=self.quantity(bp.tp, T),
            fc=self.quantity(bp.fc, Kind.STRESS),
            rod=BoltSpec(diameter=self.quantity(bp.rod_diameter, L), grade=bp.rod_grade),
            f=self.quantity(bp.f, L), rods_per_side=bp.rods_per_side,
            rod_spacing=self.quantity(bp.rod_spacing, L), hef=self.quantity(bp.hef, L),
            plate_grade=bp.plate_grade, A2_over_A1=bp.A2_over_A1, edges=edges,
            washer_thickness=(None if bp.washer_thickness is None
                              else self.quantity(bp.washer_thickness, T)),
            grout_pad=bp.grout_pad,
            flange_weld=None if bp.flange_weld is None else self.quantity(bp.flange_weld, T),
            friction_mu=bp.friction_mu, cracked=bp.cracked, seismic=bp.seismic,
        )

    def case_forces(self) -> dict[str, Forces]:
        return {c.name: Forces(P=self.quantity(c.P, Kind.FORCE), V2=self.quantity(c.V, Kind.FORCE),
                               M3=self.quantity(c.M, Kind.MOMENT)) for c in self.cases}

    def load_combinations(self) -> list[LoadCombination]:
        opts = self.combinations
        cases = [LoadCase(name=c.name, type=c.type) for c in self.cases]
        seismic = (SeismicParameters(SDS=opts.SDS, rho=opts.rho, omega0=opts.omega0)
                   if opts.SDS is not None else None)
        out: list[LoadCombination] = []
        for method in opts.methods:
            out += asce7_combinations(cases, method, seismic, opts.live_factor)
        return out


def load_project(path: str | Path) -> Project:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    version = data.get("format_version", FORMAT_VERSION)
    if version > FORMAT_VERSION:
        raise ValueError(f"project format {version} is newer than this OpenConex "
                         f"({FORMAT_VERSION}); please update")
    return Project.model_validate(data)


def save_project(project: Project, path: str | Path) -> None:
    Path(path).write_text(project.model_dump_json(indent=2, exclude_defaults=False) + "\n",
                          encoding="utf-8", newline="\n")
