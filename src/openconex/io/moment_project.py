# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""``moment_connection`` section of a project file and its conversion to the engine."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from openconex.connections.moment.end_plate import EXTENDED, EndPlate, EndPlateLayout
from openconex.connections.moment.fr_moment import (
    ColumnFace,
    FlangeDetail,
    FlangePlate,
    MomentConnection,
    WebPlate,
)
from openconex.core.model import BoltSpec, IShape
from openconex.core.shapes import aisc_shapes
from openconex.io.shear_project import BoltInput
from openconex.units import Kind

if TYPE_CHECKING:
    from openconex.io.project import Project, WSectionInput

__all__ = ["EndPlateInput", "FlangePlateInput", "MomentConnectionInput", "WebPlateInput",
           "moment_model"]

Quantity = str | float


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class WebPlateInput(_Input):
    bolt: BoltInput = Field(default_factory=BoltInput)
    rows: int = Field(ge=1)
    spacing: Quantity
    length: Quantity
    thickness: Quantity
    lev: Quantity
    """Plate edge to the bottom bolt."""
    leh: Quantity
    """Bolt line to the plate edge."""
    weld: Quantity
    """Fillet weld on each side of the plate at the column flange."""


class FlangePlateInput(_Input):
    width: Quantity
    thickness: Quantity
    weld_to_column: Quantity
    unbraced_length: Quantity = 0.0
    """Length for the compression check (bolt spacing, or free length to the welds)."""
    weld_to_beam: Quantity | None = None
    """Welded plates: fillet weld size along the beam flange."""
    weld_length: Quantity | None = None
    """Welded plates: length of each longitudinal weld."""
    transverse_weld: bool = False


class EndPlateInput(_Input):
    """Moment end plate (AISC Design Guide 16); two bolts per row."""

    layout: EndPlateLayout
    bolt: BoltInput = Field(default_factory=BoltInput)
    width: Quantity
    thickness: Quantity
    gage: Quantity
    pf: Quantity
    """First bolt row inside the flanges to the inner face of the tension flange."""
    pb: Quantity | None = None
    """Pitch between the bolt rows inside the flanges (two or more rows)."""
    pf_o: Quantity | None = None
    """Extended plates: outer bolt row to the outer face of the tension flange."""
    pext: Quantity | None = None
    """Extended plates: extension beyond the outer face of the tension flange."""
    ps_o: Quantity | None = None
    """flush_4_stiffened_between: outer bolt row to the stiffener."""
    stiffener_thickness: Quantity | None = None
    """flush_4_stiffened_between: stiffener thickness."""
    ps: Quantity | None = None
    """flush_4_stiffened_inside: bolt row to the stiffener."""
    snug_tight: bool = False
    pretension: Quantity | None = None
    """Bolt pretension T_b instead of AISC 360-22 Table J3.1."""
    web_weld: Quantity | None = None
    """Fillet weld on each side of the beam web (omitted: CJP groove weld)."""
    flange_weld: Quantity | None = None
    """Fillet weld at the beam flanges (omitted: CJP groove weld)."""
    weld_reinforcement: Quantity | None = None
    """CJP flange welds: reinforcing fillet leg (Design Guide 4: N = t_f + 2w)."""
    symmetric: bool = True
    """Same bolt pattern at both flanges; otherwise two bolts at the compression flange."""

    def missing(self) -> list[str]:
        layout = self.layout
        need = []
        if layout not in (EndPlateLayout.FLUSH_2, EndPlateLayout.EXTENDED_4,
                          EndPlateLayout.EXTENDED_4_STIFFENED):
            need.append("pb")
        if layout in EXTENDED:
            need += ["pf_o", "pext"]
        if layout is EndPlateLayout.FLUSH_4_STIFFENED_BETWEEN:
            need += ["ps_o", "stiffener_thickness"]
        if layout is EndPlateLayout.FLUSH_4_STIFFENED_INSIDE:
            need.append("ps")
        return [f"end_plate.{n}" for n in need if getattr(self, n) is None]


class MomentConnectionInput(_Input):
    type: FlangeDetail
    beam: str | WSectionInput
    beam_grade: str = "ASTM A992"
    column: str | WSectionInput
    """Column; the connection is to its flange."""
    column_grade: str = "ASTM A992"
    grade: str = "ASTM A572 Gr. 50"
    """Flange and web plates."""
    electrode: str = "E70XX"
    web: WebPlateInput | None = None
    """Single plate on the web (all types except ``end_plate``)."""
    end_plate: EndPlateInput | None = None
    """``end_plate``: the moment end plate."""
    top: FlangePlateInput | None = None
    """Flange plate (bolted: both plates; welded: the top, tension, plate)."""
    bottom: FlangePlateInput | None = None
    """Welded: the bottom plate. Bolted: optional, defaults to ``top``."""
    bolt: BoltInput | None = None
    """Bolted flange plates: flange bolts."""
    rows: int = Field(default=0, ge=0)
    """Bolted flange plates: bolts in each of the two lines."""
    spacing: Quantity | None = None
    gage: Quantity | None = None
    plate_lev: Quantity | None = None
    beam_lev: Quantity | None = None
    underrun: Quantity = "0.25 in"
    deformation_considered: bool = True
    column_near_end: bool = False
    two_sided: bool = False
    support: ColumnFace = ColumnFace.FLANGE
    """``flange`` or ``web`` of the column (web: welded_flange or bolted_flange_plate)."""
    plate_extension: Quantity = "3/4 in"
    """Column web: extension of the connection plates past the column flange tips."""
    panel_zone: bool = False
    """Check the column panel zone (§J10.6) with ``column_V`` and ``column_P`` of the cases."""
    panel_zone_inelastic: bool = False
    """Panel zone deformation considered in the stability analysis (Eq. J10-11, J10-12)."""
    doubler_plate: Quantity | None = None
    """Total thickness of the web doubler plates (steel ``grade``)."""
    continuity_plate: Quantity | None = None
    """Thickness of the column continuity plates (transverse stiffeners), a pair at each
    beam flange (steel ``grade``)."""
    continuity_plate_width: Quantity | None = None
    """Width of each stiffener; omitted: (b_fc - t_wc)/2."""
    continuity_plate_clip: Quantity = "3/4 in"
    continuity_plate_full_depth: bool = True
    continuity_plate_length: Quantity | None = None
    """Omitted: the clear web depth (full depth) or half of it (partial depth)."""
    continuity_plate_weld: Quantity | None = None
    """Double-sided fillet weld to the column flanges; omitted: CJP."""
    continuity_plate_web_weld: Quantity | None = None
    """Double-sided fillet weld to the column web; omitted: not checked."""
    doubler_weld: Quantity | None = None
    """Fillet weld of the doubler plate to the column flanges; omitted: CJP."""

    def missing(self) -> list[str]:
        missing: list[str] = []
        if self.type is FlangeDetail.END_PLATE:
            if self.end_plate is None:
                return ["end_plate"]
            return self.end_plate.missing()
        if self.web is None:
            missing.append("web")
        if self.support is ColumnFace.WEB and self.type is FlangeDetail.WELDED_FLANGE:
            missing += [n for n in ("top", "bottom") if getattr(self, n) is None]
        if self.type is FlangeDetail.BOLTED_FLANGE_PLATE:
            missing += [n for n in ("top", "bolt", "spacing", "gage", "plate_lev", "beam_lev")
                        if getattr(self, n) is None]
            if self.rows < 1:
                missing.append("rows")
        elif self.type is FlangeDetail.WELDED_FLANGE_PLATE:
            for name in ("top", "bottom"):
                plate = getattr(self, name)
                if plate is None:
                    missing.append(name)
                elif plate.weld_to_beam is None or plate.weld_length is None:
                    missing.append(f"{name}.weld_to_beam/weld_length")
        return missing


def _section(project: Project, section: str | WSectionInput, grade: str) -> tuple[IShape, float]:
    """I-shape and elastic section modulus S_x."""
    library = project.material_library()
    L = Kind.LENGTH
    if isinstance(section, str):
        shape = aisc_shapes().get(section)
        return shape.to_ishape(grade, materials=library), shape["Sx"]
    s = IShape(name=section.label(), d=project.quantity(section.d, L),
               bf=project.quantity(section.bf, L), tf=project.quantity(section.tf, L),
               tw=project.quantity(section.tw, L), k_des=project.quantity(section.k_des, L),
               grade=section.grade, materials=library)
    inertia = (s.bf * s.d**3 - (s.bf - s.tw) * (s.d - 2 * s.tf) ** 3) / 12
    return s, inertia / (s.d / 2)


def moment_model(project: Project) -> MomentConnection:
    """Engine model of the project's moment connection."""
    mc = project.moment_connection
    assert mc is not None
    L, T = Kind.LENGTH, Kind.THICKNESS
    library = project.material_library()
    bolts = project.bolt_library()

    def q(value, kind=L, default=0.0):
        return default if value is None else project.quantity(value, kind)

    def bolt(data: BoltInput) -> BoltSpec:
        return BoltSpec(diameter=q(data.diameter), grade=data.grade, threads=data.threads,
                        hole=data.hole, bolts=bolts)

    def plate(data: FlangePlateInput | None) -> FlangePlate | None:
        if data is None:
            return None
        return FlangePlate(width=q(data.width), thickness=q(data.thickness, T),
                           weld_to_column=q(data.weld_to_column, T),
                           unbraced_length=q(data.unbraced_length),
                           weld_to_beam=q(data.weld_to_beam, T),
                           weld_length=q(data.weld_length),
                           transverse_weld=data.transverse_weld)

    beam, Sx = _section(project, mc.beam, mc.beam_grade)
    column, _ = _section(project, mc.column, mc.column_grade)
    steel = library[mc.grade]
    w = mc.web
    web = None if w is None else WebPlate(
        bolt=bolt(w.bolt), rows=w.rows, spacing=q(w.spacing), length=q(w.length),
        thickness=q(w.thickness, T), lev=q(w.lev), leh=q(w.leh), weld=q(w.weld, T),
        Fy=steel.Fy, Fu=steel.Fu)
    end_plate = None
    e = mc.end_plate
    if mc.type is FlangeDetail.END_PLATE and e is not None:
        end_plate = EndPlate(
            layout=e.layout, bolt=bolt(e.bolt), width=q(e.width), thickness=q(e.thickness, T),
            gage=q(e.gage), pf=q(e.pf), Fy=steel.Fy, Fu=steel.Fu, pb=q(e.pb), pf_o=q(e.pf_o),
            pext=q(e.pext), ps_o=q(e.ps_o), stiffener_thickness=q(e.stiffener_thickness, T),
            ps=q(e.ps), snug_tight=e.snug_tight,
            pretension=None if e.pretension is None else project.quantity(e.pretension,
                                                                           Kind.FORCE),
            web_weld=q(e.web_weld, T), flange_weld=q(e.flange_weld, T),
            weld_reinforcement=q(e.weld_reinforcement, T), symmetric=e.symmetric)
    top = plate(mc.top)
    bottom = plate(mc.bottom)
    if mc.type is FlangeDetail.BOLTED_FLANGE_PLATE and bottom is None:
        bottom = top
    return MomentConnection(
        detail=mc.type, beam=beam, beam_Sx=Sx, column=column, web=web, plate_Fy=steel.Fy,
        plate_Fu=steel.Fu, top=top, bottom=bottom,
        bolt=bolt(mc.bolt) if mc.bolt is not None else None, rows=mc.rows,
        spacing=q(mc.spacing), gage=q(mc.gage), plate_lev=q(mc.plate_lev),
        beam_lev=q(mc.beam_lev), underrun=q(mc.underrun),
        FEXX=project.electrode_library()[mc.electrode].FEXX,
        deformation_considered=mc.deformation_considered, column_near_end=mc.column_near_end,
        two_sided=mc.two_sided, end_plate=end_plate,
        continuity_plate=q(mc.continuity_plate, T),
        continuity_plate_width=q(mc.continuity_plate_width),
        continuity_plate_clip=q(mc.continuity_plate_clip),
        continuity_plate_full_depth=mc.continuity_plate_full_depth,
        continuity_plate_length=q(mc.continuity_plate_length),
        continuity_plate_weld=q(mc.continuity_plate_weld, T),
        continuity_plate_web_weld=q(mc.continuity_plate_web_weld, T),
        doubler_weld=q(mc.doubler_weld, T), panel_zone=mc.panel_zone, support=mc.support,
        plate_extension=q(mc.plate_extension),
        panel_zone_inelastic=mc.panel_zone_inelastic, doubler_plate=q(mc.doubler_plate, T))
