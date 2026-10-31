# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Plan-view interference checks for anchor rods, washers and pedestal bars.

The checks are geometric and independent of the load combination. They use the
same anchor layout as the drawing: two rods per row at ±f, distributed over
``rod_spacing``. The washer footprint is the square plate washer from AISC
Manual Table 14-2 (or the designed thickness, which does not change its plan
size). A positive result means that the footprint is clear of the obstacle.

Coordinates are x along N (strong-axis moment) and y along B.
"""

from __future__ import annotations

import math

from openconex.core.bolting import base_plate_hole, min_edge_distance
from openconex.core.checks import CheckResult
from openconex.core.loads import Method
from openconex.core.model import HSSKind, HSSShape
from openconex.kernel.design import Calc
from openconex.units import Kind, from_internal

from .check import BasePlate

__all__ = ["anchor_interference"]

DG1 = "AISC DG1 3rd ed."
SPEC = "AISC 360-22"


def _rod_positions(bp: BasePlate) -> list[tuple[float, float]]:
    n = bp.rods_per_side
    ys = ([0.0] if n == 1 else
          [-bp.rod_spacing / 2 + i * bp.rod_spacing / (n - 1) for i in range(n)])
    return [(sx * bp.f, y) for sx in (-1, 1) for y in ys]


def _washer_size(bp: BasePlate) -> float:
    """Square plate-washer size [internal length] from Manual Table 14-2."""
    _, size, _ = base_plate_hole(from_internal(bp.rod.diameter, Kind.LENGTH, "in"))
    return size


def _distance_to_rect(px: float, py: float, x0: float, y0: float, x1: float, y1: float) -> float:
    dx = max(x0 - px, 0.0, px - x1)
    dy = max(y0 - py, 0.0, py - y1)
    return math.hypot(dx, dy)


def _column_clearance(bp: BasePlate, x: float, y: float) -> float:
    """Distance from the rod center to the column footprint (0 if inside)."""
    col = bp.column
    if isinstance(col, HSSShape) and col.kind is HSSKind.ROUND:
        return max(math.hypot(x, y) - col.d / 2, 0.0)
    return _distance_to_rect(x, y, -col.d / 2, -col.bf / 2, col.d / 2, col.bf / 2)


def _lug_rectangles(bp: BasePlate) -> list[tuple[float, float, float, float]]:
    """Plan rectangles (x0, y0, x1, y1) occupied by the shear lug."""
    lug = bp.shear_lug
    t, w = lug.thickness, lug.width
    rects = []
    if lug.direction in ("strong", "both"):
        rects.append((-t / 2, -w / 2, t / 2, w / 2))
    if lug.direction in ("weak", "both"):
        rects.append((-w / 2, -t / 2, w / 2, t / 2))
    return rects


def _min_lug_clearance(bp: BasePlate, x: float, y: float) -> float:
    return min(_distance_to_rect(x, y, *rect) for rect in _lug_rectangles(bp))


def _check_column(bp: BasePlate, positions: list[tuple[float, float]], half: float,
                  method: Method, combo: str) -> CheckResult:
    c = Calc(method, combo)
    c.step("a_{ws}", "Tabla 14-2", 2 * half, Kind.LENGTH, "AISC Manual Tabla 14-2")
    c.step(r"a_{ws}/2", "", half, Kind.LENGTH, DG1)
    clearance = min(_column_clearance(bp, x, y) for x, y in positions)
    c.step("c_{col,min}", "mínima distancia al contorno de la columna", clearance,
           Kind.LENGTH, DG1)
    return c.result("base_plate.anchor_column_clearance", f"{DG1} §4.2", half,
                    clearance, Kind.LENGTH)


def _check_plate_edge(bp: BasePlate, positions: list[tuple[float, float]], half: float,
                      method: Method, combo: str) -> CheckResult:
    d_in = from_internal(bp.rod.diameter, Kind.LENGTH, "in")
    table_edge = min_edge_distance(d_in)
    required = max(table_edge, half)
    actual = min(min(bp.N / 2 - abs(x), bp.B / 2 - abs(y)) for x, y in positions)
    c = Calc(method, combo)
    c.step("l_{e,min}", "Tabla J3.4", table_edge, Kind.LENGTH, f"{SPEC} Tabla J3.4")
    c.step(r"a_{ws}/2", "", half, Kind.LENGTH, "AISC Manual Tabla 14-2")
    c.step("l_{e,req}", r"\max(l_{e,min},\ a_{ws}/2)", required, Kind.LENGTH,
           f"{SPEC} §J3.4")
    c.step("l_{e,prov}", "mínima distancia del eje a un borde de la placa", actual,
           Kind.LENGTH, DG1)
    return c.result("base_plate.anchor_plate_edge", f"{SPEC} §J3.4", required,
                    actual, Kind.LENGTH)


def _check_lug(bp: BasePlate, positions: list[tuple[float, float]], half: float,
               method: Method, combo: str) -> CheckResult:
    clearance = min(_min_lug_clearance(bp, x, y) for x, y in positions)
    c = Calc(method, combo)
    c.step(r"a_{ws}/2", "", half, Kind.LENGTH, "AISC Manual Tabla 14-2")
    c.step("c_{lug,min}", "mínima distancia del eje a la llave de corte", clearance,
           Kind.LENGTH, f"{DG1} §4.5")
    return c.result("base_plate.anchor_lug_clearance", f"{DG1} §4.5", half,
                    clearance, Kind.LENGTH)


def _check_rebars(bp: BasePlate, positions: list[tuple[float, float]], method: Method,
                  combo: str) -> CheckResult:
    pairs = []
    for x, y in positions:
        for bar in bp.pedestal_rebars:
            required = (bp.rod.diameter + bar.diameter) / 2
            actual = math.hypot(x - bar.x, y - bar.y)
            ratio = math.inf if actual <= 0 else required / actual
            pairs.append((ratio, required, actual, x, y, bar))
    _, required, actual, x, y, bar = max(pairs, key=lambda item: item[0])
    c = Calc(method, combo)
    c.step("d_a/2 + d_b/2", "", required, Kind.LENGTH, f"{SPEC} §J3.3")
    c.step("c_{bar}", "distancia libre entre ejes", actual, Kind.LENGTH,
           f"{SPEC} §J3.3; ACI 318-19 §25.2")
    c.step("x_a", "", x, Kind.LENGTH, DG1, y_a=(y, Kind.LENGTH),
           x_b=(bar.x, Kind.LENGTH), y_b=(bar.y, Kind.LENGTH),
           d_b=(bar.diameter, Kind.LENGTH))
    return c.result("base_plate.anchor_rebar_clearance", f"{SPEC} §J3.3", required,
                    actual, Kind.LENGTH)


def anchor_interference(bp: BasePlate, method: Method, combo: str = "") -> list[CheckResult]:
    """Checks for anchor/washer clashes with the column, plate edge, lug and bars."""
    positions = _rod_positions(bp)
    half = _washer_size(bp) / 2
    results = [
        _check_column(bp, positions, half, method, combo),
        _check_plate_edge(bp, positions, half, method, combo),
    ]
    if bp.shear_lug is not None:
        results.append(_check_lug(bp, positions, half, method, combo))
    if bp.pedestal_rebars:
        results.append(_check_rebars(bp, positions, method, combo))
    return results
