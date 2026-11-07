# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Independent check of the coped-beam and extended-plate formulas.

This script does not import ``openconex``.  It recomputes:

* AISC Design Examples II.A-4, II.A-6 A/B and II.A-7 for coped beam ends
  (Manual Part 9 equations 9-9 to 9-21 and AISC 360-22 §F11);
* Design Example II.A-19A for an extended single plate (Manual Part 10
  equations 10-6/10-7 and the instantaneous-centre method of Part 7).

The ICR coefficient is solved by a grid search plus refinement, deliberately
different from the damped Newton iteration used by the program.

Run with::

    python docs/verificacion/calculos/placa_extendida_viga_destajada.py
    python docs/verificacion/calculos/placa_extendida_viga_destajada.py --check

Units are inches and kips throughout.
"""

from __future__ import annotations

import math
import sys

E = 29_000.0
PHI_FLEXURE = 0.90
OMEGA_FLEXURE = 1.67
PHI_SHEAR_YIELD = 1.00
OMEGA_SHEAR_YIELD = 1.50
PHI_SHEAR_RUPTURE = 0.75
OMEGA_SHEAR_RUPTURE = 2.00
PHI_BLOCK = 0.75
OMEGA_BLOCK = 2.00
PHI_BOLT = 0.75
OMEGA_BOLT = 2.00
DELTA_MAX = 0.34
HOLE = 0.8125
NET_HOLE = HOLE + 1.0 / 16.0


def available(nominal: float, phi: float, omega: float, lrfd: bool) -> float:
    return phi * nominal if lrfd else nominal / omega


def tee_properties(d: float, tw: float, bf: float, tf: float,
                   dc: float) -> tuple[float, float]:
    """S_c and Z_c of the tee left by a top cope (no fillets)."""
    h = d - dc
    web = (h - tf) * tw
    flange = bf * tf
    area = web + flange
    y = (flange * tf / 2.0 + web * (tf + (h - tf) / 2.0)) / area
    inertia = (bf * tf**3 / 12.0 + flange * (y - tf / 2.0) ** 2
               + tw * (h - tf) ** 3 / 12.0
               + web * (tf + (h - tf) / 2.0 - y) ** 2)
    s = inertia / max(y, h - y)
    half = area / 2.0
    if flange >= half:
        yp = half / bf
        z = (bf * yp**2 / 2.0 + bf * (tf - yp) ** 2 / 2.0
             + web * (tf + (h - tf) / 2.0 - yp))
    else:
        yp = tf + (half - flange) / tw
        z = (flange * (yp - tf / 2.0) + tw * (yp - tf) ** 2 / 2.0
             + tw * (h - yp) ** 2 / 2.0)
    return s, z


def flexure_top(d: float, tw: float, bf: float, tf: float, c: float,
                dc: float, Fy: float) -> dict[str, float]:
    """Manual Eq. 9-9 to 9-20, top cope only."""
    hc = d - dc
    cd, ch = c / d, c / hc
    f = 2.0 * cd if cd <= 1.0 else 1.0 + cd
    k = 2.2 * (hc / c) ** 1.65 if ch <= 1.0 else 2.2 * hc / c
    k1 = max(f * k, 1.61)
    s, z = tee_properties(d, tw, bf, tf, dc)
    mp, my = Fy * z, Fy * s
    lam = hc / tw
    lp = 0.475 * math.sqrt(k1 * E / Fy)
    if lam <= lp:
        mn = mp
    elif lam <= 2.0 * lp:
        mn = mp - (mp - my) * (lam / lp - 1.0)
    else:
        fcr = 0.903 * E * k1 * (tw / hc) ** 2
        mn = fcr * s
    rn = mn / (c + 0.5)
    return {"S": s, "Z": z, "lambda": lam, "lambda_p": lp, "M_n": mn,
            "R_n": rn, "phiR_n": PHI_FLEXURE * rn, "R_n/Omega": rn / OMEGA_FLEXURE}


def flexure_double(d: float, tw: float, bf: float, tf: float, c: float,
                   dc: float, dc_bottom: float, Fy: float) -> dict[str, float]:
    """Manual Eq. 9-21 and AISC 360-22 §F11, both flanges coped."""
    hc = d - dc - dc_bottom
    cb = max(3.0 + math.log(c / d) * (1.0 - dc / d), 1.84)
    s, z = tw * hc**2 / 6.0, tw * hc**2 / 4.0
    my, mp = Fy * s, Fy * z
    ratio = c * hc / tw**2
    if ratio <= 0.08 * E / Fy:
        mn = mp
    elif ratio <= 1.9 * E / Fy:
        mn = min(cb * (1.52 - 0.274 * ratio * Fy / E) * my, mp)
    else:
        fcr = 1.9 * E * cb / ratio
        mn = min(fcr * s, mp)
    rn = mn / (c + 0.5)
    return {"C_b": cb, "S": s, "Z": z, "M_n": mn, "R_n": rn,
            "phiR_n": PHI_FLEXURE * rn, "R_n/Omega": rn / OMEGA_FLEXURE}


def shear_yielding(hc: float, tw: float, Fy: float, lrfd: bool) -> float:
    return available(0.60 * Fy * hc * tw, PHI_SHEAR_YIELD, OMEGA_SHEAR_YIELD, lrfd)


def shear_rupture(hc: float, tw: float, Fu: float, holes: float,
                  lrfd: bool) -> float:
    return available(0.60 * Fu * (hc - holes) * tw, PHI_SHEAR_RUPTURE,
                     OMEGA_SHEAR_RUPTURE, lrfd)


def block_shear(agv: float, anv: float, ant: float, Fy: float, Fu: float,
                lrfd: bool, ubs: float = 1.0) -> float:
    rupture = 0.60 * Fu * anv + ubs * Fu * ant
    yielding = 0.60 * Fy * agv + ubs * Fu * ant
    return available(min(rupture, yielding), PHI_BLOCK, OMEGA_BLOCK, lrfd)


def coped_beam_cases() -> dict[str, dict[str, float]]:
    """II.A-4, II.A-6 A/B and II.A-7."""
    w21x62 = (21.0, 0.400, 8.24, 0.615, 9.0, 8.0, 0.0, 0, 0.0, 0.0, 0.0, 0.0)
    w21x73 = (21.2, 0.455, 8.30, 0.740, 9.0, 8.0, 0.0, 0, 0.0, 0.0, 0.0, 0.0)
    w18x50 = (18.0, 0.355, 7.50, 0.570, 4.0, 2.0, 0.0, 3, 3.0, 1.25, 1.625, 0.875)
    w16x40 = (16.0, 0.305, 7.00, 0.505, 9.5, 3.5, 2.0, 0, 0.0, 0.0, 0.0, 0.0)
    out = {}
    for name, values in (("W21X62", w21x62), ("W21X73", w21x73),
                         ("W18X50", w18x50), ("W16X40", w16x40)):
        d, tw, bf, tf, c, dc, dcb, rows, spacing, lev, leh, hole = values
        if dcb:
            flex = flexure_double(d, tw, bf, tf, c, dc, dcb, 50.0)
        else:
            flex = flexure_top(d, tw, bf, tf, c, dc, 50.0)
        hc = d - dc - dcb
        out[name] = {f"flexure_{k}": v for k, v in flex.items()}
        out[name].update({
            "shear_yielding_LRFD": shear_yielding(hc, tw, 50.0, True),
            "shear_yielding_ASD": shear_yielding(hc, tw, 50.0, False),
            "shear_rupture_LRFD": shear_rupture(hc, tw, 65.0, rows * hole, True),
            "shear_rupture_ASD": shear_rupture(hc, tw, 65.0, rows * hole, False),
        })
        if rows and leh:
            length = lev + (rows - 1) * spacing
            agv = length * tw
            anv = agv - (rows - 0.5) * hole * tw
            tension = leh - 0.25
            ant = (tension - 0.5 * hole) * tw
            out[name]["block_LRFD"] = block_shear(agv, anv, ant, 50.0, 65.0, True)
            out[name]["block_ASD"] = block_shear(agv, anv, ant, 50.0, 65.0, False)
    return out


# ----------------------------------------------------------------- extended plate


def _response(distance: float, dmax: float) -> float:
    return (1.0 - math.exp(-10.0 * DELTA_MAX * distance / dmax)) ** 0.55


def _residual(icr: tuple[float, float], bolts: list[tuple[float, float]],
              load: tuple[float, float]) -> tuple[float, float, float]:
    x0, y0 = icr
    u = (0.0, -1.0)
    radii = [(x - x0, y - y0) for x, y in bolts]
    distances = [math.hypot(rx, ry) for rx, ry in radii]
    dmax = max(distances)
    lever = (load[0] - x0) * u[1] - (load[1] - y0) * u[0]
    if abs(lever) < 1e-9:
        return 1e9, 1e9, 1e9
    sense = -1.0 if lever > 0 else 1.0
    fx = fy = moment = 0.0
    for (rx, ry), distance in zip(radii, distances, strict=True):
        if distance == 0:
            continue
        force = _response(distance, dmax)
        fx += sense * force * (-ry / distance)
        fy += sense * force * (rx / distance)
        moment += force * distance
    load_value = moment / abs(lever)
    return fx + load_value * u[0], fy + load_value * u[1], load_value


def icr_coefficient(bolts: list[tuple[float, float]],
                    load: tuple[float, float]) -> float:
    """C by coarse grid search plus successive refinement."""
    best: tuple[float, float, float, float] | None = None
    for step, half in ((1.0, 30), (0.1, 20), (0.01, 20), (0.001, 20), (0.0001, 20)):
        if best is None:
            xs = [i * step for i in range(-half, half + 1)]
            ys = xs
        else:
            xs = [best[1] + i * step for i in range(-half, half + 1)]
            ys = [best[2] + i * step for i in range(-half, half + 1)]
        for x in xs:
            for y in ys:
                fx, fy, p = _residual((x, y), bolts, load)
                error = math.hypot(fx, fy)
                if best is None or error < best[0]:
                    best = (error, x, y, p)
    assert best is not None
    return best[3]


def extended_plate_ii_a_19a() -> dict[str, float]:
    """II.A-19A: PL 1/2 x 12, two lines of four 3/4 in. A325-N bolts."""
    d, rows, spacing, length = 0.75, 4, 3.0, 12.0
    thickness, lev, leh, a = 0.5, 1.5, 1.25, 9.0
    Fy, Fu, beam_tw, beam_Fu = 50.0, 65.0, 0.295, 65.0
    lines, gage = 2, 3.0
    area = math.pi * d**2 / 4.0
    hole = NET_HOLE
    shear = available(54.0 * area, PHI_BOLT, OMEGA_BOLT, True)
    web = available(2.4 * d * beam_tw * beam_Fu, PHI_BOLT, OMEGA_BOLT, True)
    plate = available(2.4 * d * thickness * Fu, PHI_BOLT, OMEGA_BOLT, True)
    tearout = available(1.2 * (lev - HOLE / 2.0) * thickness * Fu,
                        PHI_BOLT, OMEGA_BOLT, True)
    rn = min(shear, web, plate, tearout)
    group = [(j * gage, i * spacing) for j in range(lines) for i in range(rows)]
    e = a + (lines - 1) * gage / 2.0
    load = ((lines - 1) * gage / 2.0 + e, (rows - 1) * spacing / 2.0)
    coefficient = icr_coefficient(group, load)
    bolts = coefficient * rn
    cx = sum(x for x, _ in group) / len(group)
    cy = sum(y for _, y in group) / len(group)
    distances = [math.hypot(x - cx, y - cy) for x, y in group]
    c_prime = sum(_response(dist, max(distances)) * dist for dist in distances)
    m_max = 54.0 / 0.90 * area * c_prime
    t_max = 6.0 * m_max / (Fy * length**2)
    z, s = thickness * length**2 / 4.0, thickness * length**2 / 6.0
    flexure_yield = available(min(Fy * z, 1.5 * Fy * s),
                              PHI_FLEXURE, OMEGA_FLEXURE, True)
    ratio = a * length / thickness**2
    mp = min(Fy * z, 1.5 * Fy * s)
    cb = 1.84
    if ratio <= 0.08 * E / Fy:
        mn_ltb = mp
    elif ratio <= 1.9 * E / Fy:
        mn_ltb = min(cb * (1.52 - 0.274 * ratio * Fy / E) * Fy * s, mp)
    else:
        mn_ltb = min(1.9 * E * cb / ratio * s, mp)
    ltb = available(mn_ltb, PHI_FLEXURE, OMEGA_FLEXURE, True)
    center = (rows - 1) * spacing / 2.0
    ys = [abs(i * spacing - center) for i in range(rows)]
    z_net = z - sum(thickness * hole * y if y >= hole / 2.0
                    else thickness * hole**2 / 4.0 for y in ys)
    flexure_rupture = available(Fu * z_net, PHI_SHEAR_RUPTURE,
                                OMEGA_SHEAR_RUPTURE, True)
    agv = (length - lev) * thickness
    anv = agv - (rows - 0.5) * hole * thickness
    ant = (leh + (lines - 1) * gage - (lines - 0.5) * hole) * thickness
    block = block_shear(agv, anv, ant, Fy, Fu, True, ubs=0.5)
    shear_yield = available(0.60 * Fy * length * thickness,
                            PHI_SHEAR_YIELD, OMEGA_SHEAR_YIELD, True)
    shear_rupture = available(0.60 * Fu * (length - rows * hole) * thickness,
                              PHI_SHEAR_RUPTURE, OMEGA_SHEAR_RUPTURE, True)
    interaction = (36.0 / shear_yield) ** 2 + (36.0 * a / min(flexure_yield, ltb)) ** 2
    return {"bolts": bolts, "C": coefficient, "t_max": t_max,
            "shear_yielding": shear_yield, "shear_rupture": shear_rupture,
            "block_shear": block, "flexural_yielding": flexure_yield,
            "flexural_ltb": ltb, "flexural_rupture": flexure_rupture,
            "Z_net": z_net, "interaction": interaction}


PUBLISHED: dict[str, dict[str, float]] = {
    "W21X62": {"flexure_phiR_n": 116, "flexure_R_n/Omega": 77.2,
               "shear_yielding_LRFD": 156, "shear_yielding_ASD": 104,
               "shear_rupture_LRFD": 152, "shear_rupture_ASD": 102},
    "W21X73": {"flexure_phiR_n": 150, "flexure_R_n/Omega": 100,
               "shear_yielding_LRFD": 180, "shear_yielding_ASD": 120,
               "shear_rupture_LRFD": 176, "shear_rupture_ASD": 117},
    "W18X50": {"flexure_phiR_n": 374, "flexure_R_n/Omega": 249,
               "shear_yielding_LRFD": 170, "shear_yielding_ASD": 113,
               "block_LRFD": 68.6, "block_ASD": 45.8},
    "W16X40": {"flexure_phiR_n": 37.9, "flexure_R_n/Omega": 25.2},
    "II.A-19A": {"bolts": 41.7, "t_max": 0.575, "shear_yielding": 180,
                 "shear_rupture": 125, "block_shear": 145,
                 "flexural_yielding": 810, "flexural_ltb": 810,
                 "flexural_rupture": 624, "interaction": 0.200},
}


def main() -> int:
    print("Coped beams")
    for name, values in coped_beam_cases().items():
        print(f"  {name}: " + ", ".join(f"{k} = {v:.3f}"
                                         for k, v in values.items()))
    print("\nII.A-19A extended plate")
    for key, value in extended_plate_ii_a_19a().items():
        print(f"  {key} = {value:.3f}")
    return 0


def check() -> int:
    failures = []
    cases = coped_beam_cases()
    for name, published in PUBLISHED.items():
        computed = cases.get(name) or extended_plate_ii_a_19a()
        for key, target in published.items():
            value = computed[key]
            if abs(value - target) / abs(target) > 0.01:
                failures.append(f"{name} {key}: {value:.4f} vs {target:.4f}")
    if failures:
        print("FAIL")
        for failure in failures:
            print(f"  {failure}")
        return 1
    print("OK: 29 independent values within 1 % of the published examples.")
    return 0


if __name__ == "__main__":
    raise SystemExit(check() if "--check" in sys.argv else main())
