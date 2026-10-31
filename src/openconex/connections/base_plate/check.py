# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Complete check of an exposed column base plate for one load combination.

The plate is rectangular, N along the strong-axis moment and B across it.
Anchors are placed in two rows parallel to B at ±f from the column axis,
``rods_per_side`` in each row, spread over ``rod_spacing``. ACI 318 anchorage
checks are strength design and run only for LRFD combinations; with ASD the
anchor rods are checked as threaded parts with AISC 360-22 §J3.

Biaxial bending (DG1 §4.3.7, Example 4.7-14): with a weak-axis moment M2 each
axis is checked separately with the rectangular bearing model (the weak axis
with N and B swapped and the outer rods of each row at ±rod_spacing/2), and
the moment strengths with the anchor rods of the tension face at their
available steel strength are combined with Eq. 4-69,
(Mx/Mx,cap)² + (My/My,cap)² ≤ 1.0. The shear is the resultant of V2 and V3.
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


def _tension_lever(bp: BasePlate, weak: bool) -> float:
    """Anchor row to the plate bending line at the tension face (DG1 Eq. 4-61)."""
    col = bp.column
    if not weak:
        return bp.f - col.d / 2 + col.tf / 2
    wall = col.tf / 2 if isinstance(col, HSSShape) else 0.0  # I shape: flange tips
    return bp.rod_spacing / 2 - col.bf / 2 + wall


def _weak_anchors(bp: BasePlate) -> bool:
    return bp.rods_per_side >= 2 and bp.rod_spacing > 0


def _bending_checks(bp: BasePlate, P_: float, M: float, N: float, B: float, f: float,
                    x: float, m: float, n: float, method: Method, combo: str,
                    suffix: str) -> tuple[bpl.BendingResult, float, list[CheckResult]]:
    """Bearing and plate thickness about one axis; returns (model, T, results)."""
    col = bp.column
    results: list[CheckResult] = []
    bend = bpl.rectangular_bending(P_, M, N, B, f, bp.fc, bp.A2_over_A1, method)
    T = 0.0
    if bend.case == "not_possible":
        c = Calc(method, combo)
        c.step("q_{max}", "f_{p(max)} B", bend.q_max, Kind.FORCE_PER_LENGTH, DG1)
        results.append(c.result(f"base_plate.bearing{suffix}", f"{DG1} §4.3.6", math.inf,
                                0.0, Kind.FORCE))
        return bend, T, results
    if bend.case == "compression_only":
        comp = bpl.compression_design(P_, col.d, col.bf, N, B, bp.Fy, bp.fc,
                                    bp.A2_over_A1, method,
                                    col.kind if isinstance(col, HSSShape) else None)
        c = Calc(method, combo)
        c.step("f_{p(max)}", r"\phi_c 0.85 f'_c \sqrt{A_2/A_1}", comp.fp_max, Kind.STRESS,
               "AISC 360-22 §J8")
        results.append(c.result(f"base_plate.bearing{suffix}", "AISC 360-22 §J8", P_,
                                comp.Pp_available, Kind.FORCE))
        results.append(_thickness(f"base_plate.thickness_compression{suffix}", comp.tp_req,
                                  bp.tp,
                                  method, combo, f"{DG1} Eq. 4-15"))
    elif bend.case == "low_moment":
        c = Calc(method, combo)
        c.step("e", "M/P", bend.e, Kind.LENGTH, f"{DG1} Eq. 4-39")
        c.step("e_{crit}", r"\frac{N}{2} - \frac{P}{2 q_{max}}", bend.e_crit, Kind.LENGTH,
               f"{DG1} Eq. 4-40")
        c.step("Y", "N - 2e", bend.Y, Kind.LENGTH, f"{DG1} Eq. 4-42")
        c.step("q", "P/Y", bend.q, Kind.FORCE_PER_LENGTH, f"{DG1} Eq. 4-43")
        c.step("q_{max}", "f_{p(max)} B", bend.q_max, Kind.FORCE_PER_LENGTH, f"{DG1} Eq. 4-37")
        results.append(c.result(f"base_plate.bearing{suffix}", f"{DG1} §4.3.3", bend.q, bend.q_max,
                                Kind.FORCE_PER_LENGTH))
        tp_req, steps = _compression_steps(method, bend.q / B, bend.Y, m, n, bp.Fy)
        results.append(_thickness(f"base_plate.thickness_compression{suffix}", tp_req, bp.tp,
                                  method, combo, f"{DG1} Eq. 4-51", steps,
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
            results.append(_thickness(f"base_plate.thickness_compression{suffix}", tp_req, bp.tp,
                                      method, combo, f"{DG1} Eq. 4-51", bearing_steps + steps,
                                      _tp_expression(method, r"\sqrt{M_{pl}/F_y}")))
        c = Calc(method, combo)
        c.step("x", "" if suffix else r"f - \frac{d}{2} + \frac{t_f}{2}", x, Kind.LENGTH,
               f"{DG1} Eq. 4-61")
        results.append(_thickness(f"base_plate.thickness_tension{suffix}",
                                  bpl.plate_thickness_tension(T, x, B, bp.Fy, method), bp.tp,
                                  method, combo, f"{DG1} Eq. 4-62", bearing_steps + c.steps,
                                  _tp_expression(method, r"\sqrt{\frac{T x}{B F_y}}")))

    return bend, T, results


def _weak_axis_without_anchors(bp: BasePlate, P_: float, M2: float, method: Method,
                               combo: str) -> CheckResult:
    """Weak-axis moment resisted by bearing only (no rods off the axis): e ≤ e_crit."""
    c = Calc(method, combo)
    q_max = c.step("q_{max}", "f_{p(max)} N", bpl.bearing_stress(bp.fc, bp.A2_over_A1, method)
                   * bp.N, Kind.FORCE_PER_LENGTH, f"{DG1} Eq. 4-37")
    capacity = max(P_, 0.0) * (bp.B / 2 - max(P_, 0.0) / (2 * q_max))
    c.step("M_{2,cap}", r"P\left(\frac{B}{2} - \frac{P}{2 q_{max}}\right)", capacity,
           Kind.MOMENT, f"{DG1} Eq. 4-40")
    return c.result("base_plate.bearing_weak", f"{DG1} §4.3.3", M2, capacity, Kind.MOMENT)


def _rod_positions(bp: BasePlate) -> list[tuple[float, float]]:
    k = bp.rods_per_side
    ys = ([-bp.rod_spacing / 2 + j * bp.rod_spacing / (k - 1) for j in range(k)] if k > 1
          else [0.0])
    return [(x, y) for x in (bp.f, -bp.f) for y in ys]


def _elastic_rod_forces(bp: BasePlate, P_: float, M: float, M2: float) -> list[float]:
    """Rod forces without bearing: -P/n + M x/Σx² + M2 y/Σy² (tension positive)."""
    rods = _rod_positions(bp)
    sx = sum(x * x for x, _ in rods)
    sy = sum(y * y for _, y in rods)
    return [-P_ / len(rods) + M * x / sx + (M2 * y / sy if sy else 0.0) for x, y in rods]


def _face_tension_capacity(bp: BasePlate, rods: int, method: Method) -> float:
    """Available tensile steel strength of the rods of one face (DG1 Example 4.7-14)."""
    if method is Method.LRFD:
        Fu = bp.rod.material.Fu
        per_rod = anchors.steel_tension(bp.rod.diameter, Fu, Fu, 0.0, method).capacity
    else:
        per_rod = bolts.bolt_tension(bp.rod, 0.0, method).capacity
    return rods * per_rod


def _biaxial_interaction(bp: BasePlate, P_: float, M: float, M2: float, method: Method,
                         combo: str) -> CheckResult:
    """(Mx/Mx,cap)² + (My/My,cap)² ≤ 1.0 (DG1 Eq. 4-69)."""
    c = Calc(method, combo)
    caps = []
    for label, moment, N, B, f, rods in (("x", M, bp.N, bp.B, bp.f, bp.rods_per_side),
                                          ("y", M2, bp.B, bp.N, bp.rod_spacing / 2, 2)):
        T_cap = c.step(f"T_{{{label},cap}}", "", _face_tension_capacity(bp, rods, method),
                       Kind.FORCE, f"{DG1} Example 4.7-14")
        Y, cap = bpl.biaxial_capacity(P_, N, B, f, bp.fc, bp.A2_over_A1, T_cap, method)
        c.step(f"Y_{{{label}}}", r"\frac{T_{cap} + P}{q_{max}}", Y, Kind.LENGTH,
               f"{DG1} §4.3.7")
        caps.append(c.step(f"M_{{{label},cap}}",
                           r"q_{max} Y\left(f + \frac{N}{2} - \frac{Y}{2}\right) - P f",
                           cap, Kind.MOMENT, f"{DG1} §4.3.7"))
        c.step(f"M_{{u{label}}}" if method is Method.LRFD else f"M_{{a{label}}}", "", moment,
               Kind.MOMENT)
    ratio = (sum((m_ / cap) ** 2 for m_, cap in zip((M, M2), caps, strict=True))
             if min(caps) > 0 else math.inf)
    c.step(r"\sum (M/M_{cap})^2", "", ratio, clause=f"{DG1} Eq. 4-69")
    return c.result("base_plate.biaxial", f"{DG1} Eq. 4-69", ratio, 1.0, Kind.DIMENSIONLESS)


def check_base_plate(bp: BasePlate, forces: Forces, method: Method,
                     combo: str = "") -> list[CheckResult]:
    """All base plate checks for one set of forces (P, V = √(V2² + V3²), M = M3, M2)."""
    col = bp.column
    P_, V = forces.P, math.hypot(forces.V2, forces.V3)
    M, M2 = abs(forces.M3), abs(forces.M2)
    results: list[CheckResult] = []
    m, n = _cantilevers(col, bp.N, bp.B)

    bend, T, axis = _bending_checks(bp, P_, M, bp.N, bp.B, bp.f, _tension_lever(bp, False),
                                    m, n, method, combo, "")
    results += axis
    if bend.case == "not_possible":
        return results
    T_weak, bend_weak = 0.0, None
    if M2:
        if _weak_anchors(bp):
            bend_weak, T_weak, axis = _bending_checks(bp, P_, M2, bp.B, bp.N, bp.rod_spacing / 2,
                                                      _tension_lever(bp, True), m, n, method,
                                                      combo, "_weak")
            results += axis
        else:
            results.append(_weak_axis_without_anchors(bp, P_, M2, method, combo))

    # --- anchors -------------------------------------------------------------
    if bend.case == "uplift" and bend.Y == 0:
        positions = [bp.f, -bp.f]
        forces_row = bpl.uplift_low_moment(P_, M, positions)
        rod_t = max(forces_row) / bp.rods_per_side
        group_t = -P_
    else:
        rod_t = T / bp.rods_per_side
        group_t = T
    if M2 and bend_weak is not None:
        # each axis separately (DG1 §4.3.7); with uplift, elastic biaxial rod forces
        if not (bend_weak.case == "uplift" and bend_weak.Y == 0):  # all rods in tension
            rod_t = max(rod_t, T_weak / 2)
        group_t = max(group_t, T_weak)
        if P_ < 0:
            elastic = _elastic_rod_forces(bp, P_, M, M2)
            rod_t = max(rod_t, max(elastic))
            group_t = max(group_t, sum(r for r in elastic if r > 0))
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

    if M2 and bend_weak is not None:
        results.append(_biaxial_interaction(bp, P_, M, M2, method, combo))

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
