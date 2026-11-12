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

from .bent_plate import SkewedBentPlate, check_skewed_bent_plate
from .bolts_fit import check_edge, check_rows, check_spacing, fail, fmt_length
from .coped_beam import CopedBeam, check_coped_beam
from .double_angle import DoubleAngle, check_double_angle, check_shared_support_bolts
from .double_angle_axial import AxialBeam, check_double_angle_axial
from .end_plate import EndPlate, check_end_plate
from .extended_single_plate import ExtendedSinglePlate, check_extended_single_plate
from .extended_single_plate_axial import check_extended_single_plate_axial
from .seated import SeatedAngle, check_seated
from .single_plate import SinglePlate, check_single_plate
from .single_plate_axial import check_single_plate_axial
from .stiffened_seat import StiffenedSeat, check_stiffened_seat

__all__ = ["ShearConnection", "ShearType", "check_shear_connection",
           "check_shear_envelope", "validate_shear_connection"]


class ShearType(StrEnum):
    DOUBLE_ANGLE = "double_angle"
    SINGLE_PLATE = "single_plate"
    EXTENDED_SINGLE_PLATE = "extended_single_plate"
    END_PLATE = "end_plate"
    SEATED = "seated"
    STIFFENED_SEAT = "stiffened_seat"
    SKEWED_BENT_PLATE = "skewed_bent_plate"


ELEMENTS = {
    ShearType.DOUBLE_ANGLE: DoubleAngle,
    ShearType.SINGLE_PLATE: SinglePlate,
    ShearType.EXTENDED_SINGLE_PLATE: ExtendedSinglePlate,
    ShearType.END_PLATE: EndPlate,
    ShearType.SEATED: SeatedAngle,
    ShearType.STIFFENED_SEAT: StiffenedSeat,
    ShearType.SKEWED_BENT_PLATE: SkewedBentPlate,
}

AXIAL_TYPES = {ShearType.DOUBLE_ANGLE, ShearType.SINGLE_PLATE,
               ShearType.EXTENDED_SINGLE_PLATE}


@dataclass(frozen=True)
class ShearConnection:
    type: ShearType
    element: (DoubleAngle | SinglePlate | ExtendedSinglePlate | EndPlate | SeatedAngle
              | StiffenedSeat | SkewedBentPlate)
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
    offset: float = 0.0
    """Double angle: beam centreline offset for a shared support bolt row (II.A-9)."""

    def __post_init__(self) -> None:
        if not isinstance(self.element, ELEMENTS[self.type]):
            raise TypeError(f"{self.type.value} needs a {ELEMENTS[self.type].__name__}")

    @property
    def welded_double_angle(self) -> bool:
        da = self.element
        return isinstance(da, DoubleAngle) and (da.support_weld > 0 or da.beam_weld > 0)


def validate_shear_connection(conn: ShearConnection) -> None:
    """Reject bolt groups that do not fit the connected element.

    The drawing and the 3D model are generated from these fields; a bolt row
    outside the plate or angle, or an edge distance below AISC 360-22
    Table J3.4, must stop the calculation with a message that says what to
    correct.  Welded legs have no holes and are not checked.
    """
    el = conn.element
    if isinstance(el, DoubleAngle):
        beam_bolted = el.beam_weld <= 0.0
        support_bolted = el.support_weld <= 0.0
        if beam_bolted or support_bolted:
            check_rows("el ángulo doble", el.bolt, el.length, el.rows,
                       el.spacing, el.lev)
            if beam_bolted:
                check_edge("l_eh en el ala de la viga", el.leh_beam, el.bolt)
            if support_bolted:
                check_edge("l_eh en el ala del apoyo", el.leh_support, el.bolt)
        if conn.beam_leh is not None:
            check_edge("l_eh del alma de la viga", conn.beam_leh, el.bolt)
    elif isinstance(el, SinglePlate):
        check_rows("la placa simple", el.bolt, el.length, el.rows, el.spacing, el.lev)
        check_edge("l_eh de la placa", el.leh, el.bolt)
        if el.beam_leh is not None:
            check_edge("l_eh del alma de la viga", el.beam_leh, el.bolt)
    elif isinstance(el, ExtendedSinglePlate):
        check_rows("la placa extendida", el.bolt, el.length, el.rows, el.spacing, el.lev)
        check_edge("l_eh de la placa", el.leh, el.bolt)
        if el.lines > 1:
            check_spacing("g", el.gage, el.bolt)
        if el.beam_leh is not None:
            check_edge("l_eh del alma de la viga", el.beam_leh, el.bolt)
    elif isinstance(el, EndPlate):
        check_rows("la placa de extremo", el.bolt, el.length, el.rows, el.spacing, el.lev)
        check_edge("l_eh de la placa", el.leh, el.bolt)
    elif isinstance(el, SkewedBentPlate):
        for label, plate in (("A", el.plate_a), ("B", el.plate_b)):
            check_rows(f"la placa doblada {label}", plate.bolt, plate.length,
                       plate.rows, plate.spacing, plate.lev)
            check_edge(f"l_eh de la placa doblada {label}", plate.leh, plate.bolt)
            if plate.width > 0.0 and plate.width + 1e-3 < plate.leh:
                fail(f"el ancho de la placa doblada {label} "
                     f"({fmt_length(plate.width)}) es menor que l_eh "
                     f"({fmt_length(plate.leh)}). Aumente el ancho de la placa.")


def _unsupported(key: str, value: float, method: Method, combo: str,
                 clause: str) -> CheckResult:
    c = Calc(method, combo)
    c.step("P", "", value, Kind.FORCE, clause)
    return c.result(f"shear_connection.{key}", clause, abs(value), 0.0, Kind.FORCE)


def check_shear_connection(conn: ShearConnection, forces: Forces, method: Method,
                           combo: str = "") -> list[CheckResult]:
    """All limit states for the end forces of one combination."""
    validate_shear_connection(conn)
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
            if conn.offset > 0 and not conn.welded_double_angle:
                out.append(check_shared_support_bolts(el, V, method, combo))
    elif conn.type is ShearType.SINGLE_PLATE:
        out += (check_single_plate_axial(el, V, N, method, combo) if N > 0
                else check_single_plate(el, V, method, combo))
    elif conn.type is ShearType.EXTENDED_SINGLE_PLATE:
        out += (check_extended_single_plate_axial(el, V, N, method, combo) if N > 0
                else check_extended_single_plate(el, V, method, combo))
    elif conn.type is ShearType.END_PLATE:
        out += check_end_plate(el, V, method, combo)
    elif conn.type is ShearType.SEATED:
        out += check_seated(el, V, method, combo)
    elif conn.type is ShearType.STIFFENED_SEAT:
        out += check_stiffened_seat(el, V, method, combo)
    elif conn.type is ShearType.SKEWED_BENT_PLATE:
        out += check_skewed_bent_plate(el, V, method, combo)
    else:
        raise AssertionError(f"unsupported shear connection type: {conn.type}")
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
