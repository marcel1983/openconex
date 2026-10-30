# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Flanges and webs with concentrated forces, AISC 360-22 Section J10.

Applies to rolled or built-up I-shapes (:class:`~openconex.core.model.IShape`);
Qf = 1.0 (not HSS). ``lb`` is the length of bearing of the concentrated force.
"""

from __future__ import annotations

import math

from openconex.core.checks import CheckResult
from openconex.core.materials import E_STEEL
from openconex.core.model import IShape
from openconex.kernel.design import SPEC, Calc, Method, Resistance
from openconex.units import Kind

__all__ = [
    "flange_local_bending",
    "panel_zone_shear",
    "web_compression_buckling",
    "web_local_crippling",
    "web_local_yielding",
]

J10_090 = Resistance(0.90, 1.67)
J10_100 = Resistance(1.00, 1.50)
J10_075 = Resistance(0.75, 2.00)


def flange_local_bending(shape: IShape, demand: float, method: Method, near_end: bool = False,
                         combo: str = "") -> CheckResult:
    """Rn = 6.25 Fyf tf² (Eq. J10-1); halved within 10 tf of the member end."""
    clause = f"{SPEC} §J10.1, Eq. J10-1"
    c = Calc(method, combo)
    fy, tf = shape.material.Fy, shape.tf
    rn = c.step("R_n", "6.25 F_{yf} t_f^2", 6.25 * fy * tf * tf, Kind.FORCE, clause,
                F_yf=(fy, Kind.STRESS), t_f=(tf, Kind.THICKNESS))
    if near_end:
        rn = c.step("R_n", r"0.50 R_n\ (\le 10 t_f\ \text{from end})", 0.5 * rn, Kind.FORCE,
                    clause)
    return c.result("local.flange_bending", clause, demand,
                    c.available(rn, J10_090, Kind.FORCE, clause), Kind.FORCE)


def web_local_yielding(shape: IShape, lb: float, demand: float, method: Method,
                       near_end: bool = False, combo: str = "") -> CheckResult:
    """Rn = Fyw tw (5k + lb) (Eq. J10-2), or (2.5k + lb) within d of the end (Eq. J10-3)."""
    c = Calc(method, combo)
    fy, tw, k = shape.material.Fy, shape.tw, shape.k_des
    if near_end:
        clause = f"{SPEC} §J10.2, Eq. J10-3"
        rn = c.step("R_n", "F_{yw} t_w (2.5k + l_b)", fy * tw * (2.5 * k + lb), Kind.FORCE,
                    clause, k=(k, Kind.LENGTH), l_b=(lb, Kind.LENGTH))
    else:
        clause = f"{SPEC} §J10.2, Eq. J10-2"
        rn = c.step("R_n", "F_{yw} t_w (5k + l_b)", fy * tw * (5 * k + lb), Kind.FORCE,
                    clause, k=(k, Kind.LENGTH), l_b=(lb, Kind.LENGTH))
    return c.result("local.web_yielding", clause, demand,
                    c.available(rn, J10_100, Kind.FORCE, clause), Kind.FORCE)


def web_local_crippling(shape: IShape, lb: float, demand: float, method: Method,
                        near_end: bool = False, combo: str = "") -> CheckResult:
    """Web local crippling (§J10.3, Eq. J10-4 and J10-5a/b).

    ``near_end`` means the force is applied at less than d/2 from the member end.
    """
    c = Calc(method, combo)
    fy, tw, tf, d = shape.material.Fy, shape.tw, shape.tf, shape.d
    root = math.sqrt(E_STEEL * fy * tf / tw)
    ratio = (tw / tf) ** 1.5
    if not near_end:
        clause = f"{SPEC} §J10.3, Eq. J10-4"
        rn = 0.80 * tw**2 * (1 + 3 * (lb / d) * ratio) * root
        expr = r"0.80 t_w^2 \left[1 + 3\frac{l_b}{d}\left(\frac{t_w}{t_f}\right)^{1.5}\right]"
    elif lb / d <= 0.2:
        clause = f"{SPEC} §J10.3, Eq. J10-5a"
        rn = 0.40 * tw**2 * (1 + 3 * (lb / d) * ratio) * root
        expr = r"0.40 t_w^2 \left[1 + 3\frac{l_b}{d}\left(\frac{t_w}{t_f}\right)^{1.5}\right]"
    else:
        clause = f"{SPEC} §J10.3, Eq. J10-5b"
        rn = 0.40 * tw**2 * (1 + (4 * lb / d - 0.2) * ratio) * root
        expr = (r"0.40 t_w^2 \left[1 + \left(\frac{4 l_b}{d} - 0.2\right)"
                r"\left(\frac{t_w}{t_f}\right)^{1.5}\right]")
    rn = c.step("R_n", expr + r"\sqrt{\frac{E F_{yw} t_f}{t_w}} Q_f", rn, Kind.FORCE, clause,
                l_b=(lb, Kind.LENGTH), d=(d, Kind.LENGTH))
    return c.result("local.web_crippling", clause, demand,
                    c.available(rn, J10_075, Kind.FORCE, clause), Kind.FORCE)


def web_compression_buckling(shape: IShape, demand: float, method: Method,
                             near_end: bool = False, combo: str = "") -> CheckResult:
    """Pair of compressive forces on both flanges: Rn = 24 tw³ √(E Fyw) Qf / h (Eq. J10-8).

    h is taken as d - 2 k_des; halved when the forces act within d/2 of the end.
    """
    clause = f"{SPEC} §J10.5, Eq. J10-8"
    c = Calc(method, combo)
    fy, tw = shape.material.Fy, shape.tw
    h = c.step("h", "d - 2k_{des}", shape.d - 2 * shape.k_des, Kind.LENGTH, clause)
    rn = c.step("R_n", r"\frac{24 t_w^3 \sqrt{E F_{yw}}}{h} Q_f",
                24 * tw**3 * math.sqrt(E_STEEL * fy) / h, Kind.FORCE, clause)
    if near_end:
        rn = c.step("R_n", r"0.50 R_n", 0.5 * rn, Kind.FORCE, clause)
    return c.result("local.web_compression_buckling", clause, demand,
                    c.available(rn, J10_090, Kind.FORCE, clause), Kind.FORCE)


def panel_zone_shear(column: IShape, Pr: float, demand: float, method: Method,
                     beam_depth: float | None = None, inelastic: bool = False,
                     combo: str = "") -> CheckResult:
    """Web panel zone shear (§J10.6).

    Without considering panel-zone inelastic deformation in the stability
    analysis: Eq. J10-9/J10-10. With it (``inelastic``, needs ``beam_depth``):
    Eq. J10-11/J10-12. ``Pr`` is the required axial strength of the column.
    """
    c = Calc(method, combo)
    fy, dc, tw = column.material.Fy, column.d, column.tw
    py = c.step("P_y", "F_y A_g", fy * column.area, Kind.FORCE, f"{SPEC} §J10.6")
    alpha = 1.0 if method is Method.LRFD else 1.6
    load = c.step(r"\alpha P_r / P_y", "", alpha * Pr / py, clause=f"{SPEC} §J10.6")
    base = 0.60 * fy * dc * tw
    if not inelastic:
        if load <= 0.4:
            clause = f"{SPEC} §J10.6, Eq. J10-9"
            rn = c.step("R_n", "0.60 F_y d_c t_w", base, Kind.FORCE, clause)
        else:
            clause = f"{SPEC} §J10.6, Eq. J10-10"
            rn = c.step("R_n", r"0.60 F_y d_c t_w (1.4 - \alpha P_r/P_y)", base * (1.4 - load),
                        Kind.FORCE, clause)
    else:
        if beam_depth is None:
            raise ValueError("beam_depth is required when inelastic deformation is considered")
        extra = 1 + 3 * column.bf * column.tf**2 / (beam_depth * dc * tw)
        if load <= 0.75:
            clause = f"{SPEC} §J10.6, Eq. J10-11"
            rn = c.step("R_n", r"0.60 F_y d_c t_w \left(1 + \frac{3 b_{cf} t_{cf}^2}"
                        r"{d_b d_c t_w}\right)", base * extra, Kind.FORCE, clause)
        else:
            clause = f"{SPEC} §J10.6, Eq. J10-12"
            rn = c.step("R_n", r"0.60 F_y d_c t_w \left(1 + \frac{3 b_{cf} t_{cf}^2}"
                        r"{d_b d_c t_w}\right)(1.9 - 1.2\alpha P_r/P_y)",
                        base * extra * (1.9 - 1.2 * load), Kind.FORCE, clause)
    return c.result("local.panel_zone", clause, demand,
                    c.available(rn, J10_090, Kind.FORCE, clause), Kind.FORCE)
