# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""``splice`` section of a project file and its conversion to the engine."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from openconex.connections.splice.splice import (
    BeamSplice,
    ColumnSplice,
    FlangeSplice,
    WebSplice,
)
from openconex.core.model import BoltSpec
from openconex.io.moment_project import _section
from openconex.io.shear_project import BoltInput
from openconex.units import Kind

if TYPE_CHECKING:
    from openconex.io.project import Project, WSectionInput

__all__ = ["FlangeSpliceInput", "SpliceInput", "SpliceType", "WebSpliceInput",
           "splice_model"]

Quantity = str | float


class SpliceType(StrEnum):
    BEAM = "beam"
    COLUMN = "column"


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class FlangeSpliceInput(_Input):
    """Flange splice plates, the same at both flanges and on both sides of the splice."""

    bolt: BoltInput = Field(default_factory=BoltInput)
    rows: int = Field(ge=1)
    """Bolts in each of the two lines, on each side of the splice."""
    spacing: Quantity
    gage: Quantity
    width: Quantity
    """Outer plate width."""
    thickness: Quantity
    """Outer plate thickness."""
    lev_member: Quantity
    """Member end to the nearest bolt row."""
    lev_plate: Quantity
    """Farthest bolt row to the plate end."""
    inner_width: Quantity | None = None
    """Beam splices: width of each of the two inner plates (bolts in double shear)."""
    inner_thickness: Quantity | None = None


class WebSpliceInput(_Input):
    """Two web plates, one on each face of the web; bolts in double shear."""

    bolt: BoltInput = Field(default_factory=BoltInput)
    rows: int = Field(ge=1)
    """Bolts in each vertical line."""
    spacing: Quantity
    """Vertical spacing."""
    columns: int = Field(default=1, ge=1, le=4)
    """Vertical bolt lines on each side of the splice."""
    column_spacing: Quantity | None = None
    height: Quantity
    """Plate height (the bolts are centred on it)."""
    thickness: Quantity
    """Thickness of each plate."""
    lev_member: Quantity
    """Member end to the nearest bolt line."""
    leh_plate: Quantity
    """Farthest bolt line to the plate end."""


class SpliceInput(_Input):
    type: SpliceType
    beam: str | WSectionInput | None = None
    """Beam splices: the spliced beam."""
    beam_grade: str = "ASTM A992"
    upper: str | WSectionInput | None = None
    """Column splices: upper column."""
    lower: str | WSectionInput | None = None
    """Column splices: lower column (the fillers make up half the depth difference)."""
    column_grade: str = "ASTM A992"
    grade: str = "ASTM A572 Gr. 50"
    """Splice plates."""
    flange: FlangeSpliceInput
    web: WebSpliceInput | None = None
    """Web plates: required for beam splices, optional for columns (strong-axis shear)."""
    gap: Quantity | None = None
    """Gap between the member ends; omitted: 1/2 in. for beams, 0 for columns."""
    finished_ends: bool = True
    """Column splices: ends finished to bear; compression is transferred by bearing."""
    filler_developed: bool = False
    """Column splices: fillers extended and developed (§J5.2), no bolt reduction."""
    deformation_considered: bool = True

    def missing(self) -> list[str]:
        out: list[str] = []
        if self.type is SpliceType.BEAM:
            out += [n for n in ("beam", "web") if getattr(self, n) is None]
        else:
            out += [n for n in ("upper", "lower") if getattr(self, n) is None]
        f = self.flange
        if (f.inner_width is None) != (f.inner_thickness is None):
            out.append("flange.inner_width/inner_thickness")
        if self.web is not None and self.web.columns > 1 and self.web.column_spacing is None:
            out.append("web.column_spacing")
        return out


def splice_model(project: Project) -> BeamSplice | ColumnSplice:
    """Engine model of the project's splice."""
    sp = project.splice
    assert sp is not None
    L, T = Kind.LENGTH, Kind.THICKNESS
    steel = project.material_library()[sp.grade]
    bolts = project.bolt_library()

    def q(value, kind=L, default=0.0):
        return default if value is None else project.quantity(value, kind)

    def bolt(data: BoltInput) -> BoltSpec:
        return BoltSpec(diameter=q(data.diameter), grade=data.grade, threads=data.threads,
                        hole=data.hole, bolts=bolts)

    f = sp.flange
    flange = FlangeSplice(bolt=bolt(f.bolt), rows=f.rows, spacing=q(f.spacing),
                          gage=q(f.gage), width=q(f.width), thickness=q(f.thickness, T),
                          lev_member=q(f.lev_member), lev_plate=q(f.lev_plate), Fy=steel.Fy,
                          Fu=steel.Fu, inner_width=q(f.inner_width),
                          inner_thickness=q(f.inner_thickness, T))
    w = sp.web
    web = None if w is None else WebSplice(
        bolt=bolt(w.bolt), rows=w.rows, spacing=q(w.spacing), height=q(w.height),
        thickness=q(w.thickness, T), lev_member=q(w.lev_member), leh_plate=q(w.leh_plate),
        Fy=steel.Fy, Fu=steel.Fu, columns=w.columns, column_spacing=q(w.column_spacing))
    if sp.type is SpliceType.BEAM:
        beam, Sx = _section(project, sp.beam, sp.beam_grade)
        return BeamSplice(beam=beam, beam_Sx=Sx, flange=flange, web=web,
                          gap=q(sp.gap, default=project.quantity("0.5 in", L)),
                          deformation_considered=sp.deformation_considered)
    upper, _ = _section(project, sp.upper, sp.column_grade)
    lower, _ = _section(project, sp.lower, sp.column_grade)
    return ColumnSplice(upper=upper, lower=lower, flange=flange, web=web, gap=q(sp.gap),
                        finished_ends=sp.finished_ends, filler_developed=sp.filler_developed,
                        deformation_considered=sp.deformation_considered)
