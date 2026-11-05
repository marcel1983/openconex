# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""``shear_connection`` section of a project file and its conversion to the engine.

One flat input model serves every connection type; ``REQUIRED`` lists the
fields each type needs and the converter only reads those that apply.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field

from openconex.connections.shear.check import ShearConnection, ShearType
from openconex.connections.shear.coped_beam import CopedBeam
from openconex.connections.shear.double_angle import DoubleAngle, _hole_net
from openconex.connections.shear.double_angle_axial import AxialBeam
from openconex.connections.shear.end_plate import EndPlate
from openconex.connections.shear.extended_single_plate import ExtendedSinglePlate
from openconex.connections.shear.seated import SeatedAngle
from openconex.connections.shear.single_plate import SinglePlate
from openconex.connections.shear.stiffened_seat import StiffenedSeat
from openconex.core.model import BoltSpec, HoleType, IShape, Threads
from openconex.core.shapes import aisc_shapes
from openconex.units import Kind

if TYPE_CHECKING:
    from openconex.io.project import Project, WSectionInput

__all__ = ["REQUIRED", "BoltInput", "CopeInput", "ShearConnectionInput", "shear_model"]

Quantity = str | float


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class BoltInput(_Input):
    diameter: Quantity = "3/4 in"
    grade: str = "ASTM F3125 Gr. A325"
    threads: Threads = Threads.INCLUDED
    hole: HoleType = HoleType.STANDARD


class CopeInput(_Input):
    c: Quantity
    """Cope length."""
    dc: Quantity
    """Cope depth at the top flange."""
    dc_bottom: Quantity = 0.0
    """Cope depth at the bottom flange."""
    setback: Quantity = "0.5 in"
    lev: Quantity | None = None
    """Top of the coped web to the top bolt; with ``leh`` enables the web block shear."""
    leh: Quantity | None = None
    """End of the beam to the bolt line nearest to it."""


REQUIRED: dict[ShearType, tuple[str, ...]] = {
    ShearType.DOUBLE_ANGLE: ("rows", "spacing", "length", "thickness", "lev"),
    ShearType.SINGLE_PLATE: ("rows", "spacing", "length", "thickness", "lev", "leh", "a",
                             "weld"),
    ShearType.EXTENDED_SINGLE_PLATE: ("rows", "spacing", "length", "thickness", "lev", "leh",
                                      "a", "weld"),
    ShearType.END_PLATE: ("rows", "spacing", "length", "thickness", "lev", "leh", "weld"),
    ShearType.SEATED: ("length", "thickness", "leg"),
    ShearType.STIFFENED_SEAT: ("width", "length", "thickness", "weld"),
}


class ShearConnectionInput(_Input):
    type: ShearType
    beam: str | WSectionInput
    """AISC label (e.g. ``W18X50``) or a generic W section."""
    beam_grade: str = "ASTM A992"
    support: str | WSectionInput
    """Column or girder: AISC label or generic W section."""
    support_grade: str = "ASTM A992"
    support_element: Literal["flange", "web"] = "flange"
    """Part of the support the connection is attached to (its thickness is used)."""
    grade: str = "ASTM A572 Gr. 50"
    """Plate, angle or stiffener material."""
    electrode: str = "E70XX"
    bolt: BoltInput = Field(default_factory=BoltInput)
    deformation_considered: bool = True
    cope: CopeInput | None = None
    rows: int | None = Field(default=None, ge=1)
    """Bolts per vertical line (rows of two bolts for the end plate)."""
    lines: int = Field(default=1, ge=1, le=2)
    """Extended single plate: vertical bolt lines."""
    spacing: Quantity | None = None
    gage: Quantity | None = None
    """Extended single plate: distance between bolt lines. Double angle: gage across the
    outstanding legs (axial load)."""
    length: Quantity | None = None
    thickness: Quantity | None = None
    lev: Quantity | None = None
    leh: Quantity | None = None
    """Plate edge distance; double angle: leg on the beam web."""
    leh_support: Quantity | None = None
    """Double angle: horizontal edge distance on the outstanding legs."""
    a: Quantity | None = None
    """Single plate: weld line to the (first) bolt line."""
    weld: Quantity | None = None
    support_weld: Quantity | None = None
    """Double angle (welds B) or seat angle: weld to the support."""
    beam_weld: Quantity | None = None
    """Double angle: welds A to the beam web."""
    beam_leg: Quantity | None = None
    """Double angle: width of the leg on the beam web."""
    outstanding_leg: Quantity | None = None
    """Double angle: width of the outstanding legs."""
    beam_leh: Quantity | None = None
    """End of the beam to the bolt line (web tearout under axial load)."""
    leg: Quantity | None = None
    """Seat angle: outstanding leg."""
    vertical_leg: Quantity | None = None
    """Seat angle: vertical leg (welded seat)."""
    bolts: int = Field(default=4, ge=1)
    """Seat angle: bolts through the vertical leg."""
    bearing_length: Quantity | None = None
    width: Quantity | None = None
    """Stiffened seat: stiffener width."""
    two_sided: bool = False
    """Stiffened seat: seats on both sides of the support web."""
    seat_plate_width: Quantity | None = None
    """Stiffened seat: seat plate width across the beam (default: W + 1 in)."""
    seat_plate_thickness: Quantity | None = None
    """Stiffened seat: seat plate thickness (default: 3/8 in)."""
    seat_plate_weld: Quantity | None = None
    """Stiffened seat: weld of the seat plate to the stiffener (default: 5/16 in)."""
    top_angle_leg: Quantity | None = None
    """Seat: outstanding leg of the stability angle (default: 4 in)."""
    top_angle_thickness: Quantity | None = None
    """Seat: thickness of the stability angle (default: 1/4 in)."""
    top_angle_length: Quantity | None = None
    """Seat: length of the stability angle along the beam (default: 4 in)."""
    top_angle_bolts: int = Field(default=2, ge=2)
    """Seat: bolts through each leg of the stability angle (welded seats use the weld)."""
    top_angle_weld: Quantity | None = None
    """Seat: weld of the stability angle to the support (default: 3/16 in)."""
    beam_area: Quantity | None = None
    """Gross area of a generic beam (axial checks of the double angle)."""

    def missing(self) -> list[str]:
        missing = [name for name in REQUIRED[self.type] if getattr(self, name) is None]
        if self.type is ShearType.DOUBLE_ANGLE:
            if self.beam_weld is None and self.leh is None:
                missing.append("leh")
            if self.beam_weld is not None and self.beam_leg is None:
                missing.append("beam_leg")
            if self.support_weld is None and self.leh_support is None:
                missing.append("leh_support")
            if self.support_weld is not None and self.outstanding_leg is None:
                missing.append("outstanding_leg")
        if self.type is ShearType.EXTENDED_SINGLE_PLATE and self.lines == 2 \
                and self.gage is None:
            missing.append("gage")
        if self.type is ShearType.SEATED and self.support_weld is not None \
                and self.vertical_leg is None:
            missing.append("vertical_leg")
        return missing


def _section(project: Project, section: str | WSectionInput, grade: str) -> tuple[IShape, float]:
    """I-shape and gross area of the beam or the support."""
    library = project.material_library()
    L = Kind.LENGTH
    if isinstance(section, str):
        shape = aisc_shapes().get(section)
        return shape.to_ishape(grade, materials=library), shape["A"]
    ishape = IShape(name=section.label(), d=project.quantity(section.d, L),
                    bf=project.quantity(section.bf, L), tf=project.quantity(section.tf, L),
                    tw=project.quantity(section.tw, L), k_des=project.quantity(section.k_des, L),
                    grade=section.grade, materials=library)
    area = 2 * ishape.bf * ishape.tf + (ishape.d - 2 * ishape.tf) * ishape.tw
    return ishape, area


def shear_model(project: Project) -> ShearConnection:
    """Engine model of the project's shear connection."""
    sc = project.shear_connection
    assert sc is not None
    L, T = Kind.LENGTH, Kind.THICKNESS
    library = project.material_library()

    def q(value, kind=L, default=0.0):
        return default if value is None else project.quantity(value, kind)

    beam, beam_area = _section(project, sc.beam, sc.beam_grade)
    support, _ = _section(project, sc.support, sc.support_grade)
    if sc.beam_area is not None:
        beam_area = q(sc.beam_area, Kind.AREA)
    plate = library[sc.grade]
    FEXX = project.electrode_library()[sc.electrode].FEXX
    bolt = BoltSpec(diameter=q(sc.bolt.diameter), grade=sc.bolt.grade, threads=sc.bolt.threads,
                    hole=sc.bolt.hole, bolts=project.bolt_library())
    support_t = support.tf if sc.support_element == "flange" else support.tw
    bm, sp = beam.material, support.material
    common = {"beam_tw": beam.tw, "beam_Fu": bm.Fu}
    kind = sc.type
    if kind is ShearType.DOUBLE_ANGLE:
        el = DoubleAngle(
            bolt=bolt, rows=sc.rows, spacing=q(sc.spacing), length=q(sc.length),
            thickness=q(sc.thickness, T), lev=q(sc.lev), leh_beam=q(sc.leh),
            leh_support=q(sc.leh_support), angle_Fy=plate.Fy, angle_Fu=plate.Fu,
            support_t=support_t, support_Fu=sp.Fu,
            deformation_considered=sc.deformation_considered,
            support_weld=q(sc.support_weld, T), weld_e=q(sc.outstanding_leg), FEXX=FEXX,
            beam_weld=q(sc.beam_weld, T), beam_leg=q(sc.beam_leg), **common)
    elif kind is ShearType.SINGLE_PLATE:
        el = SinglePlate(
            bolt=bolt, rows=sc.rows, spacing=q(sc.spacing), length=q(sc.length),
            thickness=q(sc.thickness, T), lev=q(sc.lev), leh=q(sc.leh), a=q(sc.a),
            plate_Fy=plate.Fy, plate_Fu=plate.Fu, weld=q(sc.weld, T), support_t=support_t,
            support_Fu=sp.Fu, deformation_considered=sc.deformation_considered,
            beam_leh=None if sc.beam_leh is None else q(sc.beam_leh), **common)
    elif kind is ShearType.EXTENDED_SINGLE_PLATE:
        el = ExtendedSinglePlate(
            bolt=bolt, rows=sc.rows, spacing=q(sc.spacing), length=q(sc.length),
            thickness=q(sc.thickness, T), lev=q(sc.lev), leh=q(sc.leh), a=q(sc.a),
            plate_Fy=plate.Fy, plate_Fu=plate.Fu, weld=q(sc.weld, T), support_t=support_t,
            support_Fu=sp.Fu, lines=sc.lines, gage=q(sc.gage),
            deformation_considered=sc.deformation_considered, **common)
    elif kind is ShearType.END_PLATE:
        el = EndPlate(
            bolt=bolt, rows=sc.rows, spacing=q(sc.spacing), length=q(sc.length),
            thickness=q(sc.thickness, T), lev=q(sc.lev), leh=q(sc.leh), plate_Fy=plate.Fy,
            plate_Fu=plate.Fu, weld=q(sc.weld, T), support_t=support_t, support_Fu=sp.Fu,
            FEXX=FEXX, deformation_considered=sc.deformation_considered, **common)
    elif kind is ShearType.SEATED:
        top = {}
        for name, unit in (("top_angle_leg", L), ("top_angle_thickness", T),
                           ("top_angle_length", L), ("top_angle_weld", T)):
            value = getattr(sc, name)
            if value is not None:
                top[name] = q(value, unit)
        el = SeatedAngle(
            length=q(sc.length), thickness=q(sc.thickness, T), leg=q(sc.leg), Fy=plate.Fy,
            bolt=bolt, bolts=sc.bolts, support_t=support_t, support_Fu=sp.Fu,
            angle_Fu=plate.Fu, beam_d=beam.d, beam_tw=beam.tw, beam_tf=beam.tf,
            beam_kdes=beam.k_des, beam_Fy=bm.Fy, support_weld=q(sc.support_weld, T),
            vertical_leg=q(sc.vertical_leg), FEXX=FEXX, top_angle_bolts=sc.top_angle_bolts,
            bearing_length=None if sc.bearing_length is None else q(sc.bearing_length),
            **top)
    else:
        extra = {}
        for name, unit in (("seat_plate_width", L), ("seat_plate_thickness", T),
                           ("seat_plate_weld", T), ("top_angle_leg", L),
                           ("top_angle_thickness", T), ("top_angle_length", L),
                           ("top_angle_weld", T)):
            value = getattr(sc, name)
            if value is not None:
                extra[name] = q(value, unit)
        el = StiffenedSeat(
            width=q(sc.width), length=q(sc.length), thickness=q(sc.thickness, T),
            stiffener_Fy=plate.Fy, weld=q(sc.weld, T), beam_d=beam.d, beam_tw=beam.tw,
            beam_tf=beam.tf, beam_kdes=beam.k_des, beam_Fy=bm.Fy, support_t=support_t,
            support_Fu=sp.Fu, two_sided=sc.two_sided, FEXX=FEXX,
            top_angle_bolts=sc.top_angle_bolts, **extra)
    cope = None
    if sc.cope is not None:
        bolted = kind in {ShearType.SINGLE_PLATE, ShearType.EXTENDED_SINGLE_PLATE} or (
            kind is ShearType.DOUBLE_ANGLE and sc.beam_weld is None)
        block = bolted and sc.cope.lev is not None and sc.cope.leh is not None
        cope = CopedBeam(
            d=beam.d, tw=beam.tw, bf=beam.bf, tf=beam.tf, Fy=bm.Fy, Fu=bm.Fu,
            c=q(sc.cope.c), dc=q(sc.cope.dc), dc_bottom=q(sc.cope.dc_bottom),
            setback=q(sc.cope.setback),
            rows=sc.rows if bolted else 0,
            lines=sc.lines if kind is ShearType.EXTENDED_SINGLE_PLATE else 1,
            spacing=q(sc.spacing), lev=q(sc.cope.lev) if block else 0.0,
            leh=q(sc.cope.leh) if block else 0.0,
            gage=q(sc.gage) if kind is ShearType.EXTENDED_SINGLE_PLATE else 0.0,
            hole=_hole_net(bolt) if bolted else 0.0)
    return ShearConnection(
        type=kind, element=el, beam=beam, support=support,
        support_element=sc.support_element, cope=cope,
        axial_beam=AxialBeam(d=beam.d, tf=beam.tf, Ag=beam_area, Fy=bm.Fy),
        gage=q(sc.gage), outstanding_leg=q(sc.outstanding_leg),
        beam_leh=None if sc.beam_leh is None else q(sc.beam_leh))
