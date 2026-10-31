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
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from openconex import __version__
from openconex.connections.base_plate.check import (
    BasePlate,
    BearingAreaModel,
    PressureModel,
    ShearLug,
)
from openconex.core.loads import (
    Forces,
    LoadCase,
    LoadCombination,
    LoadType,
    Method,
    SeismicParameters,
    asce7_combinations,
)
from openconex.core.materials import STEELS, SteelGrade
from openconex.core.model import BoltSpec, HSSKind, HSSShape, IShape
from openconex.core.shapes import aisc_shapes
from openconex.kernel.anchors import Edges
from openconex.units import PRESETS, Kind, UnitSystem, parse

__all__ = [
    "FORMAT_VERSION",
    "BasePlateInput",
    "ColumnSectionInput",
    "CombinationOptions",
    "CustomCombinationInput",
    "HSSSectionInput",
    "LoadCaseInput",
    "MaterialInput",
    "Project",
    "ProjectInfo",
    "WSectionInput",
    "load_project",
    "save_project",
]

FORMAT_VERSION = 4
Quantity = str | float


def _repeated(names: list[str]) -> list[str]:
    """Names that appear more than once, sorted."""
    return sorted({name for name in names if names.count(name) > 1})


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


class MaterialInput(_Input):
    """A structural steel added to the built-in AISC library for this project."""

    name: str = Field(min_length=1)
    Fy: Quantity
    """Specified minimum yield stress."""
    Fu: Quantity
    """Specified minimum tensile strength."""
    E: Quantity = "29000 ksi"
    """Modulus of elasticity."""

    @model_validator(mode="after")
    def _nonblank_name(self) -> MaterialInput:
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("material name must not be blank")
        return self


def _dimension_text(value: Quantity) -> str:
    """Dimension as typed, for generated section labels."""
    return f"{value:g}" if isinstance(value, (int, float)) else str(value).strip()


class WSectionInput(_Input):
    """A generic doubly symmetric I-shape (W, M, S, HP or built-up) by dimensions."""

    type: Literal["W"]
    name: str = ""
    d: Quantity
    bf: Quantity
    tf: Quantity
    tw: Quantity
    k_des: Quantity = 0.0
    grade: str = Field(min_length=1)
    """Material name from the built-in library or from ``materials``."""

    def label(self) -> str:
        return self.name or "W " + "×".join(
            _dimension_text(value) for value in (self.d, self.bf, self.tf, self.tw))


class HSSSectionInput(_Input):
    """A generic rectangular, square or round hollow structural section."""

    type: Literal["HSS"]
    name: str = ""
    shape: HSSKind = HSSKind.RECTANGULAR
    d: Quantity
    """Outside depth (rectangular/square) or outside diameter (round)."""
    bf: Quantity | None = None
    """Outside width (rectangular/square); omitted for square or round sections."""
    t: Quantity
    grade: str = Field(min_length=1)
    """Material name from the built-in library or from ``materials``."""

    @model_validator(mode="after")
    def _width_required(self) -> HSSSectionInput:
        if self.shape is HSSKind.RECTANGULAR and self.bf is None:
            raise ValueError("a rectangular HSS needs its width bf")
        if self.shape is HSSKind.ROUND and self.bf is not None:
            raise ValueError("a round HSS uses its diameter; bf is not allowed")
        return self

    def label(self) -> str:
        if self.name:
            return self.name
        if self.shape is HSSKind.ROUND:
            return f"HSS Ø{_dimension_text(self.d)}×{_dimension_text(self.t)}"
        width = self.d if self.bf is None else self.bf
        return f"HSS {_dimension_text(self.d)}×{_dimension_text(width)}×" \
               f"{_dimension_text(self.t)}"


ColumnSectionInput = WSectionInput | HSSSectionInput


class ShearLugInput(_Input):
    """Shear lug welded under the plate (DG1 §4.5)."""

    width: Quantity
    """b_sl, across the shear."""
    embedment: Quantity
    """h_sl, depth bearing on the concrete below the grout."""
    thickness: Quantity
    weld: Quantity
    """Fillet weld size on both faces."""
    direction: Literal["strong", "weak", "both"] = "strong"
    """strong: resists the shear along N (lug along B); weak: along B; both: cruciform."""
    grade: str = "ASTM A572 Gr. 50"
    ca1: Quantity | None = None
    """Edge distance in the shear direction for concrete breakout (omit: not checked)."""
    ca2: list[Quantity | None] = Field(default_factory=lambda: [None, None])
    """Edge distances at both sides of the lug (null: far)."""


class BasePlateInput(_Input):
    column: str | ColumnSectionInput
    """AISC label (e.g. ``W12X96``) or a generic section object."""
    column_grade: str = "ASTM A992"
    """Grade of the catalog shape; generic sections carry their own ``grade``."""
    N: Quantity
    B: Quantity
    tp: Quantity
    plate_grade: str = "ASTM A572 Gr. 50"
    pressure_model: PressureModel = PressureModel.RECTANGULAR
    bearing_area_model: BearingAreaModel = BearingAreaModel.PLATE
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
    shear_lug: ShearLugInput | None = None


class LoadCaseInput(_Input):
    name: str
    type: LoadType
    P: Quantity = 0.0
    """Axial force, compression positive."""
    V: Quantity = 0.0
    """Shear along the strong axis direction (N)."""
    M: Quantity = 0.0
    """Strong-axis moment."""
    V_weak: Quantity = 0.0
    """Shear along the weak axis direction (B)."""
    M_weak: Quantity = 0.0
    """Weak-axis moment; with a non-zero value the plate is checked for biaxial bending."""


class CustomCombinationInput(_Input):
    """A load combination defined by the user, by case name."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    name: str = Field(min_length=1)
    method: Method = Method.LRFD
    factors: dict[str, float] = Field(min_length=1)
    """Factor applied to each load case; negative values reverse the case sign."""
    seismic: bool = False
    overstrength: bool = False
    allowable_increase: float = Field(default=1.0, ge=1.0)
    """Factor permitted on ASD allowable strengths (e.g. 1.2 for E_m)."""
    source: str = ""

    @model_validator(mode="after")
    def _nonzero_factors(self) -> CustomCombinationInput:
        if not any(value != 0.0 for value in self.factors.values()):
            raise ValueError("a custom combination needs at least one non-zero factor")
        return self


class CombinationOptions(_Input):
    methods: list[Method] = Field(default_factory=lambda: [Method.LRFD])
    live_factor: float = 1.0
    SDS: float | None = None
    rho: float = 1.0
    omega0: float | None = None
    include_code: bool = True
    """Also generate the ASCE 7-22 combinations for ``methods``."""
    custom: list[CustomCombinationInput] = Field(default_factory=list)
    """User-defined combinations, added after the generated ones."""


class Project(_Input):
    format_version: int = FORMAT_VERSION
    generator: str = f"OpenConex {__version__}"
    info: ProjectInfo = Field(default_factory=ProjectInfo)
    materials: list[MaterialInput] = Field(default_factory=list)
    """Structural steels added to the built-in AISC library for this project."""
    base_plate: BasePlateInput
    cases: list[LoadCaseInput]
    combinations: CombinationOptions = Field(default_factory=CombinationOptions)

    @model_validator(mode="after")
    def _consistent_loads(self) -> Project:
        case_names = [case.name for case in self.cases]
        repeated = _repeated(case_names)
        if repeated:
            raise ValueError(f"duplicate load case names: {repeated}")
        custom = self.combinations.custom
        repeated = _repeated([combination.name for combination in custom])
        if repeated:
            raise ValueError(f"duplicate custom combination names: {repeated}")
        unknown = {name for combination in custom for name in combination.factors} - set(case_names)
        if unknown:
            raise ValueError(f"custom combinations use undefined load cases: {sorted(unknown)}")
        if not custom and not (self.combinations.include_code and self.combinations.methods):
            raise ValueError("no load combinations: enable include_code or define custom ones")
        library = self.material_library()
        if self.base_plate.plate_grade not in library:
            raise ValueError(f"unknown plate material: {self.base_plate.plate_grade!r}")
        if (self.base_plate.shear_lug is not None
                and self.base_plate.shear_lug.grade not in library):
            raise ValueError(f"unknown shear lug material: "
                             f"{self.base_plate.shear_lug.grade!r}")
        column = self.base_plate.column
        if isinstance(column, str):
            if self.base_plate.column_grade not in library:
                raise ValueError(f"unknown column material: {self.base_plate.column_grade!r}")
        elif column.grade not in library:
            raise ValueError(f"unknown column material: {column.grade!r}")
        if self.base_plate.bearing_area_model is BearingAreaModel.EFFECTIVE:
            if isinstance(column, HSSSectionInput):
                raise ValueError("effective bearing area is only defined for I-shapes")
            if self.base_plate.pressure_model is PressureModel.TRIANGULAR:
                raise ValueError("effective bearing area needs the rectangular pressure model")
        if self.base_plate.pressure_model is PressureModel.TRIANGULAR:
            if any(self.quantity(case.M_weak, Kind.MOMENT) != 0 for case in self.cases):
                raise ValueError(
                    "triangular pressure model does not support weak-axis moment yet")
        return self

    def material_library(self) -> dict[str, SteelGrade]:
        """Built-in AISC steels plus the project-defined ones."""
        library = dict(STEELS)
        for custom in self.materials:
            name = custom.name.strip()
            if name in library:
                raise ValueError(f"material name already exists: {name!r}")
            Fy = self.quantity(custom.Fy, Kind.STRESS)
            Fu = self.quantity(custom.Fu, Kind.STRESS)
            E = self.quantity(custom.E, Kind.STRESS)
            if min(Fy, Fu, E) <= 0:
                raise ValueError(f"material {name!r} needs positive Fy, Fu and E")
            if Fu < Fy:
                raise ValueError(f"material {name!r}: Fu must be at least Fy")
            library[name] = SteelGrade(name=name, Fy=Fy, Fu=Fu, E=E)
        return library

    # -- conversion to the engine model ------------------------------------------------
    def quantity(self, value: Quantity, kind: Kind) -> float:
        """Value typed in the project (text with unit, or number in project units), internal."""
        units = self.info.unit_system()
        if isinstance(value, (int, float)):
            return parse(str(value), kind, units)
        return parse(value, kind, units)

    def column_model(self,
                     library: dict[str, SteelGrade] | None = None) -> IShape | HSSShape:
        """Column section of the project: catalog label or generic dimensions."""
        library = library or self.material_library()
        section = self.base_plate.column
        L = Kind.LENGTH
        if isinstance(section, str):
            return aisc_shapes().get(section).to_ishape(self.base_plate.column_grade,
                                                        materials=library)
        if isinstance(section, WSectionInput):
            return IShape(
                name=section.label(), d=self.quantity(section.d, L),
                bf=self.quantity(section.bf, L), tf=self.quantity(section.tf, L),
                tw=self.quantity(section.tw, L), k_des=self.quantity(section.k_des, L),
                grade=section.grade, materials=library)
        kind = section.shape
        width = (None if kind is HSSKind.ROUND else
                 self.quantity(section.d if section.bf is None else section.bf, L))
        return HSSShape(name=section.label(), kind=kind, d=self.quantity(section.d, L),
                        width=width, t=self.quantity(section.t, L), grade=section.grade,
                        materials=library)

    def base_plate_model(self) -> BasePlate:
        bp = self.base_plate
        L, T = Kind.LENGTH, Kind.THICKNESS
        library = self.material_library()
        column = self.column_model(library)
        edges = Edges(**{k: self.quantity(v, L) for k, v in bp.edges.items()})
        return BasePlate(
            column=column, N=self.quantity(bp.N, L), B=self.quantity(bp.B, L),
            tp=self.quantity(bp.tp, T),
            fc=self.quantity(bp.fc, Kind.STRESS),
            rod=BoltSpec(diameter=self.quantity(bp.rod_diameter, L), grade=bp.rod_grade),
            f=self.quantity(bp.f, L), rods_per_side=bp.rods_per_side,
            rod_spacing=self.quantity(bp.rod_spacing, L), hef=self.quantity(bp.hef, L),
            plate_grade=bp.plate_grade, pressure_model=bp.pressure_model,
            bearing_area_model=bp.bearing_area_model,
            A2_over_A1=bp.A2_over_A1, edges=edges,
            washer_thickness=(None if bp.washer_thickness is None
                              else self.quantity(bp.washer_thickness, T)),
            grout_pad=bp.grout_pad,
            flange_weld=None if bp.flange_weld is None else self.quantity(bp.flange_weld, T),
            friction_mu=bp.friction_mu, cracked=bp.cracked, seismic=bp.seismic,
            shear_lug=self._shear_lug(), materials=library,
        )

    def _shear_lug(self) -> ShearLug | None:
        lug, L = self.base_plate.shear_lug, Kind.LENGTH
        if lug is None:
            return None
        sides = [None if v is None else self.quantity(v, L) for v in lug.ca2[:2]]
        return ShearLug(width=self.quantity(lug.width, L),
                        embedment=self.quantity(lug.embedment, L),
                        thickness=self.quantity(lug.thickness, Kind.THICKNESS),
                        weld=self.quantity(lug.weld, Kind.THICKNESS), direction=lug.direction,
                        grade=lug.grade, grout=self.quantity(self.base_plate.grout, L),
                        ca1=None if lug.ca1 is None else self.quantity(lug.ca1, L),
                        ca2=tuple([*sides, None, None][:2]))

    def case_forces(self) -> dict[str, Forces]:
        F, M = Kind.FORCE, Kind.MOMENT
        return {c.name: Forces(P=self.quantity(c.P, F), V2=self.quantity(c.V, F),
                               M3=self.quantity(c.M, M), V3=self.quantity(c.V_weak, F),
                               M2=self.quantity(c.M_weak, M)) for c in self.cases}

    def load_combinations(self) -> list[LoadCombination]:
        opts = self.combinations
        case_names = {case.name for case in self.cases}
        repeated = _repeated([case.name for case in self.cases])
        if repeated:
            raise ValueError(f"duplicate load case names: {repeated}")
        cases = [LoadCase(name=c.name, type=c.type) for c in self.cases]
        seismic = (SeismicParameters(SDS=opts.SDS, rho=opts.rho, omega0=opts.omega0)
                   if opts.SDS is not None else None)
        out: list[LoadCombination] = []
        if opts.include_code:
            for method in opts.methods:
                out += asce7_combinations(cases, method, seismic, opts.live_factor)
        for custom in opts.custom:
            unknown = set(custom.factors) - case_names
            if unknown:
                raise ValueError(f"custom combination {custom.name!r} uses undefined load cases: "
                                 f"{sorted(unknown)}")
            factors = {name: value for name, value in custom.factors.items() if value != 0.0}
            if not factors:
                raise ValueError(f"custom combination {custom.name!r} has no non-zero factors")
            out.append(LoadCombination(
                name=custom.name, method=custom.method, factors=factors,
                seismic=custom.seismic, overstrength=custom.overstrength,
                allowable_increase=custom.allowable_increase,
                source=custom.source or "custom"))
        repeated = _repeated([combination.name for combination in out])
        if repeated:
            raise ValueError(f"duplicate load combination names: {repeated}")
        if not out:
            raise ValueError("no load combinations: enable include_code or define custom ones")
        return out


def load_project(path: str | Path) -> Project:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    version = data.get("format_version", FORMAT_VERSION)
    if version > FORMAT_VERSION:
        raise ValueError(f"project format {version} is newer than this OpenConex "
                         f"({FORMAT_VERSION}); please update")
    return Project.model_validate(data)


def save_project(project: Project, path: str | Path) -> None:
    """Write ``project`` in the current format version."""
    current = project.model_copy(update={"format_version": FORMAT_VERSION})
    Path(path).write_text(current.model_dump_json(indent=2, exclude_defaults=False) + "\n",
                          encoding="utf-8", newline="\n")
