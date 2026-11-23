# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Independent check of the bolted beam and column splice formulas (F7).

This script deliberately does not import ``openconex``. It recomputes, from the
equations of AISC 360-22 (Chapters J and F13) and the AISC Manual, the main limit
states of the two example splices (``examples/splice_beam_bolted.ocnx`` and
``examples/splice_column_fillers.ocnx``) for one LRFD load each, so the tests can
compare the program against a calculation written separately.

No published worked example of a bolted beam or column splice is available to
the project yet; when one is, add it here and to ``tests/splice``.

Run with::

    python docs/verificacion/calculos/empalmes.py

Units are inches and kips throughout. Section areas exclude the fillets
(A = 2 b_f t_f + (d - 2 t_f) t_w), as in the program.
"""

from __future__ import annotations

import math

PHI_BOLT = 0.75
PHI_TY, PHI_TR = 0.90, 0.75
PHI_VY, PHI_VR = 1.00, 0.75
PHI_BS = 0.75
PHI_C = 0.90
PHI_B = 0.90
PHI_BEARING = 0.75
E = 29_000.0

BOLT_D = 0.875
AB = math.pi * BOLT_D**2 / 4
FNV = 54.0  # A325-N
HOLE = 15 / 16
HOLE_NET = HOLE + 1 / 16

W21X62 = {"d": 21.0, "bf": 8.24, "tf": 0.615, "tw": 0.400, "kdes": 1.12, "Sx": 127.0,
          "Fy": 50.0, "Fu": 65.0}
W14X90 = {"d": 14.0, "bf": 14.5, "tf": 0.710, "tw": 0.440, "Fy": 50.0, "Fu": 65.0}
W14X132 = {"d": 14.7, "bf": 14.7, "tf": 1.03, "tw": 0.645, "Fy": 50.0, "Fu": 65.0}


def area(s: dict) -> float:
    return 2 * s["bf"] * s["tf"] + (s["d"] - 2 * s["tf"]) * s["tw"]


def bear(t: float, Fu: float, lc: float | None) -> float:
    """phi min(2.4 d t Fu, 1.2 lc t Fu) (§J3.11)."""
    rn = 2.4 * BOLT_D * t * Fu
    if lc is not None:
        rn = min(rn, 1.2 * lc * t * Fu)
    return PHI_BOLT * rn


def block(agv: float, anv: float, ant: float, Fy: float, Fu: float, ubs: float = 1.0) -> float:
    return PHI_BS * min(0.6 * Fu * anv + ubs * Fu * ant, 0.6 * Fy * agv + ubs * Fu * ant)


def beam_splice() -> dict[str, float]:
    """W21X62, PL 5/8 x 8 outer + 2 PL 5/8 x 3 inner, 4 rows x 2 lines of 7/8 in. A325-N
    at 3 in., g = 5 1/2 in., l_e = 1 1/2 in.; LRFD: V = 60 kips, M = 300 kip-ft,
    P = -20 kips (tension)."""
    b = W21X62
    V, M, P = 60.0, 300.0 * 12, -20.0
    Fy, Fu = 50.0, 65.0  # A572 Gr. 50 plates
    t, w, ti, wi, g, s, le, n, gap = 0.625, 8.0, 0.625, 3.0, 5.5, 3.0, 1.5, 4, 0.5
    A, Af = area(b), b["bf"] * b["tf"]
    T = M / b["d"] - P * Af / A
    C = M / b["d"] + P * Af / A
    out = {"T": T, "C": C}
    # flange bolts, tension: double shear; member bears to its end, plates to theirs
    rv = PHI_BOLT * FNV * AB * 2
    inner = s - HOLE
    edge = le - HOLE / 2
    per = []
    for i in range(n):
        m = bear(b["tf"], b["Fu"], edge if i == 0 else inner)
        p = bear(t + ti, Fu, edge if i == n - 1 else inner)
        per.append(min(rv, m, p))
    out["flange_bolts"] = 2 * sum(per)
    Ag = w * t + 2 * wi * ti
    An = (w - 2 * HOLE_NET) * t + 2 * (wi - HOLE_NET) * ti
    out["flange_plate_tension_yielding"] = PHI_TY * Fy * Ag
    out["flange_plate_tension_rupture"] = PHI_TR * Fu * min(An, 0.85 * Ag)
    # compression: K = 0.65 over the gap and both end distances, r of the thinner plate
    kl_r = 0.65 * (gap + 2 * le) / (min(t, ti) / math.sqrt(12))
    out["flange_plate_compression"] = PHI_C * Fy * Ag if kl_r <= 25 else float("nan")
    # beam flange block shear: two blocks to the flange tips or the block between lines
    L = (n - 1) * s + le
    agv = 2 * L * b["tf"]
    anv = agv - 2 * (n - 0.5) * HOLE_NET * b["tf"]
    out["beam_flange_block_shear"] = min(
        block(agv, anv, 2 * ((b["bf"] - g) / 2 - HOLE_NET / 2) * b["tf"], b["Fy"], b["Fu"]),
        block(agv, anv, (g - HOLE_NET) * b["tf"], b["Fy"], b["Fu"]))
    # §F13.1: holes in the tension flange
    afg = b["bf"] * b["tf"]
    afn = afg - 2 * HOLE_NET * b["tf"]
    out["beam_flexural_rupture"] = PHI_B * b["Fu"] * afn / afg * b["Sx"] / 12  # kip-ft
    out["beam_flexural_rupture_applies"] = float(b["Fu"] * afn < b["Fy"] * afg)
    # web plates: 2 PL 3/8 x 15, 5 bolts at 3 in., one line, l_e = 1 1/2 in.
    tp, h, rows = 0.375, 15.0, 5
    out["web_plate_shear_yielding"] = PHI_VY * 0.6 * Fy * 2 * h * tp
    out["web_plate_shear_rupture"] = PHI_VR * 0.6 * Fu * 2 * (h - rows * HOLE_NET) * tp
    lev = (h - (rows - 1) * 3.0) / 2
    agv = 2 * (h - lev) * tp
    anv = agv - 2 * (rows - 0.5) * HOLE_NET * tp
    ant = 2 * (1.5 - 0.5 * HOLE_NET) * tp
    out["web_plate_block_shear"] = block(agv, anv, ant, Fy, Fu)
    e = gap / 2 + 1.5
    out["web_plate_moment"] = V * e
    Z = 2 * tp * h**2 / 4
    out["web_plate_flexural_yielding"] = PHI_B * Fy * Z
    ys = [abs(-6.0 + 3.0 * i) for i in range(rows)]
    out["web_plate_flexural_rupture"] = 0.75 * Fu * (Z - 2 * tp * HOLE_NET * sum(ys))
    Aw = A - 2 * Af
    out["web_axial"] = P * Aw / A
    return out


def column_splice() -> dict[str, float]:
    """W14X90 on W14X132, PL 1/2 x 14 (A36), 3 rows x 2 lines of 7/8 in. A325-N at 3 in.
    on each side, g = 5 1/2 in., l_e = 1 1/2 in., finished ends; LRFD: P = 200 kips,
    M = 150 kip-ft, V_weak = 20 kips."""
    up, lo = W14X90, W14X132
    P, M, Vw = 200.0, 150.0 * 12, 20.0
    Fy, Fu = 36.0, 58.0
    t, w, s, le, n = 0.5, 14.0, 3.0, 1.5, 3  # gage 5 1/2 in. does not enter here
    filler = (lo["d"] - up["d"]) / 2
    factor = max(0.85, 1 - 0.4 * (filler - 0.25)) if filler > 0.25 else 1.0
    A, Af = area(up), up["bf"] * up["tf"]
    T = M / up["d"] - P * Af / A
    C = M / up["d"] + P * Af / A
    out = {"T": T, "C": C, "filler": filler, "filler_factor": factor}
    rv = PHI_BOLT * FNV * AB
    inner, edge = s - HOLE, le - HOLE / 2
    for key, col, f in (("upper", up, factor), ("lower", lo, 1.0)):
        per = []
        for i in range(n):
            m = bear(col["tf"], col["Fu"], edge if i == 0 else inner)
            p = bear(t, Fu, edge if i == n - 1 else inner)
            per.append(min(rv * f, m, p))
        out[f"{key}_flange_bolts"] = 2 * sum(per)
        out[f"{key}_flange_bolts_demand"] = math.hypot(T, Vw / 2)
    Ag = w * t
    out["flange_plate_tension_yielding"] = PHI_TY * Fy * Ag
    out["flange_plate_tension_rupture"] = PHI_TR * Fu * min((w - 2 * HOLE_NET) * t,
                                                             0.85 * Ag)
    # bearing of the upper flange on the lower flange (§J7(a))
    overlap = min(up["d"], lo["d"]) / 2 - max(up["d"] / 2 - up["tf"], lo["d"] / 2 - lo["tf"])
    Apb = min(up["bf"], lo["bf"]) * max(overlap, 0.0)
    out["column_flange_bearing"] = PHI_BEARING * 1.8 * min(up["Fy"], lo["Fy"]) * Apb
    hc = min(up["d"] - 2 * up["tf"], lo["d"] - 2 * lo["tf"])
    out["column_web_bearing"] = PHI_BEARING * 1.8 * 50.0 * hc * min(up["tw"], lo["tw"])
    return out


def main() -> int:
    for name, values in (("Beam splice", beam_splice()), ("Column splice", column_splice())):
        print(name)
        for key, value in values.items():
            print(f"  {key:34} {value:10.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
