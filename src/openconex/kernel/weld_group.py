# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Fillet weld groups loaded in plane, AISC 360-22 §J2.4(c) and Manual Part 8.

The group is a set of straight weld lines of equal leg size ``w``, given by
their end points. Each line is divided into short elements. The load acts
along a line through ``load_point`` with direction ``angle`` from the
vertical axis (0° = downward), as in the Manual tables.

Instantaneous centre of rotation (ICR), §J2.4(c):

* Δu = 1.087 w (θ + 6)^-0.65 ≤ 0.17 w      (ultimate deformation)
* Δm = 0.209 w (θ + 2)^-0.32               (deformation at maximum stress)
* the critical element has the smallest Δu/r; Δi = ri (Δu/r)crit
* Fnw,i = 0.60 FEXX (1 + 0.50 sin^1.5 θi) [p(1.9 - 0.9p)]^0.3, p = Δi/Δm

θ is the angle between the element axis and its force. For a concentric load
all elements share the deformation of the most critical one.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from openconex.core.checks import CheckResult
from openconex.kernel.bolt_group import _cross, _direction, solve_icr
from openconex.kernel.design import SPEC, WELD, Calc, Method
from openconex.units import Kind

__all__ = [
    "WeldGroupResult",
    "WeldLine",
    "elastic_strength",
    "icr_strength",
    "weld_group_eccentric",
]

CLAUSE = f"{SPEC} §J2.4(c); AISC Manual 16th ed., Part 8"


@dataclass(frozen=True)
class WeldLine:
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def length(self) -> float:
        return math.hypot(self.x2 - self.x1, self.y2 - self.y1)


@dataclass(frozen=True)
class WeldGroupResult:
    Rn: float
    """Nominal strength of the group [N]."""
    icr: tuple[float, float]
    iterations: int


def _elements(lines: list[WeldLine], per_line: int):
    """(x, y, length, unit axis) of each element."""
    out = []
    for ln in lines:
        L = ln.length
        tx, ty = (ln.x2 - ln.x1) / L, (ln.y2 - ln.y1) / L
        for k in range(per_line):
            s = (k + 0.5) / per_line
            out.append((ln.x1 + s * (ln.x2 - ln.x1), ln.y1 + s * (ln.y2 - ln.y1),
                        L / per_line, tx, ty))
    return out


def _theta(tx: float, ty: float, fx: float, fy: float) -> float:
    cos = min(1.0, abs(tx * fx + ty * fy))
    return math.degrees(math.acos(cos))


def _du(w: float, theta: float) -> float:
    return min(1.087 * w * (theta + 6) ** -0.65, 0.17 * w)


def _dm(w: float, theta: float) -> float:
    return 0.209 * w * (theta + 2) ** -0.32


def _stress(FEXX: float, theta: float, p: float) -> float:
    f = max(p * (1.9 - 0.9 * p), 0.0) ** 0.3
    return 0.60 * FEXX * (1 + 0.5 * math.sin(math.radians(theta)) ** 1.5) * f


def _concentric(elems, w, FEXX, u) -> float:
    thetas = [_theta(tx, ty, *u) for *_, tx, ty in elems]
    throat = w / math.sqrt(2)
    if max(thetas) - min(thetas) < 1e-6:  # elements in line or parallel, §J2.4(b)
        return sum(_stress(FEXX, th, 1.0) * throat * L
                   for (_, _, L, _, _), th in zip(elems, thetas, strict=True))
    delta = min(_du(w, th) for th in thetas)
    return sum(_stress(FEXX, th, delta / _dm(w, th)) * throat * L
               for (_, _, L, _, _), th in zip(elems, thetas, strict=True))


def _residual(icr, elems, w, FEXX, load_point, u):
    x0, y0 = icr
    throat = w / math.sqrt(2)
    data = []
    for x, y, L, tx, ty in elems:
        rx, ry = x - x0, y - y0
        r = math.hypot(rx, ry)
        fdir = (-ry / r, rx / r) if r else (0.0, 0.0)
        th = _theta(tx, ty, *fdir)
        data.append((rx, ry, r, L, th))
    crit = min(_du(w, th) / r for _, _, r, _, th in data if r > 0)
    lever = _cross(load_point[0] - x0, load_point[1] - y0, *u)
    sense = -1.0 if lever > 0 else 1.0
    fx = fy = moment = 0.0
    for rx, ry, r, L, th in data:
        if r == 0:
            continue
        force = _stress(FEXX, th, crit * r / _dm(w, th)) * throat * L
        fx += sense * force * (-ry / r)
        fy += sense * force * (rx / r)
        moment += force * r
    p = moment / abs(lever)
    return fx + p * u[0], fy + p * u[1], p


def icr_strength(lines: list[WeldLine], w: float, FEXX: float, load_point: tuple[float, float],
                 angle: float = 0.0, per_line: int = 40, tol: float = 1e-9,
                 max_iter: int = 200) -> WeldGroupResult:
    """Nominal strength of the weld group by the ICR method."""
    elems = _elements(lines, per_line)
    pts = [(x, y) for x, y, *_ in elems]
    weights = [L for _, _, L, _, _ in elems]
    total = sum(weights)
    cx = sum(x * L for (x, _), L in zip(pts, weights, strict=True)) / total
    cy = sum(y * L for (_, y), L in zip(pts, weights, strict=True)) / total
    u = _direction(angle)
    e = _cross(load_point[0] - cx, load_point[1] - cy, *u)
    span = max(math.hypot(x - cx, y - cy) for x, y in pts)
    if abs(e) < 1e-9 * span:
        return WeldGroupResult(_concentric(elems, w, FEXX, u), (math.inf, math.inf), 0)
    ip = sum(((x - cx) ** 2 + (y - cy) ** 2) * L for (x, y), L in zip(pts, weights, strict=True))
    r0 = ip / (total * e)
    guess = [cx - r0 * u[1], cy + r0 * u[0]]
    scale = 0.60 * FEXX * w * total
    icr, it, p = solve_icr(lambda g: _residual(g, elems, w, FEXX, load_point, u), guess, span,
                           tol * scale, max_iter, direction=(-r0 * u[1], r0 * u[0]))
    return WeldGroupResult(p, icr, it)


def elastic_strength(lines: list[WeldLine], w: float, FEXX: float,
                     load_point: tuple[float, float], angle: float = 0.0,
                     per_line: int = 40) -> float:
    """Nominal strength by the elastic method, without the directional increase."""
    elems = _elements(lines, per_line)
    pts = [(x, y) for x, y, *_ in elems]
    total = sum(L for _, _, L, _, _ in elems)
    cx = sum(x * L for x, _, L, _, _ in elems) / total
    cy = sum(y * L for _, y, L, _, _ in elems) / total
    u = _direction(angle)
    moment = _cross(load_point[0] - cx, load_point[1] - cy, *u)  # for P = 1
    ip = sum(((x - cx) ** 2 + (y - cy) ** 2) * L for x, y, L, _, _ in elems)
    fmax = max(math.hypot(u[0] / total - moment * (y - cy) / ip,
                          u[1] / total + moment * (x - cx) / ip) for x, y in pts)
    return 0.60 * FEXX * (w / math.sqrt(2)) / fmax


def weld_group_eccentric(lines: list[WeldLine], w: float, FEXX: float,
                         load_point: tuple[float, float], demand: float, method: Method,
                         angle: float = 0.0, use_icr: bool = True,
                         combo: str = "") -> CheckResult:
    c = Calc(method, combo)
    if use_icr:
        rn = icr_strength(lines, w, FEXX, load_point, angle).Rn
        clause = CLAUSE + " (instantaneous center of rotation)"
    else:
        rn = elastic_strength(lines, w, FEXX, load_point, angle)
        clause = CLAUSE + " (elastic method)"
    rn = c.step("R_n", "ICR" if use_icr else "elastic", rn, Kind.FORCE, clause,
                w=(w, Kind.THICKNESS), F_EXX=(FEXX, Kind.STRESS))
    cap = c.available(rn, WELD, Kind.FORCE, clause)
    return c.result("weld_group.eccentric", clause, demand, cap, Kind.FORCE)
