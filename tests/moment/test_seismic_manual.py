# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""AISC 358 seismic connections against published worked examples.

* AISC Seismic Design Manual, 3rd ed. (2018), Examples 4.3.6 (RBS) and 4.3.7 (BFP),
  W24X76 beams on a W14X176 column; they follow AISC 358-16 and AISC 341-16.
* AISC Design Guide 39, End-Plate Moment Connections (2023), Examples 6.3-2 (4ES,
  W24X62 on W14X159) and 6.3-3 (8ES, W36X150 on W18X258), per AISC 358-22.

The projects are in ``tests/reference/aisc358/``. The published values are quoted in
kip and inch with the rounding of the examples. Where OpenConex follows the 2022
editions or a more conservative reading, the test states the difference and checks the
OpenConex value by hand (docs/tecnico/07-validacion.md, "AISC 358-22").
"""

import math
from pathlib import Path

import pytest

from openconex.connections.moment.fr_moment import check_moment_envelope
from openconex.io.project import load_project
from openconex.units import Kind, from_internal

REFERENCE = Path(__file__).parents[1] / "reference" / "aisc358"


def results(name):
    project = load_project(REFERENCE / f"{name}.ocnx")
    rs = check_moment_envelope(project.moment_model(), project.load_combinations(),
                               project.case_forces(), project.column_forces())
    return {r.id: r for r in rs if r.combo == "AISC 358"}


def kip(v):
    return from_internal(v, Kind.FORCE, "kip")


def kip_in(v):
    return from_internal(v, Kind.MOMENT, "kip*in")


def inch(v):
    return from_internal(v, Kind.LENGTH, "in")


@pytest.fixture(scope="module")
def rbs():
    return results("sdm_4.3.6_rbs")


@pytest.fixture(scope="module")
def bfp():
    return results("sdm_4.3.7_bfp")


@pytest.fixture(scope="module")
def es4():
    return results("dg39_6.3-2_4es")


@pytest.fixture(scope="module")
def es8():
    return results("dg39_6.3-3_8es")


# -- SDM Example 4.3.6, RBS ---------------------------------------------------------------
def test_sdm_rbs_capacity_design(rbs):
    """Z_RBS = 137, M_pr = 8,670, S_h = 14.5, L_h = 316, V_RBS = 72.1, M_f = 9,720,
    M_pe = 11,000, V_u = 73.7, φV_n = 315."""
    face = rbs["seismic.rbs_moment_at_face"]
    assert kip_in(face.demand) == pytest.approx(9720, rel=5e-3)
    assert kip_in(face.capacity) == pytest.approx(11000, rel=5e-3)
    shear = rbs["seismic.beam_shear"]
    assert kip(shear.demand) == pytest.approx(73.7, rel=5e-3)
    assert kip(shear.capacity) == pytest.approx(315, rel=5e-3)


def test_sdm_rbs_column(rbs):
    """Local limit states 483, 424 and 668 kips (unchanged); the 2016 example compares them
    with P_f = M_f/d* = 419 kips, AISC 341-22 §E3.6f.1(a) with 0.85 M_f/d* for a welded web.
    Continuity plates: b ≥ 4.08 in., t ≥ 0.75 t_bf = 0.510 in."""
    for key, value in (("moment.column_flange_local_bending", 483),
                       ("moment.column_web_local_yielding", 424),
                       ("moment.column_web_crippling", 668)):
        assert kip(rbs[key].capacity) == pytest.approx(value, rel=5e-3), key
        assert kip(rbs[key].demand) == pytest.approx(0.85 * 419, rel=1e-2), key
    assert inch(rbs["seismic.continuity_plate_width"].demand) == pytest.approx(4.08, rel=5e-3)
    assert inch(rbs["seismic.continuity_plate_thickness"].demand) == pytest.approx(0.510,
                                                                                   rel=5e-3)


def test_sdm_rbs_panel_zone(rbs):
    """R_u = (9,720 + 9,220)/23.22 − 125 = 691 kips, the opposite beam with the smaller
    M_f; with a 1/2 in. doubler, Eq. J10-11 with t_w + t_p; t_min = (d_z + w_z)/90 = 0.390."""
    pz = rbs["moment.column_panel_zone"]
    assert kip(pz.demand) == pytest.approx(691, rel=5e-3)
    t = 0.830 + 0.5
    cap = 0.6 * 50 * 15.2 * t * (1 + 3 * 15.7 * 1.31**2 / (23.9 * 15.2 * t))
    assert kip(pz.capacity) == pytest.approx(cap, rel=5e-3)
    assert inch(rbs["seismic.panel_zone_thickness"].demand) == pytest.approx(0.390, rel=5e-3)
    assert inch(rbs["seismic.doubler_thickness"].demand) == pytest.approx(0.390, rel=5e-3)


def test_sdm_rbs_column_beam_ratio(rbs):
    """ΣM*_pc = 34,100 projected to the beam centerline (h = 75 and 84 in.), ΣM*_be =
    19,800 with both beam ends (V_RBS 72.1 and 37.6 kips)."""
    ratio = rbs["seismic.column_beam_ratio"]
    assert kip_in(ratio.capacity) == pytest.approx(34100, rel=5e-3)
    assert kip_in(ratio.demand) == pytest.approx(19800, rel=1e-2)


# -- SDM Example 4.3.7, BFP ---------------------------------------------------------------
def test_sdm_bfp_plate_and_bolts(bfp):
    """F_pr = M_f/(d + t_p) = 591 kips; 14 bolts × 0.9 × 50.5 = 636; plate yielding 675,
    rupture 614, buckling 608 (L/r = 6.75). M_f = 14,900 in OpenConex: the example takes
    V_h with w_u L_cf/2 instead of w_u L_h/2 and rounds M_f to 15,000."""
    fpr = kip(bfp["seismic.bfp_bolts"].demand)
    assert fpr == pytest.approx(591, rel=1.5e-2)
    for key, value in (("seismic.bfp_bolts", 636), ("seismic.bfp_plate_yielding", 675),
                       ("seismic.bfp_plate_rupture", 614),
                       ("seismic.bfp_plate_compression", 608)):
        assert kip(bfp[key].capacity) == pytest.approx(value, rel=5e-3), key
        assert kip(bfp[key].demand) == pytest.approx(fpr), key
    assert kip_in(bfp["seismic.bfp_beam_flange_rupture"].demand) == pytest.approx(
        1.1 * 50 * 200, rel=5e-3)
    shear = bfp["seismic.beam_shear"]
    assert kip(shear.demand) == pytest.approx(102, rel=1.5e-2)
    assert kip(shear.capacity) == pytest.approx(315, rel=5e-3)


def test_sdm_bfp_block_shear_without_expected_strength(bfp):
    """The example takes R_t F_u and R_y F_y of the beam flange (909 kips); OpenConex
    keeps F_u and F_y of AISC 360 §J4.3, which is smaller."""
    assert kip(bfp["seismic.bfp_block_shear"].capacity) < 909


def test_sdm_bfp_column(bfp):
    """Flange local bending 483, web local yielding 458 and crippling 719 kips for
    F_pr; continuity plates b ≥ 4.09 in., t ≥ 0.75 × 1-1/2 in."""
    for key, value in (("moment.column_flange_local_bending", 483),
                       ("moment.column_web_local_yielding", 458),
                       ("moment.column_web_crippling", 719)):
        assert kip(bfp[key].capacity) == pytest.approx(value, rel=5e-3), key
    assert inch(bfp["seismic.continuity_plate_width"].demand) == pytest.approx(4.09, rel=5e-3)
    assert inch(bfp["seismic.continuity_plate_thickness"].demand) == pytest.approx(1.125)


def test_sdm_bfp_column_beam_ratio(bfp):
    """ΣM*_pc = 34,100 and ΣM*_be = 15,000 + 14,300 + (101 + 68.1)(15.2/2) = 30,600."""
    ratio = bfp["seismic.column_beam_ratio"]
    assert kip_in(ratio.capacity) == pytest.approx(34100, rel=5e-3)
    assert kip_in(ratio.demand) == pytest.approx(30600, rel=1e-2)


def test_sdm_bfp_panel_zone_uses_the_2022_demand(bfp):
    """The 2016 example projects R_y F_y Z_e (782 kips); AISC 341-22 Commentary Eq. C-E3-11
    sums M_f, and AISC 358-22 §7.5 Step 17 takes the depth d + t_p:
    (15,000 + 14,300)/(23.9 + 1.5) − 159 = 994 kips."""
    pz = bfp["moment.column_panel_zone"]
    assert kip(pz.demand) == pytest.approx((15000 + 14300) / (23.9 + 1.5) - 159, rel=1e-2)
    assert kip(pz.demand) > 782


# -- DG39 Example 6.3-2, 4ES --------------------------------------------------------------
def test_dg39_4es_end_plate(es4):
    """M_f = 10,400 (S_h = 7.63 with the detailed L_st = 6.5 in.; OpenConex takes
    L_st = h_st/tan 30° = 6.28 in.), Y_p = 223 in. with b_p,eff = 8.04 in., bolts
    1-1/4 in. A490-N, t_s ≥ 0.430 in., φV_n = 306, compression bolts 301."""
    rupture = es4["seismic.end_plate_bolt_rupture"]
    assert kip_in(rupture.demand) == pytest.approx(10400, rel=1e-2)
    ab = math.pi * 1.25**2 / 4
    assert kip_in(rupture.capacity) == pytest.approx(0.9 * 2 * 113 * ab * (25.4 + 20.8),
                                                     rel=5e-3)
    yielding = es4["seismic.end_plate_yielding"]
    assert kip_in(yielding.capacity) == pytest.approx(50 * 1.125**2 * 223 / 1.11, rel=5e-3)
    assert inch(es4["seismic.end_plate_stiffener_thickness"].demand) == pytest.approx(
        0.430, rel=5e-3)
    assert es4["seismic.end_plate_stiffener_slenderness"].demand == pytest.approx(7.25)
    shear = es4["seismic.beam_shear"]
    assert kip(shear.demand) == pytest.approx(89.7, rel=5e-3)
    assert kip(shear.capacity) == pytest.approx(306, rel=5e-3)
    assert kip(es4["seismic.end_plate_compression_bolts"].capacity) == pytest.approx(
        301, rel=5e-3)


def test_dg39_4es_column(es4):
    """t_cf,req = 1.08 in., φ_d R_n = 610 kips (Eq. 6.7-15). Web local yielding 517 and
    crippling 665 kips with l_b = t_bf + w + 2t_p; AISC 358-22 Eq. 6.7-17 writes
    l_b = t_bf + 2w + 2t_p, which OpenConex follows (529 and 681 kips)."""
    assert inch(es4["seismic.end_plate_column_flange"].demand) == pytest.approx(1.08, rel=1e-2)
    assert kip(es4["moment.column_flange_strength"].capacity) == pytest.approx(610, rel=5e-3)
    lb = 0.59 + 2 * 0.3125 + 2 * 1.125
    assert kip(es4["moment.column_web_local_yielding"].capacity) == pytest.approx(
        (6 * 1.79 + lb) * 50 * 0.745, rel=5e-3)
    assert kip(es4["moment.column_web_crippling"].capacity) == pytest.approx(665, rel=3e-2)


def test_dg39_4es_panel_zone_and_ratio(es4):
    """V_upz = F_fu − V_uc − P_ub/2 = 450 − 69 − 14 = 367 kips; OpenConex does not subtract
    the beam axial force (381 kips). φR_n = 419; ΣM*_pc = 27,500; ΣM*_be = 11,000;
    t_cw,req = 0.390 in."""
    pz = es4["moment.column_panel_zone"]
    assert kip(pz.demand) == pytest.approx(367 + 28 / 2, rel=1e-2)
    assert kip(pz.capacity) == pytest.approx(419, rel=5e-3)
    ratio = es4["seismic.column_beam_ratio"]
    assert kip_in(ratio.capacity) == pytest.approx(27500, rel=5e-3)
    assert kip_in(ratio.demand) == pytest.approx(11000, rel=5e-3)
    assert inch(es4["seismic.panel_zone_thickness"].demand) == pytest.approx(0.390, rel=5e-3)


# -- DG39 Example 6.3-3, 8ES --------------------------------------------------------------
def test_dg39_8es_end_plate(es8):
    """M_f = 39,600, bolts 1-3/8 in. A490-N, Y_p = 528 in., t_s ≥ 0.625 in.
    (h_st/t_s = 12.0), φV_n = 673, compression bolts 725."""
    rupture = es8["seismic.end_plate_bolt_rupture"]
    assert kip_in(rupture.demand) == pytest.approx(39600, rel=5e-3)
    assert kip_in(rupture.capacity) == pytest.approx(
        0.9 * 2 * 113 * 1.485 * (41.2 + 37.4 + 32.5 + 28.7), rel=5e-3)
    yielding = es8["seismic.end_plate_yielding"]
    assert kip_in(yielding.capacity) == pytest.approx(50 * 1.375**2 * 528 / 1.11, rel=5e-3)
    assert inch(es8["seismic.end_plate_stiffener_thickness"].demand) == pytest.approx(0.625)
    assert es8["seismic.end_plate_stiffener_slenderness"].demand == pytest.approx(12.0)
    shear = es8["seismic.beam_shear"]
    assert kip(shear.demand) == pytest.approx(201, rel=5e-3)
    assert kip(shear.capacity) == pytest.approx(673, rel=5e-3)
    assert kip(es8["seismic.end_plate_compression_bolts"].capacity) == pytest.approx(
        725, rel=5e-3)


def test_dg39_8es_prequalification_limits(es8):
    """L_c/d = (40 ft − 21.5 in.)/35.9 in. = 12.8 ≥ 7; t_bf, b_bf, d, t_p, b_p, g, p_f and
    p_b within Table 6.1 (g = p_f = p_b at the upper limit)."""
    assert es8["seismic.span_depth"].capacity == pytest.approx(12.8, rel=5e-3)
    for key in ("tbf", "bbf", "d", "tp", "bp", "g", "pf", "pb"):
        assert es8[f"seismic.end_plate_{key}"].status.value == "ok", key
    for key in ("g", "pf", "pb"):
        assert es8[f"seismic.end_plate_{key}"].ratio == pytest.approx(1.0), key


def test_dg39_8es_column(es8):
    """t_cf,req = 1.54 in., φ_d R_n = 2,800 kips, crippling 1,960 kips (l_b with one w)."""
    assert inch(es8["seismic.end_plate_column_flange"].demand) == pytest.approx(1.54, rel=5e-3)
    assert kip(es8["moment.column_flange_strength"].capacity) == pytest.approx(2800, rel=5e-3)
    assert kip(es8["moment.column_web_crippling"].capacity) == pytest.approx(1960, rel=1.5e-2)


def test_dg39_8es_panel_zone_and_ratio(es8):
    """V_upz = 1,130 − 540 − 40/2 = 570 kips (OpenConex 590 without P_ub/2), φR_n = 982;
    ΣM*_pc = 57,100; ΣM*_be = 41,800; t_cw,req = 0.566 in."""
    pz = es8["moment.column_panel_zone"]
    assert kip(pz.demand) == pytest.approx(570 + 40 / 2, rel=1e-2)
    assert kip(pz.capacity) == pytest.approx(982, rel=5e-3)
    ratio = es8["seismic.column_beam_ratio"]
    assert kip_in(ratio.capacity) == pytest.approx(57100, rel=5e-3)
    assert kip_in(ratio.demand) == pytest.approx(41800, rel=5e-3)
    assert inch(es8["seismic.panel_zone_thickness"].demand) == pytest.approx(0.566, rel=5e-3)


def test_built_up_beam_takes_phi_v_090():
    """DG39 Example 6.3-1 (built-up members): φ_v = 0.90, AISC 360 §G2.1(b)."""
    import json

    from openconex.io.project import Project
    d = json.loads((REFERENCE / "dg39_6.3-2_4es.ocnx").read_text(encoding="utf-8"))
    d["moment_connection"]["beam"] = {"type": "W", "name": "PL", "d": "23.7 in", "bf": "7.04 in",
                                      "tf": "0.59 in", "tw": "0.43 in",
                                      "grade": "ASTM A992"}
    project = Project.model_validate(d)
    rs = check_moment_envelope(project.moment_model(), project.load_combinations(),
                               project.case_forces(), project.column_forces())
    shear = next(r for r in rs if r.id == "seismic.beam_shear")
    assert kip(shear.capacity) == pytest.approx(0.9 * 0.6 * 50 * 23.7 * 0.43, rel=5e-3)
