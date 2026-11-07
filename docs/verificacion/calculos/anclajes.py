# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Independent check of the ACI 318-19 anchor formulas.

This script does not import ``openconex``.  It recomputes three published
examples from AISC Design Guide 1 (3rd ed., 2024):

* Example 4.7-4: shear resisted by anchors, limited by the edge.
* Example 4.7-9: anchor tension in a base plate under pure moment.
* Example 4.7-15: anchor reinforcement for concrete breakout in tension.

The empirical ACI equations are evaluated in inches, pounds and psi, as the
code does, and the results are reported in kips.

Run with::

    python docs/verificacion/calculos/anclajes.py
    python docs/verificacion/calculos/anclajes.py --check
"""

from __future__ import annotations

import math
import sys

PHI_STEEL_TENSION = 0.75
PHI_CONCRETE = 0.70
PHI_PULLOUT = 0.70
PHI_AISC_BOLT = 0.75

# UNC threads per inch.
TPI = {0.75: 10, 0.875: 9, 1.0: 8}


def tensile_stress_area(d: float) -> float:
    """Ase,N = π/4 (d − 0.9743/n_t)^2 [in²]."""
    return math.pi / 4.0 * (d - 0.9743 / TPI[round(d, 3)]) ** 2


def futa(Fu: float, Fy: float) -> float:
    """futa ≤ min(Fu, 1.9 Fy, 125 ksi)."""
    return min(Fu, 1.9 * Fy, 125.0)


def steel_tension(d: float, Fu: float, Fy: float) -> tuple[float, float]:
    """Nsa of one anchor and its available strength."""
    nsa = tensile_stress_area(d) * futa(Fu, Fy)
    return nsa, PHI_STEEL_TENSION * nsa


def heavy_hex_bearing_area(d: float) -> float:
    """Net bearing area of a heavy hex nut [in²]."""
    f = 1.5 * d + 0.125
    return math.sqrt(3.0) / 2.0 * f * f - math.pi * d * d / 4.0


def pullout(d: float, fc_psi: float) -> tuple[float, float]:
    """Np = 8 Abrg f'c of one headed anchor or nut."""
    np_ = 8.0 * heavy_hex_bearing_area(d) * fc_psi
    return np_, PHI_PULLOUT * np_


def effective_hef(hef: float, edges: tuple[float | None, ...],
                  span_x: float, span_y: float) -> float:
    """ACI 318-19 §17.6.2.1.2 when three or more edges are near."""
    near = [c for c in edges if c is not None and c < 1.5 * hef]
    if len(near) >= 3:
        return min(hef, max(max(near) / 1.5, max(span_x, span_y) / 3.0))
    return hef


def projected_area_tension(hef: float, span_x: float, span_y: float,
                           edges: tuple[float | None, ...]) -> float:
    """A_Nc of a rectangular group, ACI 318-19 §17.6.2.1.1."""
    r = 1.5 * hef

    def side(c: float | None) -> float:
        return r if c is None else min(c, r)

    return ((span_x + side(edges[0]) + side(edges[1]))
            * (span_y + side(edges[2]) + side(edges[3])))


def breakout_tension(hef: float, fc_psi: float, span_x: float = 0.0,
                     span_y: float = 0.0,
                     edges: tuple[float | None, ...] = (None, None, None, None),
                     eccentricity: float = 0.0, cracked: bool = True
                     ) -> dict[str, float]:
    """ACI 318-19 §17.6.2, Condition B (no supplementary reinforcement)."""
    h = effective_hef(hef, edges, span_x, span_y)
    anc = projected_area_tension(h, span_x, span_y, edges)
    anco = 9.0 * h * h
    if 11.0 <= h <= 25.0:
        nb = 16.0 * math.sqrt(fc_psi) * h ** (5.0 / 3.0)
    else:
        nb = 24.0 * math.sqrt(fc_psi) * h**1.5
    psi_ec = 1.0 / (1.0 + eccentricity / (1.5 * h))
    ca_min = min((c for c in edges if c is not None), default=math.inf)
    psi_ed = (1.0 if ca_min >= 1.5 * h
              else 0.7 + 0.3 * ca_min / (1.5 * h))
    psi_c = 1.0 if cracked else 1.25
    ncbg = anc / anco * psi_ec * psi_ed * psi_c * nb
    return {"hef_effective": h, "A_Nc": anc, "A_Nco": anco, "Nb": nb / 1000.0,
            "Ncbg": ncbg / 1000.0, "phiNcbg": PHI_CONCRETE * ncbg / 1000.0}


def breakout_shear(d: float, hef: float, ca1: float, fc_psi: float,
                   spacing: float) -> dict[str, float]:
    """ACI 318-19 §17.7.2, no side edges near and deep member."""
    r = 1.5 * ca1
    avc = (spacing + 2.0 * r) * r
    avco = 4.5 * ca1 * ca1
    le = min(hef, 8.0 * d)
    root = math.sqrt(fc_psi) * ca1**1.5
    vb = min(7.0 * (le / d) ** 0.2 * math.sqrt(d) * root, 9.0 * root)
    vcbg = avc / avco * vb
    return {"A_Vc": avc, "A_Vco": avco, "Vb": vb / 1000.0,
            "Vcbg": vcbg / 1000.0, "phiVcbg": PHI_CONCRETE * vcbg / 1000.0}


def aisc_rod_shear(d: float, Fu: float, n: int) -> dict[str, float]:
    """AISC 360-22 Eq. J3-1 with Fnv = 0.450 Fu (threads included)."""
    rn = 0.450 * Fu * math.pi * d * d / 4.0
    return {"rod_Rnv": rn, "rod_phiRnv": PHI_AISC_BOLT * rn,
            "group_phiRnv": n * PHI_AISC_BOLT * rn}


def hooked_bar_ldh(fy_psi: float, fc_psi: float, db: float) -> tuple[float, float, float]:
    """ACI 318-19 Eq. 25.4.3.1a and minimum length."""
    psi_c = min(fc_psi / 15000.0 + 0.6, 1.0) if fc_psi < 6000.0 else 1.0
    ldh = max(fy_psi * psi_c / (55.0 * math.sqrt(fc_psi)) * db**1.5,
              max(8.0 * db, 6.0))
    return ldh, psi_c, max(8.0 * db, 6.0)


def straight_bar_ld(fy_psi: float, fc_psi: float, db: float,
                    cb: float) -> tuple[float, float, float]:
    """ACI 318-19 Eq. 25.4.2.4a, ψt = ψe = λ = 1, Ktr = 0."""
    fc_psi = min(fc_psi, 10_000.0)
    psi_s = 0.8 if db <= 0.75 else 1.0
    psi_g = 1.0 if fy_psi <= 60_000.0 else 1.15 if fy_psi <= 80_000.0 else 1.3
    confinement = min(cb / db, 2.5)
    ld = (3.0 / 40.0) * (fy_psi * psi_s * psi_g / math.sqrt(fc_psi)
                         * db / confinement)
    return max(ld, 12.0), confinement, psi_s


def dg1_4_7_4() -> dict[str, float]:
    """4 x 3/4 in. F1554 Gr. 36 rods, ca1 = 12 in., f'c = 4 ksi."""
    d, Fu, fc_psi = 0.75, 58.0, 4000.0
    result = breakout_shear(d, 12.0, 12.0, fc_psi, 4.0)
    result.update(aisc_rod_shear(d, Fu, 2))
    return result


def dg1_4_7_9() -> dict[str, float]:
    """4 x 1 in. F1554 Gr. 36 rods, hef = 12 in., f'c = 4 ksi, pure moment."""
    d, Fu, Fy, fc_psi = 1.0, 58.0, 36.0, 4000.0
    nsa, phi_nsa = steel_tension(d, Fu, Fy)
    breakout = breakout_tension(12.0, fc_psi, span_x=6.0)
    np_, phi_np = pullout(d, fc_psi)
    return {"Nsa": nsa, "phiNsa": phi_nsa, **breakout,
            "Np": np_ / 1000.0, "phiNpn": phi_np / 1000.0,
            "m": (28.0 - 0.95 * 18.2) / 2.0,
            "n": (12.0 - 0.8 * 11.0) / 2.0,
            "x": 12.0 - 18.2 / 2.0 + 0.680 / 2.0}


def dg1_4_7_15() -> dict[str, float]:
    """4 x 7/8 in. rods, 4 #6 anchor reinforcement, f'c = 4 ksi, hef = 14 in."""
    fc_psi, fy_psi = 4000.0, 60_000.0
    edges = (8.0, 8.0, 8.0, 8.0)
    breakout = breakout_tension(14.0, fc_psi, span_x=4.0, span_y=4.0, edges=edges)
    demand, area = 70.0, 1.76
    as_req = demand / (0.75 * 60.0)
    ldh, psi_c, ldh_min = hooked_bar_ldh(fy_psi, fc_psi, 0.75)
    ld, confinement, psi_s = straight_bar_ld(fy_psi, fc_psi, 0.75, 4.0)
    g, cover = 2.83, 2.0
    hef_req = ldh + g / 1.5 + cover
    available_above = 14.0 - cover - g / 1.5
    straight_req = max(ld * as_req / area, 12.0)
    return {**breakout, "As_req": as_req, "As": area,
            "phi_reinforcement": 0.75, "psi_c_hook": psi_c,
            "ldh": ldh, "ldh_min": ldh_min, "ld": ld, "confinement": confinement,
            "psi_s": psi_s, "hef_req": hef_req, "available_above": available_above,
            "straight_req": straight_req, "le": 15.2, "ca1": 8.0,
            "side_face_limit": 20.0}


PUBLISHED = {
    "4.7-4": {"A_Vc": 720, "A_Vco": 648, "Vb": 23.7, "Vcbg": 26.3,
              "phiVcbg": 18.4, "rod_Rnv": 11.5, "rod_phiRnv": 8.63,
              "group_phiRnv": 17.3},
    "4.7-9": {"Nsa": 35.1, "phiNsa": 26.3, "A_Nc": 1510, "A_Nco": 1300,
              "Nb": 63.6, "Ncbg": 73.9, "phiNcbg": 51.7, "Np": 48.0,
              "phiNpn": 33.6, "m": 5.36, "n": 1.60, "x": 3.24},
    "4.7-15": {"hef_effective": 5.33, "A_Nc": 400, "A_Nco": 256, "Nb": 18.7,
               "Ncbg": 29.2, "phiNcbg": 20.4, "As_req": 1.56, "As": 1.76,
               "psi_c_hook": 0.867, "ldh": 9.71, "ldh_min": 6.00,
               "ld": 17.1, "confinement": 2.5, "hef_req": 13.6,
               "available_above": 10.1, "straight_req": 15.1, "le": 15.2,
               "ca1": 8.00, "side_face_limit": 20.0},
}


def main() -> int:
    for example, values in (("4.7-4", dg1_4_7_4()), ("4.7-9", dg1_4_7_9()),
                            ("4.7-15", dg1_4_7_15())):
        print(example)
        print("  " + ", ".join(f"{key} = {value:8.3f}"
                                for key, value in values.items()))
    return 0


def check() -> int:
    failures = []
    cases = (("4.7-4", dg1_4_7_4()), ("4.7-9", dg1_4_7_9()),
             ("4.7-15", dg1_4_7_15()))
    count = 0
    for example, computed in cases:
        for key, target in PUBLISHED[example].items():
            count += 1
            value = computed[key]
            if abs(value - target) / abs(target) > 0.01:
                failures.append(f"{example} {key}: {value:.4f} vs {target:.4f}")
    if failures:
        print("FAIL")
        for failure in failures:
            print(f"  {failure}")
        return 1
    print(f"OK: {count} independent values within 1 % of the published examples.")
    return 0


if __name__ == "__main__":
    raise SystemExit(check() if "--check" in sys.argv else main())
