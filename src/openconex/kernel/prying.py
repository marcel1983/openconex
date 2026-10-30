# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Prying action in tee and angle flanges, AISC Manual 16th ed., Part 9.

Notation (per bolt, along the flange):
``b``  bolt centreline to the face of the stem (tee) or leg (angle);
``a``  bolt centreline to the edge of the flange;
``p``  tributary length of flange per bolt;
``B``  available tensile strength of one bolt (φrn or rn/Ω).
"""

from __future__ import annotations

import math

from openconex.core.checks import CheckResult
from openconex.kernel.design import Calc, Method, Resistance
from openconex.units import Kind

__all__ = ["prying_min_thickness", "prying_tension"]

MANUAL = "AISC Manual 16th ed., Part 9 (prying action)"
FLANGE = Resistance(0.90, 1.67)


def _geometry(c: Calc, b: float, a: float, db: float) -> tuple[float, float]:
    bp = c.step("b'", r"b - \frac{d_b}{2}", b - db / 2, Kind.LENGTH, MANUAL)
    ap = c.step("a'", r"\min(a, 1.25b) + \frac{d_b}{2}", min(a, 1.25 * b) + db / 2, Kind.LENGTH,
                MANUAL)
    return bp, ap


def _critical_thickness(c: Calc, B: float, bp: float, p: float, Fu: float) -> float:
    if c.method is Method.LRFD:
        return c.step("t_c", r"\sqrt{\frac{4 B b'}{\phi p F_u}}",
                      math.sqrt(4 * B * bp / (FLANGE.phi * p * Fu)), Kind.THICKNESS,
                      MANUAL)
    return c.step("t_c", r"\sqrt{\frac{\Omega\, 4 B b'}{p F_u}}",
                  math.sqrt(FLANGE.omega * 4 * B * bp / (p * Fu)), Kind.THICKNESS,
                  MANUAL)


def prying_tension(B: float, t: float, b: float, a: float, p: float, db: float,
                   hole: float, Fu: float, demand: float, method: Method,
                   combo: str = "") -> CheckResult:
    """Available tension per bolt including prying, T_avail = B Q.

    ``hole`` is the hole width along the flange (d'); ``demand`` is the
    required tension per bolt (without prying).
    """
    c = Calc(method, combo)
    bp, ap = _geometry(c, b, a, db)
    rho = c.step(r"\rho", "b'/a'", bp / ap, clause=MANUAL)
    delta = c.step(r"\delta", "1 - d'/p", 1 - hole / p, clause=MANUAL)
    tc = _critical_thickness(c, B, bp, p, Fu)
    alpha_expr = r"\frac{1}{\delta(1+\rho)}\left[\left(\frac{t_c}{t}\right)^2 - 1\right]"
    alpha = c.step(r"\alpha'", alpha_expr, ((tc / t) ** 2 - 1) / (delta * (1 + rho)),
                   clause=MANUAL)
    if alpha < 0:
        q = 1.0
    elif alpha <= 1:
        q = (t / tc) ** 2 * (1 + delta * alpha)
    else:
        q = (t / tc) ** 2 * (1 + delta)
    q = c.step("Q", r"(t/t_c)^2 (1 + \delta \alpha'),\ 0 \le \alpha' \le 1", q,
               clause=MANUAL)
    cap = c.step("T_{avail}", "B Q", B * q, Kind.FORCE, MANUAL)
    return c.result("prying.tension", MANUAL, demand, cap, Kind.FORCE)


def prying_min_thickness(T: float, b: float, p: float, db: float, Fu: float,
                         thickness: float, method: Method, combo: str = "") -> CheckResult:
    """Flange thickness needed so that prying can be neglected.

    ``T`` is the required tension per bolt. The check uses demand = required
    thickness and capacity = provided thickness.
    """
    c = Calc(method, combo)
    bp = c.step("b'", r"b - \frac{d_b}{2}", b - db / 2, Kind.LENGTH, MANUAL)
    if method is Method.LRFD:
        tmin = c.step("t_{min}", r"\sqrt{\frac{4 T_u b'}{\phi p F_u}}",
                      math.sqrt(4 * T * bp / (FLANGE.phi * p * Fu)), Kind.THICKNESS,
                      MANUAL)
    else:
        tmin = c.step("t_{min}", r"\sqrt{\frac{\Omega\, 4 T_a b'}{p F_u}}",
                      math.sqrt(FLANGE.omega * 4 * T * bp / (p * Fu)), Kind.THICKNESS,
                      MANUAL)
    return c.result("prying.min_thickness", MANUAL, tmin, thickness, Kind.THICKNESS)
