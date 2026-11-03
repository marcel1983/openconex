# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""All-bolted double angle under shear and axial tension (Design Example II.A-1B).

Extends :func:`~openconex.connections.shear.double_angle.check_double_angle`
for the beam shear V with an axial tension N:

* bolts through the beam web: the bearing and tearout clear distances follow
  the line of action of the bolt force. For the bottom (edge) bolt of the
  angles l_e = l_ev / cos θ with θ = atan(N/V); for the other bolts and for the
  beam web l_e = l_eh / cos β with β = atan(V/N), the web edge distance less
  the length underrun (AISC 360-22 §J3.11);
* bolts in the outstanding legs: tension with shear (§J3.8) reduced by prying
  action of the angles (Manual Part 9, p = l / n);
* shear yielding and rupture, tensile yielding and rupture (U = 1) of the
  angles; block shear of the angles on the beam side for shear (L), for axial
  load (least of L and U) and their interaction (as Manual Eq. 12-1); block
  shear of the outstanding legs for shear;
* when the beam section is given: shear yielding of the beam web, tensile
  yielding and rupture of the beam (U = web area / gross area, §D3) and block
  shear of the beam web for the axial load (U-shape).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from openconex.core.checks import CheckResult
from openconex.core.loads import Method
from openconex.kernel import bolts, elements
from openconex.kernel.bolts import bolt_tension_shear
from openconex.kernel.design import Calc
from openconex.kernel.prying import prying_tension
from openconex.units import Kind, to_internal

from .double_angle import MANUAL, SPEC, DoubleAngle, _block_shear, _hole_net, _transfer

__all__ = ["AxialBeam", "check_double_angle_axial"]


@dataclass(frozen=True)
class AxialBeam:
    """Beam section data for the beam limit states under axial load."""

    d: float
    tf: float
    Ag: float
    Fy: float


def _rename(key: str, check: CheckResult) -> CheckResult:
    return check.model_copy(update={"id": f"double_angle.{key}",
                                    "text_id": f"check.double_angle.{key}"})


def _beam_bolts(da: DoubleAngle, V: float, N: float, method: Method, combo: str,
                beam_leh: float) -> CheckResult:
    c = Calc(method, combo)
    clause = f"{SPEC} §J3.7, §J3.11"
    b, dh = da.bolt, da.bolt.hole_dimensions[0]
    kw = {"deformation_considered": da.deformation_considered}
    theta = c.step(r"\theta", r"\tan^{-1}(N/V)", math.degrees(math.atan2(N, V)), clause=clause)
    cos_t, cos_b = math.cos(math.radians(theta)), math.sin(math.radians(theta))

    def bearing_tearout(t, Fu, le, name):
        lc = le - dh / 2
        bear = bolts.bolt_bearing(b, t, Fu, 0.0, method, **kw).capacity
        tear = bolts.bolt_tearout(b, t, Fu, lc, 0.0, method, **kw).capacity
        return c.step(rf"r_{{n,{name}}}", r"\min(2.4dtF_u, 1.2l_ctF_u)", min(bear, tear),
                      Kind.FORCE, clause, l_c=(lc, Kind.LENGTH))

    shear = c.step(r"2 r_{n,bolt}", "", 2 * bolts.bolt_shear(b, 0.0, method).capacity,
                   Kind.FORCE, f"{SPEC} §J3.7")
    edge = 2 * bearing_tearout(da.thickness, da.angle_Fu, da.lev / cos_t, "angle,edge")
    other = 2 * bearing_tearout(da.thickness, da.angle_Fu, da.leh_beam / cos_b, "angle")
    web = bearing_tearout(da.beam_tw, da.beam_Fu, beam_leh / cos_b, "web")
    rows = [min(shear, edge if i == da.rows - 1 else other, web) for i in range(da.rows)]
    rn = c.step(r"\sum r_{n,i}", "", sum(rows), Kind.FORCE, clause)
    return c.result("double_angle.bolts_beam", clause, math.hypot(V, N), rn, Kind.FORCE)


def _support_tension(da: DoubleAngle, V: float, N: float, method: Method, combo: str,
                     gage: float, leg: float) -> CheckResult:
    n = 2 * da.rows
    b = da.bolt
    tc = bolt_tension_shear(b, N / n, V, method, planes=n, combo=combo)
    c = Calc(method, combo)
    clause = f"{SPEC} §J3.8; {MANUAL[:-8]}Part 9"
    bb = c.step("b", r"\frac{g - t_w - t}{2}", (gage - da.beam_tw - da.thickness) / 2,
                Kind.LENGTH, clause)
    a = c.step("a", r"\frac{2\,\mathrm{leg} + t_w - g}{2}", (2 * leg + da.beam_tw - gage) / 2,
               Kind.LENGTH, clause)
    p = c.step("p", "l/n", da.length / da.rows, Kind.LENGTH, clause)
    pry = prying_tension(tc.capacity, da.thickness, bb, a, p, b.diameter, b.hole_dimensions[0],
                         da.angle_Fu, N / n, method, combo)
    out = c.step("n T_{avail}", "n B Q", n * pry.capacity, Kind.FORCE, clause,
                 n=(n, Kind.DIMENSIONLESS))
    result = c.result("double_angle.bolts_tension", clause, N, out, Kind.FORCE)
    return result.model_copy(update={"steps": tc.steps + pry.steps + result.steps})


def check_double_angle_axial(da: DoubleAngle, V: float, N: float, method: Method,
                             gage: float, outstanding_leg: float, combo: str = "",
                             beam_leh: float | None = None,
                             underrun: float | None = None,
                             beam: AxialBeam | None = None) -> list[CheckResult]:
    """Limit states for the beam shear ``V`` and axial tension ``N`` (both ≥ 0).

    ``gage`` is the bolt gage across the outstanding legs, ``outstanding_leg``
    their width. ``beam_leh`` is the web edge distance (default ``leh_beam``),
    reduced by ``underrun`` (default 1/4 in.).
    """
    from .double_angle import check_double_angle

    if N <= 0:
        return check_double_angle(da, V, method, combo)
    if underrun is None:
        underrun = to_internal(0.25, "in", Kind.LENGTH)
    web_leh = (beam_leh if beam_leh is not None else da.leh_beam) - underrun
    t, hole, n, L = da.thickness, _hole_net(da.bolt), da.rows, da.length
    Fy, Fu = da.angle_Fy, da.angle_Fu
    R = math.hypot(V, N)
    anv = 2 * (L - n * hole) * t

    block_v = _block_shear(da, da.leh_beam, V, method, combo, "block_shear_beam")
    block_l = elements.block_shear(2 * da.leh_beam * t, 2 * (da.leh_beam - 0.5 * hole) * t,
                                   2 * (L - da.lev - (n - 0.5) * hole) * t, Fy, Fu, N, method,
                                   combo=combo)
    block_u = elements.block_shear(4 * da.leh_beam * t, 4 * (da.leh_beam - 0.5 * hole) * t,
                                   2 * (L - 2 * da.lev - (n - 1) * hole) * t, Fy, Fu, N,
                                   method, combo=combo)
    block_n = _rename("block_shear_axial", min(block_l, block_u, key=lambda r: r.capacity))
    c = Calc(method, combo)
    clause = "AISC Manual 16th ed., Part 12 (as Eq. 12-1)"
    u = c.step("U", r"\left(\frac{V}{R_{v}}\right)^2 + \left(\frac{N}{R_{t}}\right)^2",
               (V / block_v.capacity) ** 2 + (N / block_n.capacity) ** 2, clause=clause)
    block_i = c.result("double_angle.block_shear_interaction", clause, u, 1.0,
                       Kind.DIMENSIONLESS)

    out = [
        _beam_bolts(da, V, N, method, combo, web_leh),
        _transfer(da, V, method, combo, "support"),
        _support_tension(da, V, N, method, combo, gage, outstanding_leg),
        _rename("angle_shear_yielding", elements.shear_yielding(2 * L * t, Fy, R, method,
                                                                combo)),
        _rename("angle_shear_rupture", elements.shear_rupture(anv, Fu, R, method, combo)),
        _rename("angle_tension_yielding", elements.tension_yielding(2 * L * t, Fy, N, method,
                                                                    combo)),
        _rename("angle_tension_rupture", elements.tension_rupture(anv, Fu, N, method, combo)),
        block_v, block_n, block_i,
        _block_shear(da, da.leh_support, V, method, combo, "block_shear_support"),
    ]
    if beam is not None:
        tw = da.beam_tw
        U = (beam.d - 2 * beam.tf) * tw / beam.Ag
        an = beam.Ag - n * hole * tw
        out += [
            _rename("beam_shear_yielding", elements.shear_yielding(beam.d * tw, beam.Fy, V,
                                                                   method, combo)),
            _rename("beam_tension_yielding", elements.tension_yielding(beam.Ag, beam.Fy, N,
                                                                       method, combo)),
            _rename("beam_tension_rupture", elements.tension_rupture(an * U, da.beam_Fu, N,
                                                                     method, combo)),
            _rename("beam_block_shear", elements.block_shear(
                2 * web_leh * tw, 2 * (web_leh - 0.5 * hole) * tw,
                (L - 2 * da.lev - (n - 1) * hole) * tw, beam.Fy, da.beam_Fu, N, method,
                combo=combo)),
        ]
    return out
