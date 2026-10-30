# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Acceptance tests: AISC Design Guide 1 (3rd ed.) examples, tests/reference/dg1/*.toml.

Each ``case_*`` function computes, from the case inputs, the values that the
example publishes, keyed as in the case file ("key", "lrfd.key", "asd.key").
Every computed key is compared with the published value within the case
tolerance (1 % by default, wider where the guide rounds intermediate steps).
"""

import math
import tomllib
from pathlib import Path

import pytest

from openconex.connections.base_plate import plate as bpl
from openconex.connections.base_plate import seismic, transfer
from openconex.core.loads import Method
from openconex.core.model import BoltSpec, FilletWeld
from openconex.kernel import anchors, bolts, elements, welds
from openconex.units import ureg

CASES = Path(__file__).parents[1] / "reference" / "dg1"
LRFD, ASD = Method.LRFD, Method.ASD
F36, F55 = "ASTM F1554 Gr. 36", "ASTM F1554 Gr. 55"
INTERNAL = ["mm", "mm**2", "mm**3", "N", "MPa", "N*mm", "N/mm", "N*mm/mm", "dimensionless"]


def q(text):
    """Quantity text (or number) to internal units."""
    if not isinstance(text, str):
        return float(text)
    quantity = ureg.Quantity(text)
    for unit in INTERNAL:
        if quantity.dimensionality == ureg.Unit(unit).dimensionality:
            return float(quantity.to(unit).magnitude)
    raise ValueError(text)


def load(case_id):
    with (CASES / f"ex_{case_id}.toml").open("rb") as fh:
        return tomllib.load(fh)


def g(case, key):
    return q(case["given"][key])


def by_method(fn):
    """Evaluate fn(method) for LRFD and ASD into 'lrfd.k' / 'asd.k' keys."""
    out = {}
    for prefix, method in (("lrfd", LRFD), ("asd", ASD)):
        out.update({f"{prefix}.{k}": v for k, v in fn(method).items()})
    return out


def first(result, symbol):
    return next(s.value for s in result.steps if s.symbol == symbol)


# --------------------------------------------------------------------------- cases


def case_4_7_1(c, A2=1.0):
    d, bf = g(c, "d"), g(c, "bf")
    N, B, fy, fc = g(c, "N"), g(c, "B"), q("50 ksi"), g(c, "fc")
    out = {"Delta": (0.95 * d - 0.8 * bf) / 2, "A1_req": bpl.required_area(g(c, "Pu"), fc, 1.0,
                                                                           LRFD)}

    def run(method):
        P = g(c, "Pu" if method is LRFD else "Pa")
        r = bpl.compression_design(P, d, bf, N, B, fy, fc, A2, method)
        out.update(m=r.m, n=r.n, lambda_n_prime=r.lambda_n_prime, l=r.l_crit)
        pp = "phiPp" if method is LRFD else "Pp_over_Omega"
        return {pp: r.Pp_available, "X": r.X, "lambda": r.lam, "tp_req": r.tp_req}

    out.update(by_method(run))
    return out


def case_4_7_2(c):
    a1, a2 = 20 * 18, 24 * 22  # in.², A2 geometrically similar to A1
    out = case_4_7_1(c, A2=a2 / a1)
    out["A1_req"] = bpl.required_area(g(c, "Pu"), g(c, "fc"), 4.0, LRFD)
    return out


def case_b_3_1(c):
    cc, area = bpl.effective_area(g(c, "d"), g(c, "bf"), g(c, "tf"), g(c, "tw"), g(c, "tp"),
                                  g(c, "N"), g(c, "B"))
    return {"c": cc, "A_eff": area,
            "lrfd.phiPn": bpl.bearing_stress(g(c, "fc"), 4.0, LRFD) * area}


def _rect(c, method, P_key, M_key):
    return bpl.rectangular_bending(g(c, P_key), g(c, M_key), g(c, "N"), g(c, "B"),
                                   q(c["given"].get("f", "0 in")), g(c, "fc"),
                                   c["given"].get("A2_over_A1", 1.0), method)


def case_4_7_9(c):
    d, tf, fy = g(c, "d"), g(c, "tf"), q("50 ksi")
    N, B, f = g(c, "N"), g(c, "B"), g(c, "f")
    m, n = (N - 0.95 * d) / 2, (B - 0.8 * g(c, "bf")) / 2
    x = f - d / 2 + tf / 2
    rod = q("1 in")
    out = {"m": m, "n": n, "x": x,
           "Nsa": first(anchors.steel_tension(rod, q("58 ksi"), q("36 ksi"), 0, LRFD), "N_{sa}"),
           "phiNsa": anchors.steel_tension(rod, q("58 ksi"), q("36 ksi"), 0, LRFD).capacity}
    bo = anchors.breakout_tension(g(c, "hef"), g(c, "fc"), 0, LRFD, span_x=q("6 in"))
    out.update(A_Nc=first(bo, "A_{Nc}"), A_Nco=first(bo, "A_{Nco}"), Nb=first(bo, "N_b"),
               Ncbg=first(bo, "N_{cbg}"), phiNcbg=bo.capacity)
    po = anchors.pullout(anchors.heavy_hex_bearing_area(rod), g(c, "fc"), 0, LRFD)
    out.update(Np=first(po, "N_p"), phiNpn=po.capacity)
    weld = FilletWeld(size=g(c, "flange_weld"), length=g(c, "bf"))
    out["weld_Rn"] = first(welds.fillet_weld(weld, 0, LRFD, theta=90), "R_n")

    def run(method):
        r = _rect(c, method, "Pu" if method is LRFD else "Pa", "Mu" if method is LRFD else "Ma")
        M = g(c, "Mu" if method is LRFD else "Ma")
        return {"fp_max": r.fp_max, "q_max": r.q_max, "Y": r.Y, "T": r.T, "r_rod": r.T / 2,
                "tp_req_tension": bpl.plate_thickness_tension(r.T, x, B, fy, method),
                "tp_req_compression": bpl.plate_thickness_compression(r.fp_max, r.Y, m, fy,
                                                                      method),
                "flange_force": M / d,
                "weld_strength": welds.fillet_weld(weld, 0, method, theta=90).capacity}

    out.update(by_method(run))
    return out


def case_4_7_10(c):
    d, bf, fy, N, B = g(c, "d"), g(c, "bf"), q("50 ksi"), g(c, "N"), g(c, "B")
    m, n = (N - 0.95 * d) / 2, (B - 0.8 * bf) / 2
    out = {"m": m, "n": n}

    def run(method):
        r = _rect(c, method, "Pu" if method is LRFD else "Pa", "Mu" if method is LRFD else "Ma")
        out.update(e=r.e, Y=r.Y)
        fp = r.q / B
        return {"fp_max": r.fp_max, "q_max": r.q_max, "e_crit": r.e_crit, "q": r.q, "fp": fp,
                "tp_req_m": bpl.plate_thickness_compression(fp, r.Y, m, fy, method),
                "tp_req": bpl.plate_thickness_compression(fp, r.Y, max(m, n), fy, method)}

    out.update(by_method(run))
    return out


def case_4_7_11(c):
    d, bf, tf, fy = g(c, "d"), g(c, "bf"), g(c, "tf"), q("50 ksi")
    N, B, f = g(c, "N"), g(c, "B"), g(c, "f")
    m, n = (N - 0.95 * d) / 2, (B - 0.8 * bf) / 2
    x = f - d / 2 + tf / 2
    bo = anchors.breakout_tension(g(c, "hef"), g(c, "fc"), 0, LRFD, span_x=q("12 in"))
    out = {"m": m, "n": n, "x": x, "A_Nc": first(bo, "A_{Nc}"), "A_Nco": first(bo, "A_{Nco}"),
           "Nb": first(bo, "N_b"), "Ncbg": first(bo, "N_{cbg}"), "phiNcbg": bo.capacity}

    def run(method):
        r = _rect(c, method, "Pu" if method is LRFD else "Pa", "Mu" if method is LRFD else "Ma")
        return {"e": r.e, "q_max": r.q_max, "e_crit": r.e_crit, "Y": r.Y, "T": r.T,
                "fp_max": r.fp_max,
                "tp_req_compression": bpl.plate_thickness_compression(r.fp_max, r.Y, max(m, n),
                                                                      fy, method),
                "tp_req_tension": bpl.plate_thickness_tension(r.T, x, B, fy, method)}

    out.update(by_method(run))
    return out


def case_4_7_12(c):
    def run(method):
        r = _rect(c, method, "Pu" if method is LRFD else "Pa", "Mu" if method is LRFD else "Ma")
        return {"q_max": r.q_max, "Y": r.Y, "T": r.T}

    out = by_method(run)
    out["e"] = g(c, "Mu") / -g(c, "Pu")
    return out


def case_4_7_13(c):
    f = g(c, "f")
    out = {"e": g(c, "Mu") / -g(c, "Pu"), "Ix_rods": 4 * (f / 25.4) ** 2}

    def run(method):
        P = g(c, "Pu" if method is LRFD else "Pa")
        M = g(c, "Mu" if method is LRFD else "Ma")
        rows = bpl.uplift_low_moment(P, M, [f, -f])  # per row of two rods
        return {"r_rod_max": max(rows) / 2, "r_rod_min": min(rows) / 2}

    out.update(by_method(run))
    return out


def case_4_7_14(c):
    N, B, fy = g(c, "N"), g(c, "B"), q("50 ksi")
    d, bf = g(c, "d"), g(c, "bf")
    f = N / 2 - g(c, "rod_edge_distance")
    P = g(c, "Pu")
    r = bpl.rectangular_bending(P, g(c, "Mux"), N, B, f, g(c, "fc"), 4.0, LRFD)
    m, n = (N - 0.95 * d) / 2, (B - 0.8 * bf) / 2
    x = f - d / 2 + q("0.685 in") / 2
    rod = BoltSpec(diameter=g(c, "rod_diameter"), grade=F55)
    t_cap = 2 * 0.75 * rod.material.Fu * anchors.tensile_stress_area(rod.diameter)
    y_cap, m_cap = bpl.biaxial_capacity(P, N, B, f, g(c, "fc"), 4.0, t_cap, LRFD)
    return {"lrfd.f": f, "lrfd.fp_max": r.fp_max, "lrfd.q_max": r.q_max,
            "lrfd.e_crit": r.e_crit, "lrfd.ex": g(c, "Mux") / P, "lrfd.ey": g(c, "Muy") / P,
            "lrfd.Y": r.Y, "lrfd.T": r.T, "lrfd.m": m, "lrfd.n": n,
            # The guide conservatively uses the full cantilever (Y >= n) here.
            "lrfd.tp_req_compression": bpl.plate_thickness_compression(r.fp_max, n, n, fy, LRFD),
            "lrfd.x": x, "lrfd.tp_req_tension": bpl.plate_thickness_tension(r.T, x, B, fy, LRFD),
            "lrfd.T_capacity": t_cap, "lrfd.Y_capacity": y_cap, "lrfd.Mx_capacity": m_cap,
            "lrfd.My_capacity": m_cap,
            "lrfd.interaction": (g(c, "Mux") / m_cap) ** 2 + (g(c, "Muy") / m_cap) ** 2}


def case_b_2_1(c):
    d, bf = g(c, "d"), g(c, "bf")
    N, B = g(c, "N"), g(c, "B")
    m, n = (N - 0.95 * d) / 2, (B - 0.8 * bf) / 2
    out = {"m": m, "n": n}

    def run(method):
        P = g(c, "Pu" if method is LRFD else "Pa")
        M = g(c, "Mu" if method is LRFD else "Ma")
        t = bpl.triangular_bending(P, M, N, B, m, n, g(c, "fc"), 1.0, method)
        out.update(e=t.e, e_kern=t.e_kern)
        tp = math.sqrt(4 * t.M_plate / ((0.9 if method is LRFD else 1 / 1.67) * q("50 ksi")))
        return {"fp_axial": t.fp_axial, "fp_bending": t.fp_bending, "fp_max": t.fp_max,
                "fp_min": t.fp_min, "fp_available": t.fp_available, "fp_at_m": t.fp_at_m,
                "M_plate": t.M_plate, "tp_req": tp}

    out.update(by_method(run))
    return out


def case_b_2_2(c):
    N, B, d = g(c, "N"), g(c, "B"), g(c, "d")
    m = (N - 0.95 * d) / 2
    edge = g(c, "rod_edge_distance")
    out = {"m": m}

    def run(method):
        P = g(c, "Pu" if method is LRFD else "Pa")
        M = g(c, "Mu" if method is LRFD else "Ma")
        t = bpl.triangular_bending(P, M, N, B, m, 0.0, g(c, "fc"), 4.0, method, rod_edge=edge)
        out.update(e=t.e, bearing_length=t.bearing_length)
        m_tension = t.T / 2 / 2  # per rod T/2 over b_eff = 2 (m - edge), arm (m - edge)
        phi = 0.9 if method is LRFD else 1 / 1.67
        tp = math.sqrt(4 * max(t.M_plate, m_tension) / (phi * q("50 ksi")))
        return {"fp_available": t.fp_available, "T": t.T, "r_rod": t.T / 2,
                "fp_at_m": t.fp_at_m, "M_plate_compression": t.M_plate,
                "M_plate_tension": m_tension, "tp_req": tp}

    out.update(by_method(run))
    return out


def case_4_7_3(c):
    rod = BoltSpec(diameter=g(c, "rod_diameter"), grade=F36)
    tw, g_, tp = g(c, "tw"), g(c, "rod_pattern"), g(c, "tp")
    a = (g_ - tw) / 2
    bo = anchors.breakout_tension(g(c, "hef"), g(c, "fc"), 0, LRFD, span_x=g_, span_y=g_)
    hook = anchors.pullout_hook(rod.diameter, g(c, "hook_eh"), g(c, "fc"), 0, LRFD)
    out = {"rod_Rn": rod.material.Fu * anchors.tensile_stress_area(rod.diameter), "a": a,
           "b_eff": 2 * a, "weld_kds": 1.5,
           "weld_Rn": first(welds.fillet_weld_per_length(g(c, "weld_size"), q("70 ksi"), 0, LRFD,
                                                         90), "R_n"),
           "hook_Np": first(hook, "N_p"), "hook_phiNpn": hook.capacity,
           "A_Nc": first(bo, "A_{Nc}"), "A_Nco": first(bo, "A_{Nco}"), "Nb": first(bo, "N_b"),
           "Ncbg": first(bo, "N_{cbg}"), "phiNcbg": bo.capacity}

    def run(method):
        r = -g(c, "Pu" if method is LRFD else "Pa") / 4
        plate = transfer.plate_bending_at_rods(r, a, tp, q("50 ksi"), method)
        mp = first(plate, "M_r")
        phi = 0.9 if method is LRFD else 1 / 1.67
        return {"r_rod": r, "rod_strength": out["rod_Rn"] * (0.75 if method is LRFD else 0.5),
                "M_plate": mp, "tp_req": math.sqrt(4 * mp / (2 * a * phi * q("50 ksi"))),
                "weld_demand": r / (2 * a),
                "weld_strength": welds.fillet_weld_per_length(g(c, "weld_size"), q("70 ksi"), 0,
                                                              method, 90).capacity,
                "web_stress": 2 * r / (2 * a * tw),  # one rod on each side of the web
                "web_strength": q("50 ksi") * (0.9 if method is LRFD else 1 / 1.67)}

    out.update(by_method(run))
    return out


def case_4_7_4(c):
    rod = BoltSpec(diameter=g(c, "rod_diameter"), grade=F36)
    shear = bolts.bolt_shear(rod, 0, LRFD)
    bo = anchors.breakout_shear(rod.diameter, q("12 in"), g(c, "ca1"), g(c, "fc"), 0, LRFD,
                                spacing=g(c, "rod_pattern"))
    return {"rod_Rnv": first(shear, "R_n"), "A_Vc": first(bo, "A_{Vc}"),
            "A_Vco": first(bo, "A_{Vco}"), "Vb": first(bo, "V_b"), "Vcbg": first(bo, "V_{cbg}"),
            "lrfd.rod_phiRnv": shear.capacity, "lrfd.group_phiRnv": 2 * shear.capacity,
            "lrfd.phiVcbg": bo.capacity}


def case_4_7_5(c):
    fc, w, emb, t = g(c, "fc"), g(c, "lug_width"), g(c, "lug_embedment"), g(c, "lug_thickness")
    bo = anchors.breakout_tension(g(c, "hef"), fc, 0, LRFD, span_x=g(c, "rod_pattern"),
                                  edges=anchors.Edges(bottom=q("10.8 in")))
    brg = anchors.shear_lug_bearing(w, emb, fc, 0, LRFD)
    lug = anchors.shear_lug_breakout(w, emb, q("14.5 in"), fc, 0, LRFD)
    out = {"f": g(c, "N") / 2 - (g(c, "N") - g(c, "rod_pattern")) / 2, "hef_min_lug": 2.5 * emb,
           "Nb": first(bo, "N_b"), "psi_ed_N": first(bo, r"\psi_{ed,N}"),
           "A_Nco": first(bo, "A_{Nco}"), "A_Nc": first(bo, "A_{Nc}"),
           "Ncbg": first(bo, "N_{cbg}"), "phiNcbg": bo.capacity,
           "A_ef_sl": w * emb, "V_brg_sl": first(brg, "V_{brg,sl}"), "phiV_brg_sl": brg.capacity,
           "lug_A_Vc": first(lug, "A_{Vc}"), "lug_A_Vco": first(lug, "A_{Vco}"),
           "lug_Vb": first(lug, "V_b"), "lug_Vcb": first(lug, "V_{cb}"),
           "lug_phiVcb": lug.capacity, "weld_kds": 1.5}

    def run(method):
        V = g(c, "Vu" if method is LRFD else "Va")
        M = V * q("3.00 in")
        res = {"M": M}
        sy, sr, fy_, _fr = transfer.lug_steel_checks(w, t, q("50 ksi"), q("65 ksi"), V, M, method)
        res.update(lug_shear_yield=sy.capacity, lug_shear_rupture=sr.capacity,
                   lug_flexure_yield=fy_.capacity)
        lw = transfer.lug_weld(w, t, g(c, "lug_weld"), q("70 ksi"), V, M, method)
        res.update(weld_demand=lw.demand, weld_strength=lw.capacity)
        if method is LRFD:
            r = bpl.rectangular_bending(0.0, M, g(c, "N"), g(c, "B"), q("4.25 in"), fc, 4.0,
                                        method)
            res.update(fp_max=r.fp_max, q_max=r.q_max, Y=r.Y, T=r.T, r_rod=r.T / 2)
        return res

    out.update(by_method(run))
    return out


def case_4_7_6(c):
    rod = BoltSpec(diameter=g(c, "rod_diameter"), grade=F36)
    out = {"lever_arm": (g(c, "tp") + g(c, "washer_thickness") / 2) / 2,
           "Fnt": rod.material.Fnt, "Fnv": rod.Fnv, "Z": rod.diameter**3 / 6}

    def run(method):
        lrfd = method is LRFD
        V = g(c, "VW") * (1.0 if lrfd else 0.6)
        N = -(0.9 if lrfd else 0.6) * g(c, "PD") + (1.0 if lrfd else 0.6) * g(c, "PW")
        r = transfer.rod_tension_shear_bending(rod, 4, N, V, g(c, "tp"),
                                               g(c, "washer_thickness"), method)
        res = {"V": V, "N": N, "M_rod": first(r, "M_r"), "fv": V / (4 * rod.area),
               "ft": first(r, "f_t"), "Fnt_available": r.capacity / rod.area}
        t, fu = g(c, "washer_thickness"), q("65 ksi")
        res["washer_bearing_strength"] = bolts.bolt_bearing(
            rod, t, fu, 0, method, deformation_considered=False).capacity
        res["washer_tearout_strength"] = bolts.bolt_tearout(
            rod, t, fu, q("1.19 in"), 0, method, deformation_considered=False).capacity
        return res

    out.update(by_method(run))
    return out


def case_4_7_7(c):
    d, fc, hef = g(c, "rod_diameter"), g(c, "fc"), g(c, "hef")
    fu = q("58 ksi")
    bo = anchors.breakout_tension(hef, fc, 0, LRFD, span_x=q("28 in"), span_y=q("6.5 in"))
    po = anchors.pullout(g(c, "A_brg"), fc, 0, LRFD)
    vs = anchors.steel_shear(d, fu, fu, 0, LRFD, grout_pad=True)
    pr = anchors.pryout(first(bo, "N_{cbg}"), hef, 0, LRFD)
    s = math.hypot(10.125, 12.0)
    Vu, Nu = 180e0 * 10.125 / s, 180e0 * 12.0 / s
    it = anchors.tension_shear_interaction(q(f"{Nu} kip"), bo.capacity, q(f"{Vu / 8} kip"),
                                           vs.capacity)
    a = (2 * q("3.25 in") - g(c, "tw")) / 2
    out = {"Nsa": first(anchors.steel_tension(d, fu, fu, 0, LRFD), "N_{sa}"),
           "phiNsa": anchors.steel_tension(d, fu, fu, 0, LRFD).capacity,
           "A_Nc": first(bo, "A_{Nc}"), "A_Nco": first(bo, "A_{Nco}"), "Nb": first(bo, "N_b"),
           "Ncbg": first(bo, "N_{cbg}"), "phiNcbg": bo.capacity, "Np": first(po, "N_p"),
           "phiNpn": po.capacity, "Vsa": first(vs, "V_{sa}") * 0.8, "phiVsa": vs.capacity,
           "Ncpg": first(bo, "N_{cbg}"), "Vcpg": first(pr, "V_{cpg}"), "phiVcpg": pr.capacity,
           "interaction": it.demand, "a": a, "b_e": 2 * a,
           "plate_Mn": first(elements.flexural_yielding(2 * a * g(c, "tp") ** 2 / 4, q("50 ksi"),
                                                        0, LRFD), "M_n"),
           "setting_plate_Rn": first(bolts.bolt_bearing(
               BoltSpec(diameter=d, grade=F36), g(c, "setting_plate_thickness"), q("65 ksi"), 0,
               LRFD), "R_n")}

    def run(method):
        lrfd = method is LRFD
        force = q("180 kip" if lrfd else "120 kip")
        V, N = force * 10.125 / s, force * 12.0 / s
        plate = transfer.plate_bending_at_rods(N / 8, a, g(c, "tp"), q("50 ksi"), method)
        weld = FilletWeld(size=g(c, "weld_size"), length=q("48 in"))
        return {"V": V, "N": N, "V_rod": V / 8, "N_rod": N / 8, "M_plate": first(plate, "M_r"),
                "plate_strength": plate.capacity,
                "weld_strength": welds.fillet_weld(weld, 0, method, theta=90).capacity,
                "setting_plate_strength": bolts.bolt_bearing(
                    BoltSpec(diameter=d, grade=F36), g(c, "setting_plate_thickness"),
                    q("65 ksi"), 0, method).capacity}

    out.update(by_method(run))
    return out


def case_4_7_8(c):
    d, bf = q("24.1 in"), q("12.8 in")
    N, B, fc = g(c, "N"), g(c, "B"), g(c, "fc")
    D, W = g(c, "PD"), g(c, "brace_P_W")
    weld = FilletWeld(size=g(c, "weld_size"), length=2 * g(c, "weld_length"))
    out = {"A1": N * B, "Pp": 1.7 * fc * N * B, "n_prime": math.sqrt(d * bf) / 4,
           "m": (N - 0.95 * d) / 2, "n": (B - 0.8 * bf) / 2,
           "weld_Rn": first(welds.fillet_weld(weld, 0, LRFD), "R_n"),
           "web_rupture_Rn": first(elements.shear_rupture(
               g(c, "tw") * g(c, "weld_length"), q("65 ksi"), 0, LRFD), "R_n")}

    def run(method):
        lrfd = method is LRFD
        pmax = 1.2 * D + W if lrfd else D + 0.6 * W
        pmin = 0.9 * D + W if lrfd else 0.6 * D + 0.6 * W
        r = bpl.compression_design(pmax, d, bf, N, B, q("50 ksi"), fc, 4.0, method)
        res = {"P_max": pmax, "P_min": pmin, "P_1a": 1.4 * D if lrfd else D,
               "V": g(c, "brace_V_W") * (1 if lrfd else 0.6),
               "phiPp" if lrfd else "Pp_over_Omega": r.Pp_available, "X": r.X,
               "lambda": r.lam, "l": r.l_crit, "tp_req": r.tp_req,
               "weld_strength": welds.fillet_weld(weld, 0, method).capacity,
               "web_rupture_strength": elements.shear_rupture(
                   g(c, "tw") * g(c, "weld_length"), q("65 ksi"), 0, method).capacity}
        if lrfd:
            res["friction_phiVn"] = transfer.friction(pmin, N * B, fc, 0).capacity
        return res

    out.update(by_method(run))
    return out


def case_4_7_15(c):
    e8, fc = q("8 in"), g(c, "fc")
    bo = anchors.breakout_tension(g(c, "hef_final"), fc, 0, LRFD, span_x=q("4 in"),
                                  span_y=q("4 in"), edges=anchors.Edges(e8, e8, e8, e8))
    nu = -g(c, "Pu")
    return {"hef_effective": first(bo, "h_{ef}"), "A_Nc": first(bo, "A_{Nc}"),
            "A_Nco": first(bo, "A_{Nco}"), "Nb": first(bo, "N_b"), "Ncbg": first(bo, "N_{cbg}"),
            "lrfd.phiNcbg": bo.capacity, "phi_reinforcement": 0.75,
            "As_req": nu / (0.75 * g(c, "fy_rebar")), "As": 4 * g(c, "rebar_area_each"),
            "ca1": e8, "side_face_limit": 2.5 * e8}


def case_5_3_1(c):
    d, bf, tf, tw = g(c, "d"), g(c, "bf"), g(c, "tf"), g(c, "tw")
    emb = seismic.embedded_base_moment(g(c, "Vu"), g(c, "d_embed"), bf,
                                       g(c, "foundation_width"), g(c, "fc"), g(c, "Mu"))
    face = seismic.face_plate_design(g(c, "Pu"), d, bf, tf, tw, g(c, "fc"), q("50 ksi"))
    return {"d_embed_estimate": 1.5 * d, "fb": first(emb, "f_b"), "M_HB": first(emb, "M_{HB}"),
            "lrfd.phiM_HB": emb.capacity, "A1_face_plates": face["A1"],
            "lrfd.phiPp": face["phiPp"], "l": face["l"], "tp_min": face["tp_min"],
            "tp_min_seismic": face["tp_min_seismic"]}


def case_6_4_1(c):
    N, B, fc = g(c, "N"), g(c, "B"), g(c, "fc")
    f = N / 2 - g(c, "rod_edge_distance")
    r = bpl.rectangular_bending(g(c, "Pu"), g(c, "Mu"), N, B, f, fc, 4.0, LRFD)
    duct = seismic.ductile_anchors(r.T, 3, q("55 ksi"), q("75 ksi"), g(c, "d_reduced"), f,
                                   g(c, "rod_diameter"))
    bo = anchors.breakout_tension(g(c, "hef"), fc, 0, LRFD, span_x=g(c, "rod_spacing_side"),
                                  seismic=True)
    washer = g(c, "washer_plate") ** 2 - math.pi * g(c, "rod_diameter") ** 2 / 4
    po = anchors.pullout(washer, fc, 0, LRFD, seismic=True)
    le = g(c, "d") - 2 * g(c, "k_des")
    return {"f": f, "A_reduced_min": duct.A_reduced_min, "T_reduced": duct.T_reduced,
            "RtT_reduced": duct.RtT_reduced, "A_brg": washer, "pullout_strength": po.capacity,
            "A_Nc": first(bo, "A_{Nc}"), "A_Nco": first(bo, "A_{Nco}"), "Nb": first(bo, "N_b"),
            "Ncbg": first(bo, "N_{cbg}"), "breakout_strength": bo.capacity,
            "N_required": duct.N_required, "weld_le": le,
            "weld_D_req": q("50 kip") / (q("1.392 kip/in") * 2 * le),
            "M_total_with_lug": g(c, "Mu") + g(c, "Vu") * g(c, "lug_lever"),
            "lrfd.fp_max": r.fp_max, "lrfd.q_max": r.q_max, "lrfd.e": r.e,
            "lrfd.e_crit": r.e_crit, "lrfd.Y": r.Y, "lrfd.T": r.T,
            "lrfd.tp_req": bpl.plate_thickness_tension(duct.N_required, g(c, "x"), B,
                                                       q("50 ksi"), LRFD)}


CASE_FUNCTIONS = {
    "4.7-1": case_4_7_1, "4.7-2": case_4_7_2, "B.3-1": case_b_3_1, "4.7-9": case_4_7_9,
    "4.7-10": case_4_7_10, "4.7-11": case_4_7_11, "4.7-12": case_4_7_12,
    "4.7-13": case_4_7_13, "4.7-14": case_4_7_14, "B.2-1": case_b_2_1, "B.2-2": case_b_2_2,
    "4.7-3": case_4_7_3, "4.7-4": case_4_7_4, "4.7-5": case_4_7_5, "4.7-6": case_4_7_6,
    "4.7-7": case_4_7_7, "4.7-8": case_4_7_8, "4.7-15": case_4_7_15, "5.3-1": case_5_3_1,
    "6.4-1": case_6_4_1,
}


def _expected(case):
    out = {}
    for key, value in case["expected"].items():
        if isinstance(value, dict):
            out.update({f"{key}.{k}": v for k, v in value.items()})
        else:
            out[key] = value
    return out


@pytest.mark.parametrize("case_id", sorted(CASE_FUNCTIONS))
def test_dg1_example(case_id):
    case = load(case_id)
    expected = _expected(case)
    computed = CASE_FUNCTIONS[case_id](case)
    unknown = set(computed) - set(expected)
    assert not unknown, f"computed keys not in the case file: {sorted(unknown)}"
    tolerances = case.get("tolerances", {})
    failures = []
    for key, value in computed.items():
        target = q(expected[key])
        tol = tolerances.get(key.split(".")[-1], case.get("tolerance", 0.01))
        if not math.isclose(value, target, rel_tol=tol, abs_tol=1e-9):
            failures.append(f"{key}: computed {value:.6g}, DG1 {target:.6g} (tol {tol:.1%})")
    assert not failures, "\n".join(failures)
    coverage = len(computed) / len(expected)
    assert coverage >= 0.5, f"only {coverage:.0%} of the published values are checked"


def test_every_implemented_case_is_checked():
    implemented = {tomllib.loads(p.read_text())["id"] for p in CASES.glob("ex_*.toml")
                   if tomllib.loads(p.read_text())["status"] == "implemented"}
    assert implemented == set(CASE_FUNCTIONS)
