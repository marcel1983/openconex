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
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from openconex import __version__
from openconex.connections.base_plate.check import (
    BasePlate,
    BearingAreaModel,
    EmbeddedBase,
    EmbeddedRebar,
    EmbeddedType,
    Pedestal,
    PedestalRebar,
    PressureModel,
    Reinforcement,
    ShearLug,
    WeakBase,
)
from openconex.connections.moment.fr_moment import FlangeDetail
from openconex.connections.shear.check import ShearType
from openconex.core.loads import (
    Forces,
    LoadCase,
    LoadCombination,
    LoadType,
    Method,
    SeismicParameters,
    asce7_combinations,
)
from openconex.core.materials import (
    BOLTS,
    ELECTRODES,
    STEELS,
    BoltGrade,
    SteelGrade,
    WeldElectrode,
)
from openconex.core.model import BoltSpec, HSSKind, HSSShape, IShape
from openconex.core.shapes import aisc_shapes
from openconex.io.moment_project import (
    FlangePlateInput,
    MomentConnectionInput,
    WebPlateInput,
)
from openconex.io.shear_project import (
    BoltInput,
    CopeInput,
    DoublerPlateInput,
    LongitudinalStiffenerInput,
    ShearConnectionInput,
)
from openconex.io.splice_project import (
    FlangeSpliceInput,
    SpliceInput,
    SpliceType,
    WebSpliceInput,
)
from openconex.kernel.anchors import Edges
from openconex.units import PRESETS, Kind, UnitSystem, format_value, parse, to_internal

if TYPE_CHECKING:
    from openconex.connections.moment.fr_moment import MomentConnection
    from openconex.connections.shear.check import ShearConnection
    from openconex.connections.splice.splice import BeamSplice, ColumnSplice

__all__ = [
    "FORMAT_VERSION",
    "BasePlateInput",
    "BoltGradeInput",
    "BoltInput",
    "ColumnSectionInput",
    "CombinationOptions",
    "CopeInput",
    "CustomCombinationInput",
    "DoublerPlateInput",
    "ElectrodeInput",
    "EmbeddedBaseInput",
    "EmbeddedRebarInput",
    "FlangePlateInput",
    "FlangeSpliceInput",
    "HSSSectionInput",
    "LoadCaseInput",
    "LongitudinalStiffenerInput",
    "MaterialInput",
    "MomentConnectionInput",
    "PedestalInput",
    "PedestalRebarInput",
    "Project",
    "ProjectInfo",
    "ReinforcementInput",
    "ShearConnectionInput",
    "SpliceInput",
    "WSectionInput",
    "WeakBaseInput",
    "WebPlateInput",
    "WebSpliceInput",
    "load_project",
    "save_project",
]

FORMAT_VERSION = 14
Quantity = str | float


def _far_edges() -> list[Quantity | None]:
    """Edge distances of both sides of a shear lug: far (None)."""
    return [None, None]


def _required[B](block: B | None, key: str) -> B:
    if block is None:
        raise ValueError(f"the project has no {key} block")
    return block


def _validate_bfp(mc: MomentConnectionInput) -> None:
    """Flange plates and bolts of an AISC 358 BFP connection (AISC 358-22 §7.4.1, §7.4.4)."""
    if mc.grade not in ("ASTM A36", "ASTM A572 Gr. 50"):
        raise ValueError("AISC 358 bfp flange plates must be ASTM A36 or A572 Gr. 50")
    bolt = mc.bolt
    if bolt is not None and ("A490" not in bolt.grade and "F2280" not in bolt.grade):
        raise ValueError("AISC 358 bfp flange bolts must be ASTM F3125 A490 or F2280")
    if bolt is not None and bolt.threads.value != "X":
        raise ValueError("AISC 358 bfp flange bolts must have the threads excluded "
                         "from the shear plane (threads X)")


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


class BoltGradeInput(_Input):
    """A bolt or anchor-rod grade added to the built-in AISC library."""

    name: str = Field(min_length=1)
    Fnt: Quantity
    """Nominal tensile stress."""
    Fnv_N: Quantity
    """Nominal shear stress, threads included."""
    Fnv_X: Quantity
    """Nominal shear stress, threads excluded."""
    Fu: Quantity
    """Specified minimum tensile strength."""
    Fy: Quantity | None = None
    """Specified minimum yield stress, when the grade defines one."""

    @model_validator(mode="after")
    def _nonblank_name(self) -> BoltGradeInput:
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("bolt grade name must not be blank")
        return self


class ElectrodeInput(_Input):
    """A welding electrode added to the built-in library."""

    name: str = Field(min_length=1)
    FEXX: Quantity
    """Filler metal classification strength."""

    @model_validator(mode="after")
    def _nonblank_name(self) -> ElectrodeInput:
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("electrode name must not be blank")
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


ShearConnectionInput.model_rebuild(_types_namespace={"WSectionInput": WSectionInput})
MomentConnectionInput.model_rebuild(_types_namespace={"WSectionInput": WSectionInput})
SpliceInput.model_rebuild(_types_namespace={"WSectionInput": WSectionInput})


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
    electrode: str = "E70XX"
    ca1: Quantity | None = None
    """Edge distance in the shear direction for concrete breakout (omit: not checked)."""
    ca2: list[Quantity | None] = Field(default_factory=_far_edges)
    """Edge distances at both sides of the lug (null: far)."""


class ReinforcementInput(_Input):
    """Hooked reinforcement developed on both sides of the concrete breakout."""

    bars: str = ""
    """Label for the report, e.g. ``"4 #6"``."""
    area: Quantity
    """Total provided area of reinforcement."""
    fy: Quantity
    db: Quantity
    clear_cover: Quantity = "2 in"
    anchor_to_bar: Quantity
    """Horizontal distance from the anchor to the reinforcing bar."""
    le: Quantity
    """Available development length."""


class PedestalRebarInput(_Input):
    """Longitudinal pedestal bar in plan, relative to the column axis."""

    x: Quantity
    y: Quantity
    diameter: Quantity


class PedestalInput(_Input):
    """Concrete pedestal designed as a short tied column (ACI 318-19).

    The plan size is ``pedestal_N`` × ``pedestal_B`` of the base plate; for a
    round pedestal ``pedestal_N`` is the diameter and ``pedestal_B`` is omitted
    or equal. The longitudinal bars are ``pedestal_rebars``.
    """

    shape: Literal["rectangular", "round"] = "rectangular"
    height: Quantity
    """From the top of the footing to the top of the pedestal."""
    fy: Quantity = "60 ksi"
    """Yield strength of the longitudinal bars."""
    tie_diameter: Quantity | None = None
    """Tie (hoop) bar diameter; omitted: no transverse reinforcement."""
    tie_spacing: Quantity | None = None
    tie_fy: Quantity = "60 ksi"
    tie_legs: int = Field(default=2, ge=1)
    """Tie legs crossing each shear plane."""
    min_ratio: float = Field(default=0.01, gt=0.0, le=0.08)
    """Minimum longitudinal ratio ρ_g (ACI 318-19 §10.6.1.1: 0.01)."""
    lightweight: float = Field(default=1.0, gt=0.0, le=1.0)
    """λ of the concrete (1.0: normalweight)."""


class EmbeddedRebarInput(_Input):
    """Horizontal reinforcement layer of an embedded base."""

    area: Quantity
    fy: Quantity
    depth: Quantity
    """Depth below the top of the foundation."""


class EmbeddedBaseInput(_Input):
    """Embedded base, DG1 Chapter 5: Type I (§5.2.1, §5.3) or Type II (§5.2.2)."""

    embedment: Quantity
    """Depth of the column embedded in the concrete below the base plate."""
    foundation_width: Quantity
    """Width of the concrete foundation in the direction of bending."""
    face_plate_thickness: Quantity | None = None
    """Face bearing plate thickness; required by Type I, not used by Type II."""
    beta1: float = Field(default=0.85, gt=0.0, le=1.0)
    """Concrete stress-block factor used in the horizontal bearing equation."""
    base_plate_width: Quantity | None = None
    """Width B of the embedded base plate at the bottom of the column."""
    base_plate_thickness: Quantity | None = None
    """Thickness of the embedded base plate."""
    rebar_top: EmbeddedRebarInput | None = None
    rebar_bottom: EmbeddedRebarInput | None = None
    damage_limit: bool = False
    """Apply the additional 0.8 factor on M_HB recommended to limit damage."""
    type: Literal["I", "II"] = "I"
    """I: foundation below the embedded base plate not designed for vertical forces;
    II: it is, and axial compression goes through the embedded base plate (DG1 §5.2)."""
    face_plate_weld: Quantity | None = None
    """Fillet weld of the face bearing plates to the column (Type I; omitted: not checked)."""


class WeakBaseInput(_Input):
    """Weak base with ductile (upset-thread) anchor rods, DG1 §6.4."""

    reduced_diameter: Quantity
    stretch_length: Quantity
    Rt: float = Field(default=1.2, ge=1.0)


class BasePlateInput(_Input):
    connection_type: Literal["exposed", "embedded"] | None = None
    """``exposed`` (default) or ``embedded``. Omitted: inferred from ``embedded_base``."""
    column: str | ColumnSectionInput
    """AISC label (e.g. ``W12X96``) or a generic section object."""
    column_grade: str = "ASTM A992"
    """Grade of the catalog shape; generic sections carry their own ``grade``."""
    N: Quantity | None = None
    B: Quantity | None = None
    tp: Quantity | None = None
    plate_grade: str = "ASTM A572 Gr. 50"
    electrode: str = "E70XX"
    pressure_model: PressureModel = PressureModel.RECTANGULAR
    bearing_area_model: BearingAreaModel = BearingAreaModel.PLATE
    rod_bending_lever: Quantity | None = None
    """Anchor-to-web/flange distance for the plate bending check at the anchors."""
    fc: Quantity
    A2_over_A1: float = 1.0
    bearing_area: Quantity | None = None
    """Bearing area of the embedded nut or plate for anchor pullout."""
    pedestal_N: Quantity | None = None
    pedestal_B: Quantity | None = None
    grout: Quantity = "1.5 in"
    rod_diameter: Quantity | None = None
    rod_grade: str = "ASTM F1554 Gr. 36"
    rods_per_side: int = 2
    f: Quantity | None = None
    """Column axis to each anchor row."""
    rod_spacing: Quantity = 0.0
    hef: Quantity = 0.0
    pedestal_rebars: list[PedestalRebarInput] = Field(default_factory=list)
    pedestal: PedestalInput | None = None
    """Design of the pedestal as a short column; omitted: the pedestal is not checked."""
    reinforcement: ReinforcementInput | None = None
    weak_base: WeakBaseInput | None = None
    embedded_base: EmbeddedBaseInput | None = None
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
    column_V: Quantity = 0.0
    """Moment connections with ``panel_zone``: story shear of the column above the joint."""
    column_P: Quantity = 0.0
    """Moment connections with ``panel_zone``: column axial force."""


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
    bolts: list[BoltGradeInput] = Field(default_factory=list)
    """Bolt and anchor-rod grades added to the built-in AISC library."""
    electrodes: list[ElectrodeInput] = Field(default_factory=list)
    """Welding electrodes added to the built-in library."""
    sections: list[ColumnSectionInput] = Field(default_factory=list)
    """Custom column sections saved with the project, available in the GUI."""
    base_plate: BasePlateInput | None = None
    shear_connection: ShearConnectionInput | None = None
    """Beam-end shear connection."""
    moment_connection: MomentConnectionInput | None = None
    """Beam-to-column moment connection."""
    splice: SpliceInput | None = None
    """Beam or column splice. A project holds exactly one of ``base_plate``,
    ``shear_connection``, ``moment_connection`` and ``splice``."""
    cases: list[LoadCaseInput]
    combinations: CombinationOptions = Field(default_factory=CombinationOptions)

    @model_validator(mode="after")
    def _consistent_loads(self) -> Project:
        """Cases, combinations and the one connection block, in that order."""
        self._validate_cases()
        self._validate_combinations()
        key = self._validate_family()
        {"base_plate": self._validate_base_plate,
         "shear_connection": self._validate_shear,
         "moment_connection": self._validate_moment,
         "splice": self._validate_splice}[key]()
        return self

    # -- connection blocks ---------------------------------------------------------------
    def require_base_plate(self) -> BasePlateInput:
        """The ``base_plate`` block; ``ValueError`` if the project holds another one."""
        return _required(self.base_plate, "base_plate")

    def require_shear_connection(self) -> ShearConnectionInput:
        """The ``shear_connection`` block; ``ValueError`` if the project holds another one."""
        return _required(self.shear_connection, "shear_connection")

    def require_moment_connection(self) -> MomentConnectionInput:
        """The ``moment_connection`` block; ``ValueError`` if the project holds another one."""
        return _required(self.moment_connection, "moment_connection")

    def require_splice(self) -> SpliceInput:
        """The ``splice`` block; ``ValueError`` if the project holds another one."""
        return _required(self.splice, "splice")

    # -- validation ----------------------------------------------------------------------
    def _validate_cases(self) -> None:
        repeated = _repeated([case.name for case in self.cases])
        if repeated:
            raise ValueError(f"duplicate load case names: {repeated}")
        opts = self.combinations
        quakes = [c.name for c in self.cases if c.type is LoadType.SEISMIC]
        if opts.include_code and opts.methods and quakes and opts.SDS is None:
            raise ValueError(
                f"seismic load cases {quakes} need combinations.SDS to generate the ASCE 7-22 "
                "seismic combinations (use SDS = 0 to omit the vertical effect Ev)")

    def _validate_combinations(self) -> None:
        custom = self.combinations.custom
        repeated = _repeated([combination.name for combination in custom])
        if repeated:
            raise ValueError(f"duplicate custom combination names: {repeated}")
        case_names = {case.name for case in self.cases}
        unknown = {name for combination in custom for name in combination.factors} - case_names
        if unknown:
            raise ValueError(f"custom combinations use undefined load cases: {sorted(unknown)}")
        if not custom and not (self.combinations.include_code and self.combinations.methods):
            raise ValueError("no load combinations: enable include_code or define custom ones")

    def _validate_family(self) -> str:
        """Key of the one connection block; cases that only one family takes."""
        from openconex.families import KEYS
        blocks = [key for key in KEYS if getattr(self, key) is not None]
        if len(blocks) != 1:
            raise ValueError("a project needs exactly one of " + ", ".join(KEYS))
        if self.moment_connection is None and any(
                self.quantity(c.column_V, Kind.FORCE) or self.quantity(c.column_P, Kind.FORCE)
                for c in self.cases):
            raise ValueError("column_V and column_P are only used by moment connections")
        return blocks[0]

    def _any_case(self, field: str, kind: Kind) -> bool:
        """Whether some load case has a non-zero ``field``."""
        return any(self.quantity(getattr(case, field), kind) != 0 for case in self.cases)

    def _validate_base_plate(self) -> None:
        bp = self.require_base_plate()
        self._validate_base_plate_grades(bp)
        embedded = bp.embedded_base
        connection = bp.connection_type or ("embedded" if embedded is not None else "exposed")
        if connection == "embedded" and embedded is None:
            raise ValueError("connection_type 'embedded' requires embedded_base")
        if connection == "exposed" and embedded is not None:
            raise ValueError("embedded_base requires connection_type 'embedded'")
        if connection == "exposed":
            missing = [name for name, value in (
                ("N", bp.N), ("B", bp.B), ("tp", bp.tp), ("rod_diameter", bp.rod_diameter),
                ("f", bp.f)) if value is None]
            if missing:
                raise ValueError(f"exposed base plate needs {', '.join(missing)}")
        self._validate_bearing(bp)
        self._validate_weak_base(bp.weak_base)
        if bp.bearing_area is not None and self.quantity(bp.bearing_area, Kind.AREA) <= 0:
            raise ValueError("bearing_area must be positive")
        if embedded is not None:
            self._validate_embedded(bp, embedded)
        for bar in bp.pedestal_rebars:
            if self.quantity(bar.diameter, Kind.LENGTH) <= 0:
                raise ValueError("pedestal rebar diameter must be positive")
        self._validate_pedestal(embedded)
        reinforcement = bp.reinforcement
        if reinforcement is not None:
            for value, kind in ((reinforcement.area, Kind.AREA),
                                (reinforcement.fy, Kind.STRESS),
                                (reinforcement.db, Kind.LENGTH),
                                (reinforcement.clear_cover, Kind.LENGTH),
                                (reinforcement.anchor_to_bar, Kind.LENGTH),
                                (reinforcement.le, Kind.LENGTH)):
                if self.quantity(value, kind) <= 0:
                    raise ValueError("reinforcement dimensions and strengths must be positive")

    def _validate_base_plate_grades(self, bp: BasePlateInput) -> None:
        """Plate, rods, electrode, lug, custom sections and column: known materials."""
        library = self.material_library()
        if bp.plate_grade not in library:
            raise ValueError(f"unknown plate material: {bp.plate_grade!r}")
        if bp.rod_grade not in self.bolt_library():
            raise ValueError(f"unknown bolt grade: {bp.rod_grade!r}")
        electrodes = self.electrode_library()
        if bp.electrode not in electrodes:
            raise ValueError(f"unknown electrode: {bp.electrode!r}")
        lug = bp.shear_lug
        if lug is not None and lug.grade not in library:
            raise ValueError(f"unknown shear lug material: {lug.grade!r}")
        if lug is not None and lug.electrode not in electrodes:
            raise ValueError(f"unknown shear lug electrode: {lug.electrode!r}")
        repeated = _repeated([section.label() for section in self.sections])
        if repeated:
            raise ValueError(f"duplicate custom section names: {repeated}")
        for section in self.sections:
            if section.grade not in library:
                raise ValueError(f"unknown section material: {section.grade!r}")
        grade = bp.column_grade if isinstance(bp.column, str) else bp.column.grade
        if grade not in library:
            raise ValueError(f"unknown column material: {grade!r}")

    def _validate_bearing(self, bp: BasePlateInput) -> None:
        """Bearing area model and round HSS: only where the method is defined."""
        column = bp.column
        has_moment = self._any_case("M", Kind.MOMENT) or self._any_case("M_weak", Kind.MOMENT)
        if bp.bearing_area_model is BearingAreaModel.EFFECTIVE:
            if isinstance(column, HSSSectionInput):
                raise ValueError("effective bearing area is only defined for I-shapes")
            if bp.pressure_model is PressureModel.TRIANGULAR:
                raise ValueError("effective bearing area needs the rectangular pressure model")
            if has_moment:
                raise ValueError(
                    "effective bearing area is only defined for concentric compression")
        if (isinstance(column, HSSSectionInput) and column.shape is HSSKind.ROUND
                and has_moment):
            raise ValueError(
                "round HSS with moment is not supported; only axial compression is validated")

    def _validate_weak_base(self, weak: WeakBaseInput | None) -> None:
        if weak is None:
            return
        if self.require_base_plate().pressure_model is PressureModel.TRIANGULAR:
            raise ValueError("weak base requires the rectangular pressure model")
        if self._any_case("M_weak", Kind.MOMENT):
            raise ValueError("weak base does not support weak-axis moment yet")
        if self.quantity(weak.reduced_diameter, Kind.LENGTH) <= 0:
            raise ValueError("weak base reduced diameter must be positive")
        if self.quantity(weak.stretch_length, Kind.LENGTH) <= 0:
            raise ValueError("weak base stretch length must be positive")

    def _validate_embedded_scope(self, bp: BasePlateInput) -> None:
        """What the embedded base method does not cover yet."""
        if bp.weak_base is not None:
            raise ValueError("embedded base and weak base cannot be combined")
        if bp.shear_lug is not None:
            raise ValueError("embedded base does not support a shear lug yet")
        if isinstance(bp.column, HSSSectionInput):
            raise ValueError("embedded base is only defined for I-shapes")
        if self._any_case("M_weak", Kind.MOMENT):
            raise ValueError("embedded base does not support weak-axis moment yet")
        if ((self.combinations.include_code and Method.ASD in self.combinations.methods)
                or any(c.method is Method.ASD for c in self.combinations.custom)):
            raise ValueError("embedded base requires LRFD combinations")

    def _validate_embedded(self, bp: BasePlateInput, embedded: EmbeddedBaseInput) -> None:
        """Embedded base: scope, then positive dimensions."""
        self._validate_embedded_scope(bp)
        if embedded.type == "I" and embedded.face_plate_thickness is None:
            raise ValueError("embedded base Type I needs face_plate_thickness")
        if embedded.type == "II" and embedded.base_plate_width is None:
            raise ValueError("embedded base Type II needs the embedded base plate "
                             "(base_plate_width and base_plate_thickness)")
        for value, kind in ((embedded.embedment, Kind.LENGTH),
                            (embedded.foundation_width, Kind.LENGTH),
                            (embedded.face_plate_thickness, Kind.THICKNESS),
                            (embedded.face_plate_weld, Kind.THICKNESS)):
            if value is not None and self.quantity(value, kind) <= 0:
                raise ValueError("embedded base dimensions must be positive")
        if embedded.beta1 <= 0:
            raise ValueError("embedded base beta1 must be positive")
        width, thickness = embedded.base_plate_width, embedded.base_plate_thickness
        if (width is None) != (thickness is None):
            raise ValueError("embedded base plate needs both width and thickness")
        if width is not None and thickness is not None:
            if self.quantity(width, Kind.LENGTH) <= 0:
                raise ValueError("embedded base plate width must be positive")
            if self.quantity(thickness, Kind.THICKNESS) <= 0:
                raise ValueError("embedded base plate thickness must be positive")
        for layer in (embedded.rebar_top, embedded.rebar_bottom):
            if layer is None:
                continue
            for value, kind in ((layer.area, Kind.AREA), (layer.fy, Kind.STRESS),
                                (layer.depth, Kind.LENGTH)):
                if self.quantity(value, kind) <= 0:
                    raise ValueError("embedded rebar area, fy and depth must be positive")

    def _validate_pedestal(self, embedded: EmbeddedBaseInput | None) -> None:
        bp = self.require_base_plate()
        pedestal = bp.pedestal
        if pedestal is None:
            return
        if embedded is not None and embedded.type == "I":
            raise ValueError("pedestal design is not used by the embedded base Type I")
        if pedestal.shape == "round":
            if bp.pedestal_N is None:
                raise ValueError("a round pedestal needs its diameter in pedestal_N")
            if (bp.pedestal_B is not None and abs(
                    self.quantity(bp.pedestal_B, Kind.LENGTH)
                    - self.quantity(bp.pedestal_N, Kind.LENGTH)) > 1e-6):
                raise ValueError("a round pedestal uses pedestal_N as its diameter; "
                                 "omit pedestal_B or make it equal")
        elif bp.pedestal_N is None or bp.pedestal_B is None:
            raise ValueError("pedestal design needs pedestal_N and pedestal_B")
        if not bp.pedestal_rebars:
            raise ValueError("pedestal design needs the longitudinal bars in pedestal_rebars")
        if self.quantity(pedestal.height, Kind.LENGTH) <= 0:
            raise ValueError("pedestal height must be positive")
        ties = (pedestal.tie_diameter, pedestal.tie_spacing)
        if (ties[0] is None) != (ties[1] is None):
            raise ValueError("pedestal ties need both tie_diameter and tie_spacing")
        diameter, spacing = ties
        if diameter is not None and spacing is not None and (
                self.quantity(diameter, Kind.LENGTH) <= 0
                or self.quantity(spacing, Kind.LENGTH) <= 0):
            raise ValueError("pedestal tie diameter and spacing must be positive")
        for value in (pedestal.fy, pedestal.tie_fy):
            if self.quantity(value, Kind.STRESS) <= 0:
                raise ValueError("pedestal bar strengths must be positive")

    def _validate_shear(self) -> None:
        sc = self.require_shear_connection()
        missing = sc.missing()
        if missing:
            raise ValueError(f"{sc.type.value} connection needs {', '.join(missing)}")
        library = self.material_library()
        for grade in (sc.grade, sc.beam_grade, sc.support_grade):
            if grade not in library:
                raise ValueError(f"unknown material: {grade!r}")
        for section in (sc.beam, sc.support):
            if not isinstance(section, str) and section.grade not in library:
                raise ValueError(f"unknown section material: {section.grade!r}")
        if sc.bolt.grade not in self.bolt_library():
            raise ValueError(f"unknown bolt grade: {sc.bolt.grade!r}")
        if sc.electrode not in self.electrode_library():
            raise ValueError(f"unknown electrode: {sc.electrode!r}")
        if any(self.quantity(c.M, Kind.MOMENT) or self.quantity(c.V_weak, Kind.FORCE)
               or self.quantity(c.M_weak, Kind.MOMENT) for c in self.cases):
            raise ValueError("shear connections take only V and P load cases")
        if sc.type is ShearType.SKEWED_BENT_PLATE:
            self._validate_skewed_plate(sc)
        if sc.cope is not None:
            self._validate_cope(sc.cope)

    def _validate_skewed_plate(self, sc: ShearConnectionInput) -> None:
        """Skewed bent plate: positive dimensions and a load share inside the plate."""
        for name, kind in (("length", Kind.LENGTH), ("thickness", Kind.THICKNESS),
                           ("spacing", Kind.LENGTH), ("lev", Kind.LENGTH),
                           ("leh", Kind.LENGTH), ("weld", Kind.THICKNESS),
                           ("weld_return", Kind.LENGTH), ("weld_offset", Kind.LENGTH)):
            if self.quantity(getattr(sc, name), kind) <= 0:
                raise ValueError(f"skewed bent plate {name} must be positive")
        if sc.share_a is not None and sc.share_b is not None:
            raise ValueError("use share_a or share_b, not both")
        if sc.share_b is not None:
            share = self.quantity(sc.share_b, Kind.DIMENSIONLESS)
            if not 0.0 < share < 1.0:
                raise ValueError("share_b must be between 0 and 1")
        elif sc.share_a is not None:
            share = self.quantity(sc.share_a, Kind.DIMENSIONLESS)
            if not 0.0 < share < 1.0:
                raise ValueError("share_a must be between 0 and 1")
        else:
            if sc.row_distance is None or sc.load_offset is None:
                raise ValueError("row_distance and load_offset are required")
            row = self.quantity(sc.row_distance, Kind.LENGTH)
            offset = self.quantity(sc.load_offset, Kind.LENGTH)
            if not 0.0 < offset < row:
                raise ValueError("load_offset must be between 0 and row_distance")
        for name in ("plate_a_width", "plate_b_width"):
            value = getattr(sc, name)
            if value is not None and self.quantity(value, Kind.LENGTH) <= 0:
                raise ValueError(f"skewed bent plate {name} must be positive")
        for name in ("plate_a_leg", "plate_b_leg", "bend_radius"):
            value = getattr(sc, name)
            if value is not None and self.quantity(value, Kind.LENGTH) <= 0:
                raise ValueError(f"skewed bent plate {name} must be positive")

    def _validate_cope(self, cope: CopeInput) -> None:
        """Cope reinforcement: top cope only, positive dimensions."""
        if (cope.doubler is not None or cope.stiffener is not None) and \
                self.quantity(cope.dc_bottom, Kind.LENGTH) != 0:
            raise ValueError("cope reinforcement is only defined for a top cope")
        blocks = (
            (cope.doubler, (("thickness", Kind.THICKNESS), ("depth", Kind.LENGTH),
                            ("gap", Kind.LENGTH), ("weld", Kind.THICKNESS))),
            (cope.stiffener, (("width", Kind.LENGTH), ("thickness", Kind.THICKNESS),
                              ("weld", Kind.THICKNESS))),
        )
        for block, fields in blocks:
            if block is None:
                continue
            for name, kind in fields:
                if self.quantity(getattr(block, name), kind) <= 0:
                    raise ValueError(f"cope reinforcement {name} must be positive")
            length = getattr(block, "length", None)
            if length is not None and self.quantity(length, Kind.LENGTH) <= 0:
                raise ValueError("cope reinforcement length must be positive")

    def _validate_moment(self) -> None:
        mc = self.require_moment_connection()
        if mc.seismic is not None:
            self._validate_seismic()
        missing = mc.missing()
        if missing:
            raise ValueError(f"{mc.type.value} moment connection needs {', '.join(missing)}")
        self._validate_moment_grades(mc)
        bolts = self.bolt_library()
        end_plate = mc.type is FlangeDetail.END_PLATE
        if mc.support.value == "web":
            if mc.type not in (FlangeDetail.WELDED_FLANGE, FlangeDetail.BOLTED_FLANGE_PLATE):
                raise ValueError("connections to the column web take welded_flange or "
                                 "bolted_flange_plate")
            if mc.panel_zone or mc.continuity_plate or mc.doubler_plate or mc.two_sided:
                raise ValueError("connections to the column web take no panel zone, "
                                 "stiffeners, doubler plates or two_sided")
        ep = mc.end_plate
        if end_plate and ep is not None and ep.snug_tight and bolts[ep.bolt.grade].Fnt > \
                to_internal(100.0, "ksi", Kind.STRESS):
            raise ValueError("snug-tight end-plate bolts must be Group A (A325)")
        if any((self.quantity(c.P, Kind.FORCE) and not end_plate)
               or self.quantity(c.V_weak, Kind.FORCE)
               or self.quantity(c.M_weak, Kind.MOMENT) for c in self.cases):
            raise ValueError("moment connections take only V and M load cases "
                             "(and P for end plates)")

    def _validate_moment_grades(self, mc: MomentConnectionInput) -> None:
        """Plates, members, bolts and electrode of a moment connection: known materials."""
        library = self.material_library()
        for grade in (mc.grade, mc.beam_grade, mc.column_grade):
            if grade not in library:
                raise ValueError(f"unknown material: {grade!r}")
        for section in (mc.beam, mc.column):
            if not isinstance(section, str) and section.grade not in library:
                raise ValueError(f"unknown section material: {section.grade!r}")
        bolts = self.bolt_library()
        for bolt in (mc.web.bolt if mc.web else None, mc.bolt,
                     mc.end_plate.bolt if mc.end_plate else None):
            if bolt is not None and bolt.grade not in bolts:
                raise ValueError(f"unknown bolt grade: {bolt.grade!r}")
        if mc.electrode not in self.electrode_library():
            raise ValueError(f"unknown electrode: {mc.electrode!r}")

    def _validate_splice(self) -> None:
        sp = self.require_splice()
        missing = sp.missing()
        if missing:
            raise ValueError(f"{sp.type.value} splice needs {', '.join(missing)}")
        library = self.material_library()
        for grade in (sp.grade, sp.beam_grade, sp.column_grade):
            if grade not in library:
                raise ValueError(f"unknown material: {grade!r}")
        for section in (sp.beam, sp.upper, sp.lower):
            if section is not None and not isinstance(section, str) and \
                    section.grade not in library:
                raise ValueError(f"unknown section material: {section.grade!r}")
        bolts = self.bolt_library()
        for bolt in (sp.flange.bolt, sp.web.bolt if sp.web else None):
            if bolt is not None and bolt.grade not in bolts:
                raise ValueError(f"unknown bolt grade: {bolt.grade!r}")
        F, M = Kind.FORCE, Kind.MOMENT
        if any(self.quantity(c.M_weak, M) for c in self.cases):
            raise ValueError("splices take no weak-axis moment M_weak")
        if sp.type is SpliceType.BEAM:
            if sp.upper is not None or sp.lower is not None:
                raise ValueError("beam splices take beam, not upper and lower")
            if any(self.quantity(c.V_weak, F) for c in self.cases):
                raise ValueError("beam splices take only P, V and M load cases")
        else:
            if sp.beam is not None:
                raise ValueError("column splices take upper and lower, not beam")
            if sp.flange.inner_width is not None:
                raise ValueError("column splices take no inner flange plates")
            if sp.web is None and any(self.quantity(c.V, F) for c in self.cases):
                raise ValueError("column splice with strong-axis shear V needs web plates "
                                 "(web)")

    def splice_model(self) -> BeamSplice | ColumnSplice:
        """Engine model of the splice (:class:`BeamSplice` or :class:`ColumnSplice`)."""
        from openconex.io.splice_project import splice_model
        return splice_model(self)

    def _validate_seismic(self) -> None:
        from openconex.io.moment_project import PREQUALIFIED_DETAIL, PREQUALIFIED_LAYOUTS
        mc = self.require_moment_connection()
        s = mc.seismic
        assert s is not None
        need = PREQUALIFIED_DETAIL[s.connection]
        if mc.type is not need:
            raise ValueError(f"AISC 358 {s.connection.value} needs a {need.value} moment "
                             "connection")
        if mc.support.value != "flange":
            raise ValueError("AISC 358 connections frame to the column flange")
        layouts = PREQUALIFIED_LAYOUTS.get(s.connection)
        if layouts and mc.end_plate is not None and mc.end_plate.layout not in layouts:
            raise ValueError(f"AISC 358 {s.connection.value} takes the end-plate layouts "
                             f"{', '.join(lay.value for lay in layouts)}")
        from openconex.connections.moment.seismic import expected_ratios
        grades = [(mc.beam_grade if isinstance(mc.beam, str) else mc.beam.grade,
                   s.Ry_beam is not None and s.Rt_beam is not None, False),
                  (mc.column_grade if isinstance(mc.column, str) else mc.column.grade,
                   s.Ry_column is not None, False)]
        from openconex.io.moment_project import needs_plate_ratio
        tcp = mc.continuity_plate
        if needs_plate_ratio(mc, 0.0 if tcp is None else self.quantity(tcp, Kind.THICKNESS)):
            grades.append((mc.grade, s.Ry_plate is not None, True))
        for grade, given, plate in grades:
            if not given and expected_ratios(grade, plate) is None:
                raise ValueError(f"no AISC 341 R_y/R_t for {grade!r}: give them in seismic")
        if self.quantity(s.span, Kind.LENGTH) <= 0:
            raise ValueError("seismic span must be positive")
        if s.connection.value == "bfp":
            _validate_bfp(mc)
        if s.connection.value == "rbs" and s.rbs_c is not None and \
                self.quantity(s.rbs_c, Kind.LENGTH) <= 0:
            raise ValueError("seismic rbs_c must be positive")

    def moment_model(self) -> MomentConnection:
        """Engine model of the moment connection (:class:`MomentConnection`)."""
        from openconex.io.moment_project import moment_model
        return moment_model(self)

    def shear_model(self) -> ShearConnection:
        """Engine model of the shear connection (:class:`ShearConnection`)."""
        from openconex.io.shear_project import shear_model
        return shear_model(self)

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

    def bolt_library(self) -> dict[str, BoltGrade]:
        """Built-in AISC bolt grades plus the project-defined ones."""
        library = dict(BOLTS)
        for custom in self.bolts:
            name = custom.name.strip()
            if name in library:
                raise ValueError(f"bolt grade name already exists: {name!r}")
            Fnt = self.quantity(custom.Fnt, Kind.STRESS)
            Fnv_N = self.quantity(custom.Fnv_N, Kind.STRESS)
            Fnv_X = self.quantity(custom.Fnv_X, Kind.STRESS)
            Fu = self.quantity(custom.Fu, Kind.STRESS)
            if min(Fnt, Fnv_N, Fnv_X, Fu) <= 0:
                raise ValueError(f"bolt grade {name!r} needs positive stresses")
            Fy = None if custom.Fy is None else self.quantity(custom.Fy, Kind.STRESS)
            if Fy is not None and Fy <= 0:
                raise ValueError(f"bolt grade {name!r}: Fy must be positive")
            library[name] = BoltGrade(name=name, Fnt=Fnt, Fnv_N=Fnv_N, Fnv_X=Fnv_X,
                                      Fu=Fu, Fy=Fy)
        return library

    def electrode_library(self) -> dict[str, WeldElectrode]:
        """Built-in electrodes plus the project-defined ones."""
        library = dict(ELECTRODES)
        for custom in self.electrodes:
            name = custom.name.strip()
            if name in library:
                raise ValueError(f"electrode name already exists: {name!r}")
            FEXX = self.quantity(custom.FEXX, Kind.STRESS)
            if FEXX <= 0:
                raise ValueError(f"electrode {name!r} needs a positive FEXX")
            library[name] = WeldElectrode(name=name, FEXX=FEXX)
        return library

    # -- conversion to the engine model ------------------------------------------------
    def quantity(self, value: Quantity, kind: Kind) -> float:
        """Value typed in the project (text with unit, or number in project units), internal."""
        units = self.info.unit_system()
        if isinstance(value, (int, float)):
            return parse(str(value), kind, units)
        return parse(value, kind, units)

    def apply_base_plate_geometry(self, bp: BasePlate) -> None:
        """Write the plate, rod layout and anchor positions of ``bp`` into ``base_plate``.

        Used after an optimization by the CLI and the GUI; values are written as
        text in the project unit system.
        """
        data, units = self.require_base_plate(), self.info.unit_system()
        L, T = Kind.LENGTH, Kind.THICKNESS

        def text(value: float, kind: Kind) -> str:
            return format_value(value, kind, units, precision=4)

        data.N, data.B, data.tp = text(bp.N, L), text(bp.B, L), text(bp.tp, T)
        data.f, data.rod_spacing = text(bp.f, L), text(bp.rod_spacing, L)
        data.rod_diameter = text(bp.rod.diameter, L)
        data.rods_per_side = bp.rods_per_side

    def column_model(self,
                     library: dict[str, SteelGrade] | None = None) -> IShape | HSSShape:
        """Column section of the project: catalog label or generic dimensions."""
        library = library or self.material_library()
        bp = self.require_base_plate()
        section = bp.column
        L = Kind.LENGTH
        if isinstance(section, str):
            return aisc_shapes().get(section).to_column(bp.column_grade, materials=library)
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
        bp = self.require_base_plate()
        L, T = Kind.LENGTH, Kind.THICKNESS
        library = self.material_library()
        bolts = self.bolt_library()
        electrodes = self.electrode_library()
        column = self.column_model(library)
        edges = Edges(**{k: self.quantity(v, L) for k, v in bp.edges.items()})

        def dim(value: Quantity | None, kind: Kind, default: float = 0.0) -> float:
            return default if value is None else self.quantity(value, kind)

        return BasePlate(
            column=column, N=dim(bp.N, L), B=dim(bp.B, L), tp=dim(bp.tp, T),
            fc=self.quantity(bp.fc, Kind.STRESS),
            rod=BoltSpec(diameter=dim(bp.rod_diameter, L, self.quantity("1 in", L)),
                         grade=bp.rod_grade, bolts=bolts),
            f=dim(bp.f, L), rods_per_side=bp.rods_per_side,
            rod_spacing=self.quantity(bp.rod_spacing, L), hef=self.quantity(bp.hef, L),
            plate_grade=bp.plate_grade, pressure_model=bp.pressure_model,
            bearing_area_model=bp.bearing_area_model,
            rod_bending_lever=(None if bp.rod_bending_lever is None
                               else self.quantity(bp.rod_bending_lever, L)),
            reinforcement=self._reinforcement(), weak_base=self._weak_base(),
            pedestal_rebars=tuple(
                PedestalRebar(x=self.quantity(bar.x, L), y=self.quantity(bar.y, L),
                              diameter=self.quantity(bar.diameter, L))
                for bar in bp.pedestal_rebars),
            embedded_base=self._embedded_base(),
            bearing_area=(None if bp.bearing_area is None
                          else self.quantity(bp.bearing_area, Kind.AREA)),
            A2_over_A1=bp.A2_over_A1, edges=edges,
            pedestal_N=None if bp.pedestal_N is None else self.quantity(bp.pedestal_N, L),
            pedestal_B=self._pedestal_width(),
            pedestal=self._pedestal(),
            washer_thickness=(None if bp.washer_thickness is None
                              else self.quantity(bp.washer_thickness, T)),
            grout_pad=bp.grout_pad,
            flange_weld=None if bp.flange_weld is None else self.quantity(bp.flange_weld, T),
            electrode=bp.electrode, electrodes=electrodes,
            friction_mu=bp.friction_mu, cracked=bp.cracked, seismic=bp.seismic,
            shear_lug=self._shear_lug(electrodes), materials=library,
        )

    def _pedestal_width(self) -> float | None:
        bp = self.require_base_plate()
        if bp.pedestal is not None and bp.pedestal.shape == "round" and bp.pedestal_N is not None:
            return self.quantity(bp.pedestal_N, Kind.LENGTH)
        return None if bp.pedestal_B is None else self.quantity(bp.pedestal_B, Kind.LENGTH)

    def _pedestal(self) -> Pedestal | None:
        pedestal, L = self.require_base_plate().pedestal, Kind.LENGTH
        if pedestal is None:
            return None
        return Pedestal(
            height=self.quantity(pedestal.height, L),
            fy=self.quantity(pedestal.fy, Kind.STRESS), shape=pedestal.shape,
            tie_diameter=(0.0 if pedestal.tie_diameter is None
                          else self.quantity(pedestal.tie_diameter, L)),
            tie_spacing=(0.0 if pedestal.tie_spacing is None
                         else self.quantity(pedestal.tie_spacing, L)),
            tie_fy=self.quantity(pedestal.tie_fy, Kind.STRESS), tie_legs=pedestal.tie_legs,
            min_ratio=pedestal.min_ratio, lightweight=pedestal.lightweight)

    def _reinforcement(self) -> Reinforcement | None:
        reinforcement, L = self.require_base_plate().reinforcement, Kind.LENGTH
        if reinforcement is None:
            return None
        return Reinforcement(
            area=self.quantity(reinforcement.area, Kind.AREA),
            fy=self.quantity(reinforcement.fy, Kind.STRESS),
            db=self.quantity(reinforcement.db, L),
            clear_cover=self.quantity(reinforcement.clear_cover, L),
            anchor_to_bar=self.quantity(reinforcement.anchor_to_bar, L),
            le=self.quantity(reinforcement.le, L),
            bars=reinforcement.bars)

    def _weak_base(self) -> WeakBase | None:
        weak, L = self.require_base_plate().weak_base, Kind.LENGTH
        if weak is None:
            return None
        return WeakBase(reduced_diameter=self.quantity(weak.reduced_diameter, L),
                        stretch_length=self.quantity(weak.stretch_length, L),
                        Rt=weak.Rt)

    def _embedded_base(self) -> EmbeddedBase | None:
        embedded = self.require_base_plate().embedded_base
        if embedded is None:
            return None

        def layer(value: EmbeddedRebarInput | None) -> EmbeddedRebar | None:
            if value is None:
                return None
            return EmbeddedRebar(area=self.quantity(value.area, Kind.AREA),
                                 fy=self.quantity(value.fy, Kind.STRESS),
                                 depth=self.quantity(value.depth, Kind.LENGTH))

        return EmbeddedBase(
            embedment=self.quantity(embedded.embedment, Kind.LENGTH),
            foundation_width=self.quantity(embedded.foundation_width, Kind.LENGTH),
            face_plate_thickness=(0.0 if embedded.face_plate_thickness is None else
                                  self.quantity(embedded.face_plate_thickness,
                                                Kind.THICKNESS)),
            beta1=embedded.beta1,
            base_plate_width=(None if embedded.base_plate_width is None else
                              self.quantity(embedded.base_plate_width, Kind.LENGTH)),
            base_plate_thickness=(None if embedded.base_plate_thickness is None else
                                  self.quantity(embedded.base_plate_thickness,
                                                Kind.THICKNESS)),
            rebar_top=layer(embedded.rebar_top),
            rebar_bottom=layer(embedded.rebar_bottom),
            damage_limit=embedded.damage_limit, type=EmbeddedType(embedded.type),
            face_plate_weld=(None if embedded.face_plate_weld is None else
                             self.quantity(embedded.face_plate_weld, Kind.THICKNESS)))

    def _shear_lug(self, electrodes: dict[str, WeldElectrode]) -> ShearLug | None:
        lug, L = self.require_base_plate().shear_lug, Kind.LENGTH
        if lug is None:
            return None
        sides = [None if v is None else self.quantity(v, L) for v in lug.ca2[:2]]
        return ShearLug(width=self.quantity(lug.width, L),
                        embedment=self.quantity(lug.embedment, L),
                        thickness=self.quantity(lug.thickness, Kind.THICKNESS),
                        weld=self.quantity(lug.weld, Kind.THICKNESS), direction=lug.direction,
                        grade=lug.grade, FEXX=electrodes[lug.electrode].FEXX,
                        grout=self.quantity(self.require_base_plate().grout, L),
                        ca1=None if lug.ca1 is None else self.quantity(lug.ca1, L),
                        ca2=(sides[0] if sides else None,
                             sides[1] if len(sides) > 1 else None))

    def case_forces(self) -> dict[str, Forces]:
        F, M = Kind.FORCE, Kind.MOMENT
        return {c.name: Forces(P=self.quantity(c.P, F), V2=self.quantity(c.V, F),
                               M3=self.quantity(c.M, M), V3=self.quantity(c.V_weak, F),
                               M2=self.quantity(c.M_weak, M)) for c in self.cases}

    def column_forces(self) -> dict[str, Forces]:
        """Column story shear (``V2``) and axial force (``P``) of each case (panel zone)."""
        F = Kind.FORCE
        return {c.name: Forces(P=self.quantity(c.column_P, F), V2=self.quantity(c.column_V, F))
                for c in self.cases}

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
    from openconex.io.migrations import migrate
    return Project.model_validate(migrate(data, FORMAT_VERSION))


def save_project(project: Project, path: str | Path) -> None:
    """Write ``project`` in the current format version."""
    current = project.model_copy(update={"format_version": FORMAT_VERSION})
    Path(path).write_text(current.model_dump_json(indent=2, exclude_defaults=False) + "\n",
                          encoding="utf-8", newline="\n")
