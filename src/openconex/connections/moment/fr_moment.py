# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Fully restrained moment connections to a column flange (AISC Manual Parts 9-12).

Design Examples II.B-1, II.B-2 and II.B-3. The beam end moment ``M`` is
resolved into a flange force P_f = M / d_m (Manual Eq. 11-1) and the shear
``V`` is carried by a single plate on the web. Three flange details:

* ``bolted_flange_plate`` (II.B-1): plates bolted to the beam flanges and
  fillet-welded to the column. d_m = d for the bolts and the beam flange,
  d + t_p for the plates. Checks: beam flexural rupture at the holes (§F13.1),
  bolts, plate tensile yielding and rupture, plate and beam flange block
  shear, plate compression (§J4.4, K = 0.65 between bolts) and the plate weld
  to the column (k_ds = 1.5).
* ``welded_flange_plate`` (II.B-2): plates fillet-welded to the beam flanges.
  d_m = d + (t_top + t_bot)/2 for the plates, d for the welds to the beam.
  Checks: top plate tensile yielding, its longitudinal and transverse welds
  (§J2.4(b), Eq. J2-6), the base metal for those welds (Manual Eq. 9-6), the
  bottom plate in compression, its longitudinal welds and the beam flange
  rupture along them, and both plate welds to the column.
* ``welded_flange`` (II.B-3): flanges welded with CJP groove welds; the welds
  develop the flanges and only the web connection and the column are checked.

All types check the single-plate web connection in direct shear (bolts, plate
shear yielding, rupture and block shear, the fillet welds to the column and
the column flange rupture at them) and the column under the flange force
(§J10.1 flange local bending, §J10.2 web local yielding, §J10.3 web local
crippling, and §J10.5 web compression buckling when beams frame into both
flanges). Panel zone shear (§J10.6) is checked when the column shear and
axial force are given.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum

from openconex.core.checks import CheckResult
from openconex.core.loads import Forces, LoadCombination, Method, combine
from openconex.core.model import BoltSpec, IShape
from openconex.kernel import bolts, elements, local
from openconex.kernel.bolts import clear_distance
from openconex.kernel.design import FLEXURE, Calc
from openconex.kernel.welds import fillet_weld_group_concentric, fillet_weld_per_length
from openconex.units import Kind, from_internal, to_internal

__all__ = ["FlangeDetail", "FlangePlate", "MomentConnection", "WebPlate",
           "check_moment_connection", "check_moment_envelope"]

SPEC = "AISC 360-22"
MANUAL = "AISC Manual 16th ed."
INCH = to_internal(1.0, "in", Kind.LENGTH)


class FlangeDetail(StrEnum):
    BOLTED_FLANGE_PLATE = "bolted_flange_plate"
    WELDED_FLANGE_PLATE = "welded_flange_plate"
    WELDED_FLANGE = "welded_flange"


@dataclass(frozen=True)
class WebPlate:
    """Single plate on the beam web, bolted to the web and welded to the column flange."""

    bolt: BoltSpec
    rows: int
    spacing: float
    length: float
    thickness: float
    lev: float
    leh: float
    weld: float
    Fy: float
    Fu: float


@dataclass(frozen=True)
class FlangePlate:
    width: float
    thickness: float
    weld_to_column: float
    """Fillet weld size on each side of the plate at the column flange."""
    unbraced_length: float
    """Length for the compression check: bolt spacing, or the free length to the welds."""
    weld_to_beam: float = 0.0
    """Welded plates: fillet weld size along the beam flange."""
    weld_length: float = 0.0
    """Welded plates: length of each longitudinal weld along the beam flange."""
    transverse_weld: bool = False
    """Welded plates: weld across the plate end as well (top plate of II.B-2)."""


@dataclass(frozen=True)
class MomentConnection:
    detail: FlangeDetail
    beam: IShape
    beam_Sx: float
    column: IShape
    web: WebPlate
    plate_Fy: float = 0.0
    plate_Fu: float = 0.0
    top: FlangePlate | None = None
    bottom: FlangePlate | None = None
    bolt: BoltSpec | None = None
    """Bolted flange plates: flange bolts."""
    rows: int = 0
    """Bolted flange plates: bolts in each of the two lines along the beam."""
    spacing: float = 0.0
    gage: float = 0.0
    plate_lev: float = 0.0
    """Bolted flange plates: plate end to the first bolt (far from the column)."""
    beam_lev: float = 0.0
    """Bolted flange plates: beam end to the first bolt, before the length underrun."""
    underrun: float = to_internal(0.25, "in", Kind.LENGTH)
    FEXX: float = to_internal(70.0, "ksi", Kind.STRESS)
    deformation_considered: bool = True
    column_near_end: bool = False
    """Flange force applied near the column end (§J10: reduced strengths)."""
    two_sided: bool = False
    """Beams frame into both column flanges (§J10.5 web compression buckling)."""


def _rename(check: CheckResult, key: str) -> CheckResult:
    return check.model_copy(update={"id": f"moment.{key}", "text_id": f"check.moment.{key}"})


def _hole_net(bolt: BoltSpec) -> float:
    return bolt.hole_dimensions[0] + to_internal(1 / 16, "in", Kind.LENGTH)


def _bearing_tearout(bolt: BoltSpec, t: float, Fu: float, lc: float, method: Method,
                     deformation: bool) -> float:
    kw = {"deformation_considered": deformation}
    return min(bolts.bolt_bearing(bolt, t, Fu, 0.0, method, **kw).capacity,
               bolts.bolt_tearout(bolt, t, Fu, lc, 0.0, method, **kw).capacity)


# -- web connection --------------------------------------------------------------------
def _web_checks(mc: MomentConnection, V: float, method: Method, combo: str) -> list[CheckResult]:
    w, beam = mc.web, mc.beam
    deform = mc.deformation_considered
    c = Calc(method, combo)
    clause = f"{SPEC} §J3.7, §J3.11"
    shear = c.step("r_{n,bolt}", "", bolts.bolt_shear(w.bolt, 0.0, method).capacity, Kind.FORCE,
                   f"{SPEC} §J3.7")
    inner = clear_distance(w.bolt, w.spacing, to_edge=False)
    edge = clear_distance(w.bolt, w.lev, to_edge=True)
    plate_inner = c.step("r_{n,plate}", r"\min(2.4dtF_u, 1.2l_ctF_u)",
                         _bearing_tearout(w.bolt, w.thickness, w.Fu, inner, method, deform),
                         Kind.FORCE, clause)
    plate_edge = c.step("r_{n,plate,edge}", r"\min(2.4dtF_u, 1.2l_ctF_u)",
                        _bearing_tearout(w.bolt, w.thickness, w.Fu, edge, method, deform),
                        Kind.FORCE, clause, l_c=(edge, Kind.LENGTH))
    web = c.step("r_{n,web}", r"\min(2.4dt_wF_u, 1.2l_ct_wF_u)",
                 _bearing_tearout(w.bolt, beam.tw, beam.material.Fu, inner, method, deform),
                 Kind.FORCE, clause)
    rows = [min(shear, plate_edge if i == w.rows - 1 else plate_inner, web)
            for i in range(w.rows)]
    rn = c.step(r"\sum r_{n,i}", "", sum(rows), Kind.FORCE, clause)
    out = [c.result("moment.web_bolts", clause, V, rn, Kind.FORCE)]
    hole = _hole_net(w.bolt)
    t = w.thickness
    out.append(_rename(elements.shear_yielding(w.length * t, w.Fy, V, method, combo),
                       "web_plate_shear_yielding"))
    out.append(_rename(elements.shear_rupture((w.length - w.rows * hole) * t, w.Fu, V, method,
                                              combo), "web_plate_shear_rupture"))
    agv = (w.length - w.lev) * t
    out.append(_rename(elements.block_shear(agv, agv - (w.rows - 0.5) * hole * t,
                                            (w.leh - 0.5 * hole) * t, w.Fy, w.Fu, V, method,
                                            Ubs=1.0, combo=combo), "web_plate_block_shear"))
    c = Calc(method, combo)
    clause = f"{SPEC} §J2.4; {MANUAL}, Eq. 8-2"
    rw = fillet_weld_per_length(w.weld, mc.FEXX, 0.0, method).capacity
    rn = c.step("R_n", "2 r_w l", 2 * rw * w.length, Kind.FORCE, clause,
                w=(w.weld, Kind.THICKNESS), l=(w.length, Kind.LENGTH))
    out.append(c.result("moment.web_weld", clause, V, rn, Kind.FORCE))
    out.append(_rename(elements.shear_rupture(2 * w.length * mc.column.tf,
                                              mc.column.material.Fu, V, method, combo),
                       "web_support_rupture"))
    return out


# -- flange connection -----------------------------------------------------------------
def _flange_force(c: Calc, M: float, dm: float, expression: str) -> float:
    return c.step("P_f", f"M/d_m,\\ d_m = {expression}", M / dm, Kind.FORCE,
                  f"{MANUAL}, Eq. 11-1", d_m=(dm, Kind.LENGTH))


def _plate_to_column_weld(key: str, plate: FlangePlate, P: float, mc: MomentConnection,
                          method: Method, combo: str) -> CheckResult:
    c = Calc(method, combo)
    clause = f"{SPEC} §J2.4, Eq. J2-5; {MANUAL}, Eq. 8-2"
    kds = c.step("k_{ds}", r"1.0 + 0.50\sin^{1.5}90°", 1.5, clause=clause)
    rw = fillet_weld_per_length(plate.weld_to_column, mc.FEXX, 0.0, method).capacity
    rn = c.step("R_n", "2 k_{ds} r_w b", 2 * kds * rw * plate.width, Kind.FORCE, clause,
                w=(plate.weld_to_column, Kind.THICKNESS), b=(plate.width, Kind.LENGTH))
    return c.result(f"moment.{key}", clause, P, rn, Kind.FORCE)


def _plate_compression(key: str, plate: FlangePlate, P: float, mc: MomentConnection,
                       method: Method, combo: str) -> CheckResult:
    c = Calc(method, combo)
    clause = f"{SPEC} §J4.4; Commentary Table C-A-7.1 (K = 0.65)"
    r = c.step("r", r"t/\sqrt{12}", plate.thickness / math.sqrt(12), Kind.LENGTH, clause)
    slenderness = c.step(r"\frac{L_c}{r}", r"\frac{0.65 L}{r}", 0.65 * plate.unbraced_length / r,
                         clause=clause, L=(plate.unbraced_length, Kind.LENGTH))
    check = elements.compression(plate.width * plate.thickness, mc.plate_Fy, slenderness, P,
                                 method, combo)
    return check.model_copy(update={"id": f"moment.{key}", "text_id": f"check.moment.{key}",
                                    "clause": clause, "steps": tuple(c.steps) + check.steps})


def _beam_flexural_rupture(mc: MomentConnection, M: float, method: Method,
                           combo: str) -> CheckResult:
    c = Calc(method, combo)
    clause = f"{SPEC} §F13.1, Eq. F13-1"
    beam = mc.beam
    Fy, Fu = beam.material.Fy, beam.material.Fu
    afg = c.step("A_{fg}", "b_f t_f", beam.bf * beam.tf, Kind.AREA, clause)
    afn = c.step("A_{fn}", "A_{fg} - 2 (d_h + 1/16) t_f", afg - 2 * _hole_net(mc.bolt) * beam.tf,
                 Kind.AREA, clause)
    yt = c.step("Y_t", r"1.0\ (F_y/F_u \le 0.8),\ 1.1", 1.0 if Fy / Fu <= 0.8 else 1.1,
                clause=clause)
    applies = Fu * afn < yt * Fy * afg
    mn = c.step("M_n", r"\frac{F_u A_{fn}}{A_{fg}} S_x", Fu * afn / afg * mc.beam_Sx,
                Kind.MOMENT, clause, S_x=(mc.beam_Sx, Kind.SECTION_MODULUS))
    return c.result("moment.beam_flexural_rupture", clause, M,
                    c.available(mn, FLEXURE, Kind.MOMENT, clause, "M_n"), Kind.MOMENT,
                    applicable=applies)


def _bolted(mc: MomentConnection, M: float, method: Method, combo: str) -> list[CheckResult]:
    beam, plate, b = mc.beam, mc.top, mc.bolt
    t, n, hole = plate.thickness, mc.rows, _hole_net(mc.bolt)
    deform = mc.deformation_considered
    out = [_beam_flexural_rupture(mc, M, method, combo)]

    c = Calc(method, combo)
    clause = f"{SPEC} §J3.7, §J3.11"
    P_bolt = _flange_force(c, M, beam.d, "d")
    shear = c.step("r_{n,bolt}", "", bolts.bolt_shear(b, 0.0, method).capacity, Kind.FORCE,
                   f"{SPEC} §J3.7")
    inner = clear_distance(b, mc.spacing, to_edge=False)
    plate_edge = clear_distance(b, mc.plate_lev, to_edge=True)
    beam_edge = clear_distance(b, mc.beam_lev - mc.underrun, to_edge=True)
    per = []
    for i in range(n):
        plate_rn = _bearing_tearout(b, t, mc.plate_Fu, plate_edge if i == 0 else inner,
                                    method, deform)
        flange_rn = _bearing_tearout(b, beam.tf, beam.material.Fu,
                                     beam_edge if i == n - 1 else inner, method, deform)
        per.append(min(shear, plate_rn, flange_rn))
    rn = c.step(r"2\sum r_{n,i}", "", 2 * sum(per), Kind.FORCE, clause,
                n=(2 * n, Kind.DIMENSIONLESS))
    out.append(c.result("moment.flange_bolts", clause, P_bolt, rn, Kind.FORCE))

    c = Calc(method, combo)
    P = _flange_force(c, M, beam.d + t, "d + t_p")
    out.append(_rename(elements.tension_yielding(plate.width * t, mc.plate_Fy, P, method,
                                                 combo), "flange_plate_tension_yielding"))
    out.append(_rename(elements.tension_rupture((plate.width - 2 * hole) * t, mc.plate_Fu, P,
                                                method, combo), "flange_plate_tension_rupture"))
    leh = (plate.width - mc.gage) / 2
    length = (n - 1) * mc.spacing + mc.plate_lev
    agv1 = 2 * length * t
    case1 = elements.block_shear(agv1, agv1 - 2 * (n - 0.5) * hole * t,
                                 2 * (leh - 0.5 * hole) * t, mc.plate_Fy, mc.plate_Fu, P,
                                 method, Ubs=1.0, combo=combo)
    agv2 = 2 * length * t
    case2 = elements.block_shear(agv2, agv2 - 2 * (n - 0.5) * hole * t,
                                 (mc.gage - hole) * t, mc.plate_Fy, mc.plate_Fu, P, method,
                                 Ubs=1.0, combo=combo)
    agv3 = length * t
    case3 = elements.block_shear(agv3, agv3 - (n - 0.5) * hole * t,
                                 (mc.gage + leh - 1.5 * hole) * t, mc.plate_Fy, mc.plate_Fu,
                                 P, method, Ubs=1.0, combo=combo)
    out.append(_rename(min(case1, case2, case3, key=lambda r: r.capacity),
                       "flange_plate_block_shear"))
    beam_leh = (beam.bf - mc.gage) / 2
    blen = (n - 1) * mc.spacing + mc.beam_lev - mc.underrun
    agv = 2 * blen * beam.tf
    out.append(_rename(elements.block_shear(
        agv, agv - 2 * (n - 0.5) * hole * beam.tf, 2 * (beam_leh - 0.5 * hole) * beam.tf,
        beam.material.Fy, beam.material.Fu, P_bolt, method, Ubs=1.0, combo=combo),
        "beam_flange_block_shear"))
    out.append(_plate_to_column_weld("flange_plate_weld", plate, P, mc, method, combo))
    out.append(_plate_compression("flange_plate_compression", mc.bottom or plate, P, mc, method,
                                  combo))
    return out, P


def _welded(mc: MomentConnection, M: float, method: Method, combo: str) -> list[CheckResult]:
    beam, top, bottom = mc.beam, mc.top, mc.bottom
    out = []
    c = Calc(method, combo)
    P = _flange_force(c, M, beam.d + (top.thickness + bottom.thickness) / 2,
                      "d + (t_{top} + t_{bot})/2")
    out.append(_rename(elements.tension_yielding(top.width * top.thickness, mc.plate_Fy, P,
                                                 method, combo), "flange_plate_tension_yielding"))
    c = Calc(method, combo)
    P_weld = _flange_force(c, M, beam.d, "d")
    weld = fillet_weld_group_concentric(top.weld_to_beam, mc.FEXX, 2 * top.weld_length,
                                        top.width if top.transverse_weld else 0.0, P_weld,
                                        method, combo)
    out.append(_rename(weld, "top_plate_weld_to_beam"))
    c = Calc(method, combo)
    clause = f"{MANUAL}, Eq. 9-6"
    D = from_internal(top.weld_to_beam, Kind.LENGTH, "in") * 16
    Fu_min = min(beam.material.Fu, mc.plate_Fu)
    t_min = c.step("t_{min}", r"\frac{3.09 D}{F_u}",
                   to_internal(3.09 * D / from_internal(Fu_min, Kind.STRESS, "ksi"), "in",
                               Kind.LENGTH), Kind.THICKNESS, clause)
    out.append(c.result("moment.weld_base_metal", clause, t_min, min(beam.tf, top.thickness),
                        Kind.THICKNESS))
    out.append(_plate_to_column_weld("top_plate_weld_to_column", top, P, mc, method, combo))
    out.append(_plate_compression("flange_plate_compression", bottom, P, mc, method, combo))
    c = Calc(method, combo)
    clause = f"{SPEC} §J2.4; {MANUAL}, Eq. 8-2"
    rw = fillet_weld_per_length(bottom.weld_to_beam, mc.FEXX, 0.0, method).capacity
    rn = c.step("R_n", "2 r_w l", 2 * rw * bottom.weld_length, Kind.FORCE, clause,
                l=(bottom.weld_length, Kind.LENGTH))
    out.append(c.result("moment.bottom_plate_weld_to_beam", clause, P_weld, rn, Kind.FORCE))
    out.append(_rename(elements.shear_rupture(2 * beam.tf * bottom.weld_length,
                                              beam.material.Fu, P_weld, method, combo),
                       "beam_flange_rupture_at_welds"))
    out.append(_plate_to_column_weld("bottom_plate_weld_to_column", bottom, P, mc, method,
                                     combo))
    return out, P


# -- column ------------------------------------------------------------------------------
def _column_checks(mc: MomentConnection, P: float, lb: float, method: Method, combo: str,
                   column_shear: float | None, column_axial: float) -> list[CheckResult]:
    col = mc.column
    near = mc.column_near_end
    out = [
        _rename(local.flange_local_bending(col, P, method, near, combo),
                "column_flange_local_bending"),
        _rename(local.web_local_yielding(col, lb, P, method, near, combo),
                "column_web_local_yielding"),
        _rename(local.web_local_crippling(col, lb, P, method, near, combo),
                "column_web_crippling"),
    ]
    if mc.two_sided:
        out.append(_rename(local.web_compression_buckling(col, P, method, near, combo),
                           "column_web_compression_buckling"))
    if column_shear is not None:
        demand = (2 * P if mc.two_sided else P) - column_shear
        out.append(_rename(local.panel_zone_shear(col, column_axial, abs(demand), method,
                                                  combo=combo), "column_panel_zone"))
    return out


def check_moment_connection(mc: MomentConnection, V: float, M: float, method: Method,
                            combo: str = "", column_shear: float | None = None,
                            column_axial: float = 0.0) -> list[CheckResult]:
    """Limit states for the beam end shear ``V`` and moment ``M`` (absolute values used).

    ``column_shear`` (story shear in the column above the connection) enables the
    panel zone check; ``column_axial`` is the column axial force for it.
    """
    V, M = abs(V), abs(M)
    out = _web_checks(mc, V, method, combo)
    if mc.detail is FlangeDetail.BOLTED_FLANGE_PLATE:
        flange, P = _bolted(mc, M, method, combo)
        lb = mc.top.thickness
    elif mc.detail is FlangeDetail.WELDED_FLANGE_PLATE:
        flange, P = _welded(mc, M, method, combo)
        lb = mc.top.thickness
    else:
        c = Calc(method, combo)
        P = _flange_force(c, M, mc.beam.d - mc.beam.tf, "d - t_f")
        flange, lb = [], mc.beam.tf
    return out + flange + _column_checks(mc, P, lb, method, combo, column_shear, column_axial)


def check_moment_envelope(mc: MomentConnection, combinations: Iterable[LoadCombination],
                          case_forces: Mapping[str, Forces]) -> list[CheckResult]:
    """Run every combination: ``V2`` is the beam end shear and ``M3`` its moment."""
    results: list[CheckResult] = []
    for combo in combinations:
        forces = combine(combo, case_forces)
        results += check_moment_connection(mc, forces.V2, forces.M3, combo.method, combo.name)
    return results
