# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Common entry point for the shear connections (beam end reactions).

A :class:`ShearConnection` wraps one connection of the library with the beam
and its optional cope. :func:`check_shear_connection` takes the end forces of
one load combination in the project convention (``V2`` the vertical reaction,
``P`` the axial force with compression positive) and runs the limit states of
the connection, the axial ones when the beam pulls on it, and those of the
coped beam end. Axial compression and axial tension on connections without an
axial procedure give a result that does not pass, so they are never ignored.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum

from openconex.core.checks import CheckResult
from openconex.core.loads import Forces, LoadCombination, Method, combine
from openconex.core.model import IShape
from openconex.kernel.design import Calc
from openconex.units import Kind

from .coped_beam import CopedBeam, check_coped_beam
from .double_angle import DoubleAngle, check_double_angle
from .double_angle_axial import AxialBeam, check_double_angle_axial
from .end_plate import EndPlate, check_end_plate
from .extended_single_plate import ExtendedSinglePlate, check_extended_single_plate
from .seated import SeatedAngle, check_seated
from .single_plate import SinglePlate, check_single_plate
from .single_plate_axial import check_single_plate_axial
from .stiffened_seat import StiffenedSeat, check_stiffened_seat

__all__ = ["ShearConnection", "ShearType", "check_shear_connection", "check_shear_envelope"]


class ShearType(StrEnum):
    DOUBLE_ANGLE = "double_angle"
    SINGLE_PLATE = "single_plate"
    EXTENDED_SINGLE_PLATE = "extended_single_plate"
    END_PLATE = "end_plate"
    SEATED = "seated"
    STIFFENED_SEAT = "stiffened_seat"


ELEMENTS = {
    ShearType.DOUBLE_ANGLE: DoubleAngle,
    ShearType.SINGLE_PLATE: SinglePlate,
    ShearType.EXTENDED_SINGLE_PLATE: ExtendedSinglePlate,
    ShearType.END_PLATE: EndPlate,
    ShearType.SEATED: SeatedAngle,
    ShearType.STIFFENED_SEAT: StiffenedSeat,
}

AXIAL_TYPES = {ShearType.DOUBLE_ANGLE, ShearType.SINGLE_PLATE}


@dataclass(frozen=True)
class ShearConnection:
    type: ShearType
    element: (DoubleAngle | SinglePlate | ExtendedSinglePlate | EndPlate | SeatedAngle
              | StiffenedSeat)
    beam: IShape | None = None
    support: IShape | None = None
    support_element: str = "flange"
    """``flange`` or ``web`` of the support."""
    cope: CopedBeam | None = None
    axial_beam: AxialBeam | None = None
    """Beam section for the beam limit states of the double angle under axial load."""
    gage: float = 0.0
    """Double angle: bolt gage across the outstanding legs (axial load)."""
    outstanding_leg: float = 0.0
    """Double angle: width of the outstanding legs (axial load)."""
    beam_leh: float | None = None
    """Double angle: beam web edge distance before the underrun (axial load)."""

    def __post_init__(self) -> None:
        if not isinstance(self.element, ELEMENTS[self.type]):
            raise TypeError(f"{self.type.value} needs a {ELEMENTS[self.type].__name__}")

    @property
    def welded_double_angle(self) -> bool:
        da = self.element
        return isinstance(da, DoubleAngle) and (da.support_weld > 0 or da.beam_weld > 0)


def _unsupported(key: str, value: float, method: Method, combo: str,
                 clause: str) -> CheckResult:
    c = Calc(method, combo)
    c.step("P", "", value, Kind.FORCE, clause)
    return c.result(f"shear_connection.{key}", clause, abs(value), 0.0, Kind.FORCE)


def check_shear_connection(conn: ShearConnection, forces: Forces, method: Method,
                           combo: str = "") -> list[CheckResult]:
    """All limit states for the end forces of one combination."""
    V = abs(forces.V2)
    N = max(-forces.P, 0.0)
    out: list[CheckResult] = []
    if forces.P > 0:
        out.append(_unsupported("axial_compression", forces.P, method, combo,
                                "OpenConex (axial compression not implemented)"))
    el = conn.element
    if N > 0 and (conn.type not in AXIAL_TYPES or conn.welded_double_angle):
        out.append(_unsupported("axial_unsupported", -N, method, combo,
                                "OpenConex (axial tension not implemented for this connection)"))
        N = 0.0
    if conn.type is ShearType.DOUBLE_ANGLE:
        if N > 0:
            out += check_double_angle_axial(el, V, N, method, conn.gage, conn.outstanding_leg,
                                            combo, beam_leh=conn.beam_leh,
                                            beam=conn.axial_beam)
        else:
            out += check_double_angle(el, V, method, combo)
    elif conn.type is ShearType.SINGLE_PLATE:
        out += (check_single_plate_axial(el, V, N, method, combo) if N > 0
                else check_single_plate(el, V, method, combo))
    elif conn.type is ShearType.EXTENDED_SINGLE_PLATE:
        out += check_extended_single_plate(el, V, method, combo)
    elif conn.type is ShearType.END_PLATE:
        out += check_end_plate(el, V, method, combo)
    elif conn.type is ShearType.SEATED:
        out += check_seated(el, V, method, combo)
    else:
        out += check_stiffened_seat(el, V, method, combo)
    if conn.cope is not None:
        out += check_coped_beam(conn.cope, V, method, combo)
    return out


def check_shear_envelope(conn: ShearConnection, combinations: Iterable[LoadCombination],
                         case_forces: Mapping[str, Forces]) -> list[CheckResult]:
    """Run every combination and return all the results."""
    results: list[CheckResult] = []
    for combo in combinations:
        results += check_shear_connection(conn, combine(combo, case_forces), combo.method,
                                          combo.name)
    return results
