# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Complete check of an exposed column base plate for one load combination.

The plate is rectangular, N along the strong-axis moment and B across it.
Anchors are placed in two rows parallel to B at ±f from the column axis,
``rods_per_side`` in each row, spread over ``rod_spacing``. ACI 318 anchorage
checks are strength design and run only for LRFD combinations; with ASD the
anchor rods are checked as threaded parts with AISC 360-22 §J3.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from openconex.core.checks import CheckResult, governing
from openconex.core.loads import Forces, LoadCombination, Method, combine
from openconex.core.materials import STEELS
from openconex.core.model import BoltSpec, FilletWeld, HSSKind, HSSShape, IShape
from openconex.kernel import anchors, bolts
from openconex.kernel.design import Calc
from openconex.units import Kind

from . import plate as bpl
from . import transfer

__all__ = ["BasePlate", "check_base_plate", "check_envelope"]

DG1 = "AISC DG1 3rd ed."


@dataclass(frozen=True)
class BasePlate:
    column: IShape | HSSShape
    N: float
    B: float
    tp: float
    fc: float
    rod: BoltSpec
    f: float
    """Column axis to each anchor row."""
    rods_per_side: int = 2
    rod_spacing: float = 0.0
    """Distance between the outer rods of one row."""
    hef: float = 0.0
    plate_grade: str = "ASTM A572 Gr. 50"
    A2_over_A1: float = 1.0
    edges: anchors.Edges = field(default_factory=anchors.Edges)
    bearing_area: float | None = None
    """Bearing area of the embedded nut or plate; default: heavy hex nut."""
    washer_thickness: float | None = None
    """Welded plate washers: shear goes to all rods, with rod bending."""
    grout_pad: bool = True
    flange_weld: float | None = None
    """Fillet weld size on the column flanges (None: not checked)."""
    friction_mu: float = 0.4
    cracked: bool = True
    seismic: bool = False

    @property
    def Fy(self) -> float:
        return STEELS[self.plate_grade].Fy

    @property
    def rods(self) -> int:
        return 2 * self.rods_per_side


def _thickness(check_id: str, required: float, provided: float, method: Method, combo: str,
               clause: str, steps: list | None = None, expression: str = "") -> CheckResult:
    c = Calc(method, combo)
    c.steps.extend(steps or [])
    c.step("t_{p,req}", expression, required, Kind.THICKNESS, clause)
    return c.result(check_id, clause, required, provided, Kind.THICKNESS)


def _compression_steps(method: Method, fp: float, Y: float, m: float, n: float,
                       Fy: float) -> tuple[float, list]:
    """Required thickness at the bearing interface with its trace (DG1 Eq. 4-47 to 4-52)."""
    c = Calc(method)
    lc = c.step("l", r"\max(m, n)", max(m, n), Kind.LENGTH, f"{DG1} Eq. 4-10, 4-11",
                m=(m, Kind.LENGTH), n=(n, Kind.LENGTH))
    c.step("f_p", "", fp, Kind.STRESS, DG1)
    c.step("Y", "", Y, Kind.LENGTH, DG1)
    expr = (r"\frac{f_p l^2}{2}" if Y >= lc else r"f_p Y\left(l - \frac{Y}{2}\right)")
    mpl = fp * lc**2 / 2 if Y >= lc else fp * Y * (lc - Y / 2)
    c.step("M_{pl}", expr, mpl, Kind.FORCE, f"{DG1} Eq. 4-47")
    return bpl.plate_thickness_compression(fp, Y, lc, Fy, method), c.steps


def _tp_expression(method: Method, moment: str) -> str:
    k = r"\sqrt{4/\phi_b}" if method is Method.LRFD else r"\sqrt{4\Omega_b}"
    return k + moment


def _cantilevers(column: IShape | HSSShape, N: float, B: float) -> tuple[float, float]:
    """Critical plate projections m and n (DG1 Eq. 4-10, 4-11 and §4.3.3)."""
    if isinstance(column, HSSShape):
        coefficient = 0.8 if column.kind is HSSKind.ROUND else 0.95
        return (N - coefficient * column.d) / 2, (B - coefficient * column.bf) / 2
    return (N - 0.95 * column.d) / 2, (B - 0.8 * column.bf) / 2


def check_base_plate(bp: BasePlate, forces: Forces, method: Method,
                     combo: str = "") -> list[CheckResult]:
    """All base plate checks for one set of forces (P = forces.P, V = V2, M = M3)."""
    col = bp.column
    P_, V, M = forces.P, abs(forces.V2), abs(forces.M3)
    results: list[CheckResult] = []
    m, n = _cantilevers(col, bp.N, bp.B)

    # --- bearing and plate thickness ---------------------------------------
    bend = bpl.rectangular_bending(P_, M, bp.N, bp.B, bp.f, bp.fc, bp.A2_over_A1, method)
    T = 0.0
    if bend.case == "not_possible":
        c = Calc(method, combo)
        c.step("q_{max}", "f_{p(max)} B", bend.q_max, Kind.FORCE_PER_LENGTH, DG1)
        results.append(c.result("base_plate.bearing", f"{DG1} §4.3.6", math.inf, 0.0,
                                Kind.FORCE))
        return results
    if bend.case == "compression_only":
        comp = bpl.compression_design(P_, col.d, col.bf, bp.N, bp.B, bp.Fy, bp.fc,
                                    bp.A2_over_A1, method,
                                    col.kind if isinstance(col, HSSShape) else None)
        c = Calc(method, combo)
        c.step("f_{p(max)}", r"\phi_c 0.85 f'_c \sqrt{A_2/A_1}", comp.fp_max, Kind.STRESS,
               "AISC 360-22 §J8")
        results.append(c.result("base_plate.bearing", "AISC 360-22 §J8", P_, comp.Pp_available,
                                Kind.FORCE))
        results.append(_thickness("base_plate.thickness_compression", comp.tp_req, bp.tp,
                                  method, combo, f"{DG1} Eq. 4-15"))
    elif bend.case == "low_moment":
        c = Calc(method, combo)
        c.step("e", "M/P", bend.e, Kind.LENGTH, f"{DG1} Eq. 4-39")
        c.step("e_{crit}", r"\frac{N}{2} - \frac{P}{2 q_{max}}", bend.e_crit, Kind.LENGTH,
               f"{DG1} Eq. 4-40")
        c.step("Y", "N - 2e", bend.Y, Kind.LENGTH, f"{DG1} Eq. 4-42")
        c.step("q", "P/Y", bend.q, Kind.FORCE_PER_LENGTH, f"{DG1} Eq. 4-43")
        c.step("q_{max}", "f_{p(max)} B", bend.q_max, Kind.FORCE_PER_LENGTH, f"{DG1} Eq. 4-37")
        results.append(c.result("base_plate.bearing", f"{DG1} §4.3.3", bend.q, bend.q_max,
                                Kind.FORCE_PER_LENGTH))
        tp_req, steps = _compression_steps(method, bend.q / bp.B, bend.Y, m, n, bp.Fy)
        results.append(_thickness("base_plate.thickness_compression", tp_req, bp.tp, method,
                                  combo, f"{DG1} Eq. 4-51", steps,
                                  _tp_expression(method, r"\sqrt{M_{pl}/F_y}")))
    else:
        T = bend.T
        c = Calc(method, combo)
        c.step("q_{max}", "f_{p(max)} B", bend.q_max, Kind.FORCE_PER_LENGTH, f"{DG1} Eq. 4-37")
        c.step("Y", r"\left(f + \frac{N}{2}\right) - \sqrt{\left(f + \frac{N}{2}\right)^2 - "
               r"\frac{2(Pf + M)}{q_{max}}}", bend.Y, Kind.LENGTH, f"{DG1} Eq. 4-58")
        c.step("T", "q_{max} Y - P", T, Kind.FORCE, f"{DG1} Eq. 4-55")
        bearing_steps = list(c.steps)
        if bend.Y > 0:
            tp_req, steps = _compression_steps(method, bend.fp_max, bend.Y, m, n, bp.Fy)
            results.append(_thickness("base_plate.thickness_compression", tp_req, bp.tp,
                                      method, combo, f"{DG1} Eq. 4-51", bearing_steps + steps,
                                      _tp_expression(method, r"\sqrt{M_{pl}/F_y}")))
        x = bp.f - col.d / 2 + col.tf / 2
        c = Calc(method, combo)
        c.step("x", r"f - \frac{d}{2} + \frac{t_f}{2}", x, Kind.LENGTH, f"{DG1} Eq. 4-61")
        results.append(_thickness("base_plate.thickness_tension",
                                  bpl.plate_thickness_tension(T, x, bp.B, bp.Fy, method), bp.tp,
                                  method, combo, f"{DG1} Eq. 4-62", bearing_steps + c.steps,
                                  _tp_expression(method, r"\sqrt{\frac{T x}{B F_y}}")))

    # --- anchors -------------------------------------------------------------
    if bend.case == "uplift" and bend.Y == 0:
        positions = [bp.f, -bp.f]
        forces_row = bpl.uplift_low_moment(P_, M, positions)
        rod_t = max(forces_row) / bp.rods_per_side
        group_t = -P_
    else:
        rod_t = T / bp.rods_per_side
        group_t = T
    shear_rods = bp.rods if bp.washer_thickness else max(bp.rods_per_side, 1)
    rod_v = V / shear_rods
    use_friction = P_ > 0 and method is Method.LRFD and not bp.washer_thickness
    # futa = min(Fu, 1.9 Fy, 125 ksi): 1.9 Fy never governs for ASTM F1554 / F3125 rods.
    Fu = Fy = bp.rod.material.Fu
    if method is Method.LRFD:
        if rod_t > 0:
            results.append(anchors.steel_tension(bp.rod.diameter, Fu, Fy, rod_t, method, combo))
            if bp.hef:
                bo = anchors.breakout_tension(bp.hef, bp.fc, group_t, method,
                                              span_x=bp.rod_spacing, edges=bp.edges,
                                              cracked=bp.cracked, seismic=bp.seismic,
                                              combo=combo)
                results.append(bo)
            area = bp.bearing_area or anchors.heavy_hex_bearing_area(bp.rod.diameter)
            results.append(anchors.pullout(area, bp.fc, rod_t, method, bp.cracked, bp.seismic,
                                           combo))
        if V > 0 and use_friction:
            results.append(transfer.friction(P_, bp.N * bp.B, bp.fc, V, bp.friction_mu, combo))
        elif V > 0:
            results.append(anchors.steel_shear(bp.rod.diameter, Fu, Fy, rod_v, method,
                                               bp.grout_pad, combo))
    else:
        if rod_t > 0:
            results.append(bolts.bolt_tension(bp.rod, rod_t, method, combo))
        if V > 0:
            results.append(bolts.bolt_shear(bp.rod, rod_v, method, combo=combo))
    if V > 0 and bp.washer_thickness:
        results.append(transfer.rod_tension_shear_bending(bp.rod, bp.rods, group_t, V, bp.tp,
                                                          bp.washer_thickness, method, combo))

    # --- welds ---------------------------------------------------------------
    if M > 0 and bp.flange_weld:
        weld = FilletWeld(size=bp.flange_weld, length=col.bf)
        results.append(transfer.flange_weld_for_moment(M, col.d, weld, method, combo))
    return results


def check_envelope(bp: BasePlate, combinations: Iterable[LoadCombination],
                   case_forces: Mapping[str, Forces]) -> tuple[list[CheckResult], CheckResult]:
    """Run every combination; return all results and the governing one."""
    results: list[CheckResult] = []
    for combo in combinations:
        results += check_base_plate(bp, combine(combo, case_forces), combo.method, combo.name)
    return results, governing(results)
