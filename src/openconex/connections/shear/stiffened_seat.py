# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Welded stiffened seated connection (AISC Manual Part 10; Examples II.A-14, II.A-15).

A seat plate on a vertical stiffener plate of width W and length l, both
welded to the support. Limit states for the beam end reaction R:

* minimum stiffener width for web local crippling and web local yielding of
  the beam, W_min = (R − φR_a)/φR_b + setback + underrun, with the constants of
  Manual Table 9-4 (AISC 360-22 Eq. J10-3 and J10-5);
* the welds of the stiffener to the support, two lines of length l with the
  seat-plate weld 0.2 l: R_n = 2 r_w 1.2 l^2 / sqrt(l^2 + 16 e^2), e = 0.8 W
  (elastic method of Manual Table 10-8);
* stiffener thickness t ≥ max(1.5 w, F_y,beam t_w / F_y,stiffener) (Manual Part
  10; the 1.5 w rule is for 50 ksi plates with 70 ksi electrodes);
* support thickness that develops the welds, 3.09 D/F_u, or 6.19 D/F_u when
  both sides of a web carry a seat (Manual Eq. 9-6, 9-7);
* seat plate bearing on the stiffener, 1.8 F_y W t (§J7.1);
* seat plate detail: 3/8 in. thick, at least 1 in. wider than the stiffener,
  3/16 in. weld and a weld length of at least 0.2 l (Manual Part 10 and
  Design Example II.A-14).

The top angle is the standard stability detail shared with the unstiffened
seat; it carries no part of the reaction.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from openconex.core.checks import CheckResult
from openconex.core.loads import Method
from openconex.core.materials import E_STEEL
from openconex.kernel.design import Calc, Resistance
from openconex.kernel.welds import fillet_weld_per_length
from openconex.units import Kind, from_internal, to_internal

from .seated import (
    PART10,
    TOP_ANGLE_BOLTS,
    TOP_ANGLE_LEG,
    TOP_ANGLE_LENGTH,
    TOP_ANGLE_THICKNESS,
    TOP_ANGLE_WELD,
    WEB_CRIPPLING,
    WEB_YIELDING,
    top_angle_checks,
)

__all__ = ["StiffenedSeat", "check_stiffened_seat", "seat_plate_width"]

BEARING = Resistance(0.75, 2.00)
SEAT_PLATE_THICKNESS = to_internal(0.375, "in", Kind.THICKNESS)
SEAT_PLATE_WELD = to_internal(0.3125, "in", Kind.THICKNESS)
SEAT_PLATE_EDGE = to_internal(0.5, "in", Kind.LENGTH)
"""Minimum extension of the seat plate beyond each side of the stiffener."""


@dataclass(frozen=True)
class StiffenedSeat:
    width: float
    """Stiffener width W (outstanding)."""
    length: float
    """Stiffener length l (vertical)."""
    thickness: float
    """Stiffener thickness."""
    stiffener_Fy: float
    weld: float
    """Fillet weld size of the stiffener to the support (each side)."""
    beam_d: float
    beam_tw: float
    beam_tf: float
    beam_kdes: float
    beam_Fy: float
    support_t: float
    support_Fu: float
    two_sided: bool = False
    """Seats on both sides of the support web."""
    setback: float = to_internal(0.5, "in", Kind.LENGTH)
    underrun: float = to_internal(0.25, "in", Kind.LENGTH)
    FEXX: float = to_internal(70.0, "ksi", Kind.STRESS)
    seat_plate_width: float = 0.0
    """Seat plate width across the beam; 0 uses the stiffener width plus 1 in."""
    seat_plate_thickness: float = SEAT_PLATE_THICKNESS
    seat_plate_weld: float = SEAT_PLATE_WELD
    top_angle_leg: float = TOP_ANGLE_LEG
    top_angle_thickness: float = TOP_ANGLE_THICKNESS
    top_angle_length: float = TOP_ANGLE_LENGTH
    top_angle_bolts: int = TOP_ANGLE_BOLTS
    top_angle_weld: float = TOP_ANGLE_WELD


def _available(method: Method, nominal: float, r) -> float:
    return r.phi * nominal if method is Method.LRFD else nominal / r.omega


def _width(ss: StiffenedSeat, R: float, method: Method, combo: str) -> CheckResult:
    c = Calc(method, combo)
    clause = "AISC Manual 16th ed., Part 9, Table 9-4; AISC 360-22 §J10"
    tw, tf, d, Fy = ss.beam_tw, ss.beam_tf, ss.beam_d, ss.beam_Fy
    extra = ss.setback + ss.underrun
    r1 = c.step(r"R_1", r"2.5 k F_y t_w", _available(method, 2.5 * ss.beam_kdes * Fy * tw,
                                                     WEB_YIELDING), Kind.FORCE, clause)
    r2 = c.step(r"R_2", r"F_y t_w", _available(method, Fy * tw, WEB_YIELDING),
                Kind.FORCE_PER_LENGTH, clause)
    yielding = c.step(r"W_{min,yielding}", r"\frac{R - R_1}{R_2} + \mathrm{setback}"
                      r" + \mathrm{underrun}", (R - r1) / r2 + extra, Kind.LENGTH, clause)
    root = 0.40 * tw**2 * math.sqrt(E_STEEL * Fy * tf / tw)
    slender = (tw / tf) ** 1.5
    if (ss.width - extra) / d > 0.2:
        ra = root * (1 - 0.2 * slender)
        rb = root * 4 / d * slender
        names = ("R_5", "R_6")
    else:
        ra, rb = root, root * 3 / d * slender
        names = ("R_3", "R_4")
    ra = c.step(names[0], "", _available(method, ra, WEB_CRIPPLING), Kind.FORCE, clause)
    rb = c.step(names[1], "", _available(method, rb, WEB_CRIPPLING), Kind.FORCE_PER_LENGTH,
                clause)
    crippling = c.step(r"W_{min,crippling}", rf"\frac{{R - {names[0]}}}{{{names[1]}}}"
                       r" + \mathrm{setback} + \mathrm{underrun}", (R - ra) / rb + extra,
                       Kind.LENGTH, clause)
    w_min = c.step(r"W_{min}", r"\max", max(yielding, crippling), Kind.LENGTH, clause)
    return c.result("stiffened_seat.width", clause, w_min, ss.width, Kind.LENGTH)


def seat_plate_width(ss: StiffenedSeat) -> float:
    """Seat plate width; the default extends 1/2 in. beyond each stiffener edge."""
    return ss.seat_plate_width or ss.width + 2 * SEAT_PLATE_EDGE


def _seat_plate(ss: StiffenedSeat, R: float, method: Method,
                combo: str) -> list[CheckResult]:
    """Bearing on the stiffener and the standard seat-plate detail."""
    c = Calc(method, combo)
    clause = "AISC 360-22 §J7.1; AISC Manual 16th ed., Part 10"
    area = ss.width * ss.thickness
    bearing = c.result("stiffened_seat.seat_plate_bearing", clause, R,
                       c.available(1.8 * ss.stiffener_Fy * area, BEARING, Kind.FORCE,
                                   clause), Kind.FORCE)

    checks = [bearing]
    clause = f"{PART10}, seat plate detail"
    for check_id, required, actual, kind in (
            ("stiffened_seat.seat_plate_width", ss.width + 2 * SEAT_PLATE_EDGE,
             seat_plate_width(ss), Kind.LENGTH),
            ("stiffened_seat.seat_plate_thickness", SEAT_PLATE_THICKNESS,
             ss.seat_plate_thickness, Kind.THICKNESS),
            ("stiffened_seat.seat_plate_weld", SEAT_PLATE_WELD,
             ss.seat_plate_weld, Kind.THICKNESS),
            ("stiffened_seat.seat_plate_weld_length", 0.2 * ss.length,
             ss.width, Kind.LENGTH)):
        c = Calc(method, combo)
        c.step("required", "", required, kind, clause)
        checks.append(c.result(check_id, clause, required, actual, kind))
    return checks


def check_stiffened_seat(ss: StiffenedSeat, R: float, method: Method,
                         combo: str = "") -> list[CheckResult]:
    """All limit states of the stiffened seat for the beam end reaction ``R``."""
    c = Calc(method, combo)
    clause = f"{PART10}, Table 10-8"
    e = c.step("e", "0.8 W", 0.8 * ss.width, Kind.LENGTH, clause)
    rw = fillet_weld_per_length(ss.weld, ss.FEXX, 0.0, method).capacity
    L = ss.length
    rn = c.step("R_n", r"\frac{2 r_w\,1.2 l^2}{\sqrt{l^2 + 16 e^2}}",
                2 * rw * 1.2 * L**2 / math.sqrt(L**2 + 16 * e**2), Kind.FORCE, clause,
                l=(L, Kind.LENGTH), w=(ss.weld, Kind.THICKNESS))
    weld = c.result("stiffened_seat.weld", clause, R, rn, Kind.FORCE)

    c = Calc(method, combo)
    t_min = c.step("t_{min}", r"\max(1.5 w, \frac{F_{y,b}}{F_{y,s}} t_w)",
                   max(1.5 * ss.weld, ss.beam_Fy / ss.stiffener_Fy * ss.beam_tw),
                   Kind.THICKNESS, PART10)
    stiffener = c.result("stiffened_seat.stiffener_thickness", PART10, t_min, ss.thickness,
                         Kind.THICKNESS)

    c = Calc(method, combo)
    factor, eq = (6.19, "9-7") if ss.two_sided else (3.09, "9-6")
    clause = f"AISC Manual 16th ed., Eq. {eq}"
    D = from_internal(ss.weld, Kind.LENGTH, "in") * 16
    t_sup = c.step("t_{min}", rf"\frac{{{factor} D}}{{F_u}}",
                   to_internal(factor * D / from_internal(ss.support_Fu, Kind.STRESS, "ksi"),
                               "in", Kind.LENGTH), Kind.THICKNESS, clause)
    support = c.result("stiffened_seat.support_thickness", clause, t_sup, ss.support_t,
                       Kind.THICKNESS)
    return [_width(ss, R, method, combo), weld, stiffener,
            *_seat_plate(ss, R, method, combo),
            *top_angle_checks(method, combo, leg=ss.top_angle_leg,
                              thickness=ss.top_angle_thickness,
                              length=ss.top_angle_length, bolts=ss.top_angle_bolts,
                              weld=ss.top_angle_weld, welded=True), support]
