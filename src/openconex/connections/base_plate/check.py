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

Shear lug (DG1 §4.5, Example 4.7-5; ACI 318-19 §17.11): the lug takes the
shear component across its width (V2 for a lug along B, V3 for a lug along N,
both for a cruciform lug); the rest goes to friction or to the rods. Its
moment V e, with e = grout + h_sl/2, is added to the plate moment about the
same axis and resisted by bearing and the rods. Checks: concrete bearing
(ψbrg,sl from the axial load) and breakout toward an edge (when ca1 is given),
shear and flexure of the lug plate, its fillet welds, and hef ≥ 2.5 h_sl.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from openconex.core.checks import CheckResult, governing
from openconex.core.loads import Forces, LoadCombination, Method, combine
from openconex.core.materials import STEELS, SteelGrade
from openconex.core.model import BoltSpec, FilletWeld, HSSKind, HSSShape, IShape
from openconex.kernel import anchors, bolts
from openconex.kernel.design import Calc
from openconex.units import Kind

from . import plate as bpl
from . import seismic, transfer

__all__ = [
    "BasePlate",
    "BearingAreaModel",
    "PressureModel",
    "Reinforcement",
    "ShearLug",
    "WeakBase",
    "check_base_plate",
    "check_envelope",
]

DG1 = "AISC DG1 3rd ed."


class PressureModel(StrEnum):
    RECTANGULAR = "rectangular"
    """Uniform bearing stress over the compression block (DG1 §4.3)."""
    TRIANGULAR = "triangular"
    """Linear bearing stress over the compression block (DG1 Appendix B)."""


class BearingAreaModel(StrEnum):
    PLATE = "plate"
    """Bearing capacity over the full plate area B × N."""
    EFFECTIVE = "effective"
    """Bearing capacity over the effective area under the column (DG1 App. B.3)."""


@dataclass(frozen=True)
class ShearLug:
    width: float
    """b_sl, across the shear."""
    embedment: float
    """h_sl, depth bearing on the concrete (below the grout)."""
    thickness: float
    weld: float
    """Fillet weld size on both faces of the lug."""
    direction: str = "strong"
    """"strong": resists V2 (lug along B); "weak": V3 (along N); "both": cruciform."""
    grade: str = "ASTM A572 Gr. 50"
    FEXX: float = 482.633  # E70XX
    grout: float = 0.0
    ca1: float | None = None
    """Edge distance in the shear direction for concrete breakout (None: not checked)."""
    ca2: tuple[float | None, float | None] = (None, None)
    """Edge distances at both sides of the lug (None: far)."""

    def resisted(self, V2: float, V3: float) -> tuple[float, float]:
        """Shear components (strong, weak) taken by the lug."""
        return (abs(V2) if self.direction in ("strong", "both") else 0.0,
                abs(V3) if self.direction in ("weak", "both") else 0.0)


@dataclass(frozen=True)
class Reinforcement:
    """Hooked anchor reinforcement developed on both sides of the breakout."""

    area: float
    fy: float
    db: float
    clear_cover: float
    anchor_to_bar: float
    """Horizontal distance from the anchor to the reinforcing bar."""
    le: float
    """Available development length."""
    bars: str = ""


@dataclass(frozen=True)
class WeakBase:
    """Weak base with ductile (upset-thread) anchor rods, DG1 §6.4."""

    reduced_diameter: float
    stretch_length: float
    Rt: float = 1.2


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
    shear_lug: ShearLug | None = None
    materials: Mapping[str, SteelGrade] = field(default_factory=lambda: dict(STEELS), repr=False)
    """Steel library used by the plate and the shear lug; defaults to the built-ins."""
    pressure_model: PressureModel = PressureModel.RECTANGULAR
    bearing_area_model: BearingAreaModel = BearingAreaModel.PLATE
    rod_bending_lever: float | None = None
    """Distance from the anchor to the supporting web/flange for plate bending at the rods."""
    reinforcement: Reinforcement | None = None
    weak_base: WeakBase | None = None

    @property
    def Fy(self) -> float:
        return self.materials[self.plate_grade].Fy

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


def _cantilevers_weak(column: IShape | HSSShape, N: float, B: float) -> tuple[float, float]:
    """Critical projections m and n for M2, with the column rotated 90°.

    The plate bending direction is now B, so m is measured against the flange
    width and n against the depth (DG1 §4.3.7).
    """
    if isinstance(column, HSSShape):
        coefficient = 0.8 if column.kind is HSSKind.ROUND else 0.95
        return (B - coefficient * column.bf) / 2, (N - coefficient * column.d) / 2
    return (B - 0.95 * column.bf) / 2, (N - 0.8 * column.d) / 2


def _tension_lever(bp: BasePlate, weak: bool) -> float:
    """Anchor row to the plate bending line at the tension face (DG1 Eq. 4-61)."""
    col = bp.column
    if not weak:
        return bp.f - col.d / 2 + col.tf / 2
    wall = col.tf / 2 if isinstance(col, HSSShape) else 0.0  # I shape: flange tips
    return bp.rod_spacing / 2 - col.bf / 2 + wall


def _weak_anchors(bp: BasePlate) -> bool:
    return bp.rods_per_side >= 2 and bp.rod_spacing > 0


def _triangular_bending(t: bpl.TriangularResult, P_: float, B: float) -> bpl.BendingResult:
    """Adapt the triangular model to the common bending result."""
    if t.case == "not_possible":
        return bpl.BendingResult("not_possible", t.e, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    if t.case == "low_moment":
        return bpl.BendingResult(
            "low_moment", t.e, t.e_kern, t.fp_available * B, t.fp_max, t.bearing_length,
            P_ / t.bearing_length, 0.0, M_plate=t.M_plate, M_plate_tension=0.0,
            bearing_stress=t.fp_max, bearing_capacity=t.fp_available)
    return bpl.BendingResult(
        "large_moment", t.e, t.e_kern, t.fp_available * B, t.fp_max, t.bearing_length,
        t.fp_available * B, t.T, M_plate=t.M_plate,
        M_plate_tension=t.M_plate_tension, bearing_stress=t.fp_max,
        bearing_capacity=t.fp_available)


def _bending_checks(bp: BasePlate, P_: float, M: float, N: float, B: float, f: float,
                    x: float, m: float, n: float, method: Method, combo: str,
                    suffix: str, pressure_model: PressureModel = PressureModel.RECTANGULAR,
                    rod_edge: float = 0.0, rods_in_tension: int = 2,
                    tension_demand: float | None = None
                    ) -> tuple[bpl.BendingResult, float, list[CheckResult]]:
    """Bearing and plate thickness about one axis; returns (model, T, results)."""
    col = bp.column
    results: list[CheckResult] = []
    if pressure_model is PressureModel.TRIANGULAR:
        triangular = bpl.triangular_bending(
            P_, M, N, B, m, n, bp.fc, bp.A2_over_A1, method, rod_edge=rod_edge,
            rods_in_tension=rods_in_tension)
        bend = _triangular_bending(triangular, P_, B)
    else:
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
        if bp.bearing_area_model is BearingAreaModel.EFFECTIVE:
            if isinstance(col, HSSShape):
                raise ValueError("effective bearing area is only defined for I-shapes")
            _, area = bpl.effective_area(col.d, col.bf, col.tf, col.tw, bp.tp, N, B)
            c.step("A_{eff}", "", area, Kind.AREA, f"{DG1} App. B.3")
            capacity = comp.fp_max * area
        else:
            capacity = comp.Pp_available
        results.append(c.result(f"base_plate.bearing{suffix}", "AISC 360-22 §J8", P_,
                                capacity, Kind.FORCE))
        results.append(_thickness(f"base_plate.thickness_compression{suffix}", comp.tp_req,
                                  bp.tp,
                                  method, combo, f"{DG1} Eq. 4-15"))
    elif bend.case == "low_moment":
        c = Calc(method, combo)
        if bend.bearing_stress is not None:
            c.step("f_{p,max}", "", bend.bearing_stress, Kind.STRESS, f"{DG1} App. B.2")
            results.append(c.result(f"base_plate.bearing{suffix}", f"{DG1} App. B.2",
                                    bend.bearing_stress, bend.bearing_capacity, Kind.STRESS))
        else:
            c.step("e", "M/P", bend.e, Kind.LENGTH, f"{DG1} Eq. 4-39")
            c.step("e_{crit}", r"\frac{N}{2} - \frac{P}{2 q_{max}}", bend.e_crit,
                   Kind.LENGTH, f"{DG1} Eq. 4-40")
            c.step("Y", "N - 2e", bend.Y, Kind.LENGTH, f"{DG1} Eq. 4-42")
            c.step("q", "P/Y", bend.q, Kind.FORCE_PER_LENGTH, f"{DG1} Eq. 4-43")
            c.step("q_{max}", "f_{p(max)} B", bend.q_max, Kind.FORCE_PER_LENGTH,
                   f"{DG1} Eq. 4-37")
            results.append(c.result(f"base_plate.bearing{suffix}", f"{DG1} §4.3.3", bend.q,
                                    bend.q_max, Kind.FORCE_PER_LENGTH))
        if bend.M_plate is not None:
            c.step("M_{pl}", "", bend.M_plate, Kind.MOMENT, f"{DG1} App. B.2")
            tp_req = bpl.plate_thickness_from_moment(bend.M_plate, bp.Fy, method)
            results.append(_thickness(
                f"base_plate.thickness_compression{suffix}", tp_req, bp.tp, method, combo,
                f"{DG1} App. B.2", c.steps, _tp_expression(method, r"\sqrt{M_{pl}/F_y}")))
        else:
            tp_req, steps = _compression_steps(method, bend.q / B, bend.Y, m, n, bp.Fy)
            results.append(_thickness(f"base_plate.thickness_compression{suffix}", tp_req,
                                      bp.tp, method, combo, f"{DG1} Eq. 4-51", steps,
                                      _tp_expression(method, r"\sqrt{M_{pl}/F_y}")))
    else:
        T = bend.T
        c = Calc(method, combo)
        c.step("q_{max}", "f_{p(max)} B", bend.q_max, Kind.FORCE_PER_LENGTH, f"{DG1} Eq. 4-37")
        c.step("Y", r"\left(f + \frac{N}{2}\right) - \sqrt{\left(f + \frac{N}{2}\right)^2 - "
               r"\frac{2(Pf + M)}{q_{max}}}", bend.Y, Kind.LENGTH, f"{DG1} Eq. 4-58")
        c.step("T", "q_{max} Y - P", T, Kind.FORCE, f"{DG1} Eq. 4-55")
        bearing_steps = list(c.steps)
        if bend.bearing_stress is not None:
            results.append(c.result(f"base_plate.bearing{suffix}", f"{DG1} App. B.2",
                                    bend.bearing_stress, bend.bearing_capacity, Kind.STRESS))
        if bend.M_plate is not None:
            c.step("M_{pl}", "", bend.M_plate, Kind.MOMENT, f"{DG1} App. B.2")
            tp_req = bpl.plate_thickness_from_moment(bend.M_plate, bp.Fy, method)
            results.append(_thickness(
                f"base_plate.thickness_compression{suffix}", tp_req, bp.tp, method, combo,
                f"{DG1} App. B.2", bearing_steps + c.steps,
                _tp_expression(method, r"\sqrt{M_{pl}/F_y}")))
        elif bend.Y > 0:
            tp_req, steps = _compression_steps(method, bend.fp_max, bend.Y, m, n, bp.Fy)
            results.append(_thickness(f"base_plate.thickness_compression{suffix}", tp_req,
                                      bp.tp, method, combo, f"{DG1} Eq. 4-51",
                                      bearing_steps + steps,
                                      _tp_expression(method, r"\sqrt{M_{pl}/F_y}")))
        if bend.M_plate_tension is not None and bend.M_plate_tension > 0:
            c = Calc(method, combo)
            c.step("M_{pl,t}", "", bend.M_plate_tension, Kind.MOMENT, f"{DG1} App. B.2")
            tp_req = bpl.plate_thickness_from_moment(bend.M_plate_tension, bp.Fy, method)
            results.append(_thickness(
                f"base_plate.thickness_tension{suffix}", tp_req, bp.tp, method, combo,
                f"{DG1} App. B.2", bearing_steps + c.steps,
                _tp_expression(method, r"\sqrt{M_{pl,t}/F_y}")))
        else:
            c = Calc(method, combo)
            c.step("x", "" if suffix else r"f - \frac{d}{2} + \frac{t_f}{2}", x, Kind.LENGTH,
                   f"{DG1} Eq. 4-61")
            tension = T if tension_demand is None else tension_demand
            if tension != T:
                c.step("T_{req}", "", tension, Kind.FORCE, f"{DG1} §6.4")
            results.append(_thickness(
                f"base_plate.thickness_tension{suffix}",
                bpl.plate_thickness_tension(tension, x, B, bp.Fy, method), bp.tp, method,
                combo, f"{DG1} Eq. 4-62", bearing_steps + c.steps,
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


_LUG_IDS = {"element.shear_yielding": "lug_shear_yielding",
            "element.shear_rupture": "lug_shear_rupture",
            "element.flexural_yielding": "lug_flexural_yielding",
            "element.flexural_rupture": "lug_flexural_rupture"}


def _renamed(check: CheckResult, key: str, steps: tuple = ()) -> CheckResult:
    return check.model_copy(update={"id": f"base_plate.{key}",
                                    "text_id": f"check.base_plate.{key}",
                                    "steps": (*steps, *check.steps)})


def _shear_lug_checks(bp: BasePlate, P_: float, shears: tuple[float, float], method: Method,
                      combo: str) -> list[CheckResult]:
    lug = bp.shear_lug
    steel = bp.materials[lug.grade]
    out: list[CheckResult] = []
    for V in (v for v in shears if v > 0):
        c = Calc(method, combo)
        e = c.step("e", r"g + \frac{h_{sl}}{2}", lug.grout + lug.embedment / 2, Kind.LENGTH,
                   f"{DG1} Example 4.7-5", g=(lug.grout, Kind.LENGTH),
                   h_sl=(lug.embedment, Kind.LENGTH))
        M = c.step("M_{sl}", "V e", V * e, Kind.MOMENT, f"{DG1} Example 4.7-5")
        if method is Method.LRFD:
            out.append(_lug_bearing(bp, P_, V, method, combo))
            if lug.ca1:
                out.append(anchors.shear_lug_breakout(lug.width, lug.embedment, lug.ca1, bp.fc,
                                                      V, method, ca2=lug.ca2, combo=combo))
        for check in transfer.lug_steel_checks(lug.width, lug.thickness, steel.Fy, steel.Fu, V,
                                               M, method, combo):
            out.append(_renamed(check, _LUG_IDS[check.id], tuple(c.steps)))
        out.append(_renamed(transfer.lug_weld(lug.width, lug.thickness, lug.weld, lug.FEXX, V, M,
                                              method, combo), "lug_weld", tuple(c.steps)))
    if bp.hef:
        c = Calc(method, combo)
        need = c.step(r"2.5 h_{sl}", "", 2.5 * lug.embedment, Kind.LENGTH,
                      "ACI 318-19 §17.11.1")
        out.append(c.result("base_plate.lug_anchor_embedment", "ACI 318-19 §17.11.1", need,
                            bp.hef, Kind.LENGTH))
    return out


def _lug_bearing(bp: BasePlate, P_: float, V: float, method: Method,
                 combo: str) -> CheckResult:
    """Bearing of the lug with ψbrg,sl from the axial load (ACI 318-19 §17.11.2.2)."""
    lug = bp.shear_lug
    c = Calc(method, combo)
    if P_ < 0:
        Fu = bp.rod.material.Fu  # 1.9 Fy never governs for F1554 / F3125 rods
        nsa = anchors.tensile_stress_area(bp.rod.diameter) * anchors.futa(Fu, Fu)
        psi = c.step(r"\psi_{brg,sl}", r"1 + \frac{P_u}{n N_{sa}} \le 1",
                     max(min(1 + P_ / (bp.rods * nsa), 1.0), 0.0), clause="ACI 318-19 §17.11.2.2")
    else:
        psi = c.step(r"\psi_{brg,sl}", r"1 + \frac{4 P_u}{A_{bp} f'_c} \le 2",
                     min(1 + 4 * P_ / (bp.N * bp.B * bp.fc), 2.0),
                     clause="ACI 318-19 §17.11.2.2")
    check = anchors.shear_lug_bearing(lug.width, lug.embedment, bp.fc, V, method, psi, combo)
    return check.model_copy(update={"steps": (*c.steps, *check.steps)})


def check_base_plate(bp: BasePlate, forces: Forces, method: Method,
                     combo: str = "") -> list[CheckResult]:
    """All base plate checks for one set of forces (P, V = √(V2² + V3²), M = M3, M2)."""
    col = bp.column
    P_, V = forces.P, math.hypot(forces.V2, forces.V3)
    M, M2 = abs(forces.M3), abs(forces.M2)
    lug_shear = (0.0, 0.0)
    if bp.shear_lug:
        lug_shear = bp.shear_lug.resisted(forces.V2, forces.V3)
        e = bp.shear_lug.grout + bp.shear_lug.embedment / 2
        M, M2 = M + lug_shear[0] * e, M2 + lug_shear[1] * e
        V = math.hypot(abs(forces.V2) - lug_shear[0], abs(forces.V3) - lug_shear[1])
    results: list[CheckResult] = []
    m, n = _cantilevers(col, bp.N, bp.B)
    if bp.pressure_model is PressureModel.TRIANGULAR and M2:
        raise ValueError("the triangular pressure model does not support weak-axis moment yet")
    weak = bp.weak_base if method is Method.LRFD else None
    ductile = None
    tension_demand = None
    if weak is not None:
        if bp.pressure_model is not PressureModel.RECTANGULAR:
            raise ValueError("weak base requires the rectangular pressure model")
        if M2:
            raise ValueError("weak base does not support weak-axis moment yet")
        if bp.rod.material.Fy is None:
            raise ValueError("weak base requires an anchor grade with a defined yield stress")
        preliminary = bpl.rectangular_bending(P_, M, bp.N, bp.B, bp.f, bp.fc,
                                              bp.A2_over_A1, method)
        if preliminary.T > 0:
            ductile = seismic.ductile_anchors(
                preliminary.T, bp.rods_per_side, bp.rod.material.Fy, bp.rod.material.Fu,
                weak.reduced_diameter, bp.f, bp.rod.diameter, weak.Rt)
            tension_demand = ductile.N_required
    triangular = bp.pressure_model is PressureModel.TRIANGULAR and P_ > 0

    bend, T, axis = _bending_checks(
        bp, P_, M, bp.N, bp.B, bp.f, _tension_lever(bp, False), m, n, method, combo, "",
        PressureModel.TRIANGULAR if triangular else PressureModel.RECTANGULAR,
        rod_edge=bp.N / 2 - bp.f, rods_in_tension=bp.rods_per_side,
        tension_demand=tension_demand)
    results += axis
    if ductile is not None and weak is not None:
        c = Calc(method, combo)
        c.step(r"T_{red}", r"\frac{\pi d_r^2}{4}F_u", ductile.T_reduced, Kind.FORCE,
               f"{DG1} §6.4.2")
        c.step(r"R_t T_{red}", "", ductile.RtT_reduced, Kind.FORCE, f"{DG1} §6.4.2")
        c.step("N_{req}", r"n R_t T_{red}", ductile.N_required, Kind.FORCE,
               f"{DG1} §6.4.2")
        c.step("A_{s,red,req}", r"\frac{T}{n\phi F_y}", ductile.A_reduced_min,
               Kind.AREA, f"{DG1} §6.4.2")
        provided = math.pi * weak.reduced_diameter**2 / 4
        results.append(c.result("base_plate.weak_base_area", f"{DG1} §6.4.2",
                                ductile.A_reduced_min, provided, Kind.AREA))
        c = Calc(method, combo)
        c.step("L_{stretch,min}", r"\max(8d_a,\ f)", ductile.L_stretch_min, Kind.LENGTH,
               f"{DG1} §6.4.2")
        results.append(c.result("base_plate.weak_base_stretch", f"{DG1} §6.4.2",
                                ductile.L_stretch_min, weak.stretch_length, Kind.LENGTH))
    if bend.case == "not_possible":
        return results
    T_weak, bend_weak = 0.0, None
    if M2:
        if _weak_anchors(bp):
            m_weak, n_weak = _cantilevers_weak(col, bp.N, bp.B)
            bend_weak, T_weak, axis = _bending_checks(bp, P_, M2, bp.B, bp.N, bp.rod_spacing / 2,
                                                      _tension_lever(bp, True), m_weak, n_weak,
                                                      method, combo, "_weak")
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
    rod_t_nd = rod_t
    if ductile is not None:
        rod_t_nd = max(rod_t, ductile.RtT_reduced)
        group_t = max(group_t, ductile.N_required)
    if bp.rod_bending_lever is not None and rod_t > 0:
        results.append(transfer.plate_bending_at_rods(
            rod_t, bp.rod_bending_lever, bp.tp, bp.Fy, method, combo))
    shear_rods = bp.rods if bp.washer_thickness else max(bp.rods_per_side, 1)
    rod_v = V / shear_rods
    use_friction = P_ > 0 and method is Method.LRFD and not bp.washer_thickness
    # futa = min(Fu, 1.9 Fy, 125 ksi): 1.9 Fy never governs for ASTM F1554 / F3125 rods.
    Fu = Fy = bp.rod.material.Fu
    if method is Method.LRFD:
        if rod_t > 0:
            results.append(anchors.steel_tension(bp.rod.diameter, Fu, Fy, rod_t, method, combo))
            if bp.reinforcement is not None:
                reinforcement = bp.reinforcement
                results += anchors.anchor_reinforcement_design(
                    group_t, reinforcement.fy, reinforcement.area, reinforcement.db,
                    reinforcement.clear_cover, reinforcement.anchor_to_bar, bp.fc,
                    bp.hef, reinforcement.le, method, combo)
            elif bp.hef:
                bo = anchors.breakout_tension(bp.hef, bp.fc, group_t, method,
                                              span_x=bp.rod_spacing, edges=bp.edges,
                                              cracked=bp.cracked, seismic=bp.seismic,
                                              combo=combo)
                results.append(bo)
            area = bp.bearing_area or anchors.heavy_hex_bearing_area(bp.rod.diameter)
            results.append(anchors.pullout(area, bp.fc, rod_t_nd, method, bp.cracked,
                                           bp.seismic, combo))
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
        results.append(transfer.rod_tension_shear_bending(
            bp.rod, bp.rods, max(group_t, rod_t_nd * bp.rods_per_side), V, bp.tp,
            bp.washer_thickness, method, combo))

    if M2 and bend_weak is not None:
        results.append(_biaxial_interaction(bp, P_, M, M2, method, combo))
    if bp.shear_lug and any(lug_shear):
        results += _shear_lug_checks(bp, P_, lug_shear, method, combo)

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
