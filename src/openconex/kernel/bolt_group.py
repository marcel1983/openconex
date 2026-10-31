# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Eccentrically loaded bolt groups, AISC Manual 16th ed., Part 7.

The strength of the group is C·rn, where rn is the available strength of one
bolt and C the coefficient returned here. The load acts in the plane of the
group, along a line through ``load_point`` with direction ``angle`` measured
from the vertical (y) axis, as in the Manual tables. Coordinates are relative
to any origin; the group centroid is computed.

* Elastic method: superposition of direct shear and torsion (lower bound).
* Instantaneous centre of rotation (ICR): bolt load-deformation relationship
  R = Rult (1 - e^{-10Δ})^0.55 with Δmax = 0.34 in. (Crawford and Kulak).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from openconex.core.checks import CheckResult
from openconex.kernel.design import Calc, Method
from openconex.units import Kind

__all__ = ["IcrResult", "bolt_group_eccentric", "elastic_coefficient", "icr_coefficient"]

MANUAL = "AISC Manual 16th ed., Part 7"
DELTA_MAX = 0.34  # in.


@dataclass(frozen=True)
class IcrResult:
    C: float
    """Coefficient: group strength / strength of one bolt."""
    icr: tuple[float, float]
    """Instantaneous centre of rotation (same axes as the input), or None-like inf."""
    iterations: int


def _direction(angle: float) -> tuple[float, float]:
    """Unit vector of a load at ``angle`` degrees from the vertical axis."""
    a = math.radians(angle)
    return math.sin(a), -math.cos(a)  # 0° = downward vertical load


def _centroid(bolts: list[tuple[float, float]]) -> tuple[float, float]:
    n = len(bolts)
    return sum(x for x, _ in bolts) / n, sum(y for _, y in bolts) / n


def _cross(ax: float, ay: float, bx: float, by: float) -> float:
    return ax * by - ay * bx


def _lever(bolts, load_point, angle) -> float:
    """Signed perpendicular distance from the centroid to the load line."""
    cx, cy = _centroid(bolts)
    ux, uy = _direction(angle)
    return _cross(load_point[0] - cx, load_point[1] - cy, ux, uy)


def elastic_coefficient(bolts: list[tuple[float, float]], load_point: tuple[float, float],
                        angle: float = 0.0) -> float:
    """C by the elastic method: unit load divided by the largest bolt force."""
    n = len(bolts)
    cx, cy = _centroid(bolts)
    ux, uy = _direction(angle)
    moment = _lever(bolts, load_point, angle)  # for P = 1, about the centroid
    ip = sum((x - cx) ** 2 + (y - cy) ** 2 for x, y in bolts)
    rmax = 0.0
    for x, y in bolts:
        dx, dy = x - cx, y - cy
        fx = ux / n - (moment * dy / ip if ip else 0.0)
        fy = uy / n + (moment * dx / ip if ip else 0.0)
        rmax = max(rmax, math.hypot(fx, fy))
    return 1.0 / rmax


def _bolt_response(d: float, dmax: float) -> float:
    delta = DELTA_MAX * d / dmax
    return (1 - math.exp(-10 * delta)) ** 0.55


def _residual(icr, bolts, load_point, u) -> tuple[float, float, float]:
    """Force residuals for a trial ICR and the corresponding load P (Rult = 1)."""
    x0, y0 = icr
    radii = [(x - x0, y - y0) for x, y in bolts]
    dist = [math.hypot(rx, ry) for rx, ry in radii]
    dmax = max(dist)
    lever = _cross(load_point[0] - x0, load_point[1] - y0, *u)
    sense = -1.0 if lever > 0 else 1.0  # bolt forces oppose the rotation of the load
    fx = fy = moment = 0.0
    for (rx, ry), d in zip(radii, dist, strict=True):
        if d == 0:
            continue
        r = _bolt_response(d, dmax)
        fx += sense * r * (-ry / d)
        fy += sense * r * (rx / d)
        moment += r * d
    p = moment / abs(lever)
    return fx + p * u[0], fy + p * u[1], p


def icr_coefficient(bolts: list[tuple[float, float]], load_point: tuple[float, float],
                    angle: float = 0.0, tol: float = 1e-10, max_iter: int = 200) -> IcrResult:
    """C by the instantaneous centre of rotation method (Newton iteration on the ICR)."""
    n = len(bolts)
    e = _lever(bolts, load_point, angle)
    cx, cy = _centroid(bolts)
    span = max(math.hypot(x - cx, y - cy) for x, y in bolts) or 1.0
    if abs(e) < 1e-9 * span:
        return IcrResult(float(n), (math.inf, math.inf), 0)
    u = _direction(angle)
    ip = sum((x - cx) ** 2 + (y - cy) ** 2 for x, y in bolts)
    # Start from the elastic centre of rotation: r0 = Ip / (n e) from the centroid,
    # on the perpendicular to the load, on the side opposite to the load.
    r0 = ip / (n * e) if ip else span
    px, py = u[1], -u[0]
    guess = [cx - r0 * px, cy - r0 * py]
    res = solve_icr(lambda g: _residual(g, bolts, load_point, u), guess, span, tol * n, max_iter,
                    direction=(-r0 * px, -r0 * py))
    return IcrResult(res[2], res[0], res[1])


def solve_icr(residual, guess: list[float], span: float, tol: float, max_iter: int = 200,
              direction: tuple[float, float] | None = None):
    """Damped Newton iteration on the ICR position with backtracking line search.

    ``residual(icr)`` returns (Fx, Fy, P): force residuals and the load that
    balances the moment about the trial ICR. The residual also tends to zero
    as the ICR goes to infinity (pure translation), so iterations that run away
    are abandoned and the search restarts from other points along the line
    through ``guess`` in ``direction`` (perpendicular to the load).
    Returns ((x, y), iterations, P).
    """
    starts = [guess]
    if direction is not None:
        cx, cy = guess
        for k in (0.5, 0.25, 0.75, 1.5, 0.1, 2.0, 3.0):
            starts.append([cx + (k - 1) * direction[0], cy + (k - 1) * direction[1]])
    total = 0
    for start in starts:
        result = _newton(residual, start, span, tol, max_iter)
        total += result[1]
        if result[0] is not None:
            return result[0], total, result[2]
    raise ArithmeticError("ICR iteration did not converge")


def _newton(residual, guess, span, tol, max_iter):
    h = 1e-7 * span
    origin = guess
    f1, f2, p = residual(guess)
    norm = math.hypot(f1, f2)
    for it in range(1, max_iter + 1):
        if norm < tol:
            return (guess[0], guess[1]), it, p
        if math.hypot(guess[0] - origin[0], guess[1] - origin[1]) > 200 * span:
            return None, it, p  # running away to a pure translation
        j = []
        for k in range(2):
            trial = guess.copy()
            trial[k] += h
            g1, g2, _ = residual(trial)
            j.append(((g1 - f1) / h, (g2 - f2) / h))
        det = j[0][0] * j[1][1] - j[1][0] * j[0][1]
        if det == 0:
            return None, it, p
        dx = (-f1 * j[1][1] + f2 * j[1][0]) / det
        dy = (-f2 * j[0][0] + f1 * j[0][1]) / det
        step = math.hypot(dx, dy)
        if step > span:  # damp large jumps
            dx, dy = dx * span / step, dy * span / step
        alpha = 1.0
        while alpha > 1e-4:  # backtrack until the residual decreases
            trial = [guess[0] + alpha * dx, guess[1] + alpha * dy]
            t1, t2, tp = residual(trial)
            if math.hypot(t1, t2) < norm:
                break
            alpha /= 2
        guess, f1, f2, p, norm = trial, t1, t2, tp, math.hypot(t1, t2)
    return None, max_iter, p


def bolt_group_eccentric(bolts: list[tuple[float, float]], load_point: tuple[float, float],
                         bolt_strength: float, demand: float, method: Method,
                         angle: float = 0.0, use_icr: bool = True,
                         combo: str = "") -> CheckResult:
    """Group strength C · (available strength of one bolt)."""
    clause = MANUAL + (" (instantaneous center of rotation)" if use_icr else " (elastic method)")
    c = Calc(method, combo)
    coef = (icr_coefficient(bolts, load_point, angle).C if use_icr
            else elastic_coefficient(bolts, load_point, angle))
    c.step("e", "", abs(_lever(bolts, load_point, angle)), Kind.LENGTH, clause)
    c.step("C", "ICR" if use_icr else "elastic", coef, clause=clause)
    cap = c.step(r"C\,\phi r_n" if method is Method.LRFD else r"C\,r_n/\Omega", "",
                 coef * bolt_strength, Kind.FORCE, clause)
    return c.result("bolt_group.eccentric", clause, demand, cap, Kind.FORCE)
