# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Prequalified seismic moment connections (AISC 358-22, AISC 341-22).

The published worked examples are in test_seismic_manual.py; the values below are
independent hand calculations, in kip and inch, from the AISC Shapes Database
dimensions and the equations of AISC 358-22 (§2.4, §2.5, §5.7, §6.7, §7.5, §8.6) and
AISC 341-22 (Tables A3.2 and D1.1b, §E3.4a, §E3.6e, §E3.6f), whose numbers were
checked against the text of the standards (see docs/tecnico/07-validacion.md).
"""

import json
import math
from pathlib import Path

import pytest
from pydantic import ValidationError

from openconex.cli import main
from openconex.connections.moment.fr_moment import check_moment_envelope
from openconex.connections.moment.seismic import expected_ratios, nominal_depth
from openconex.io.project import Project, load_project
from openconex.report.builder import build_report
from openconex.units import Kind, from_internal

EXAMPLES = Path(__file__).parents[2] / "examples"
NAMES = ["moment_seismic_rbs", "moment_seismic_wuf_w", "moment_seismic_bfp",
         "moment_seismic_bueep", "moment_seismic_bseep_8es"]


def seismic(project):
    results = check_moment_envelope(project.moment_model(), project.load_combinations(),
                                    project.case_forces(), project.column_forces())
    return {r.id: r for r in results if r.combo == "AISC 358" and r.id.startswith("seismic.")}


def kip(v):
    return from_internal(v, Kind.FORCE, "kip")


def kip_in(v):
    return from_internal(v, Kind.MOMENT, "kip*in")


def inch(v):
    return from_internal(v, Kind.LENGTH, "in")


def data(name):
    return json.loads((EXAMPLES / f"{name}.ocnx").read_text(encoding="utf-8"))


def project_with(name, **seismic_changes):
    d = data(name)
    d["moment_connection"]["seismic"].update(seismic_changes)
    return Project.model_validate(d)


@pytest.mark.parametrize("name", NAMES)
def test_examples_pass(name):
    project = load_project(EXAMPLES / f"{name}.ocnx")
    results = check_moment_envelope(project.moment_model(), project.load_combinations(),
                                    project.case_forces(), project.column_forces())
    failing = [(r.id, r.combo, round(r.ratio, 3)) for r in results
               if r.applicable and r.status.value == "ng"]
    assert not failing
    assert any(r.combo == "AISC 358" for r in results)


def _hinge(Zx_e, Sh, span, w=2.0 / 12, Ry=1.1, Fy=50.0, Fu=65.0, cpr=None):
    """(M_pr, V_h, M_f, V_u) of AISC 358-22 Eq. 2.4-1 to 2.4-4 and §2.5."""
    cpr = cpr or min((Fy + Fu) / (2 * Fy), 1.2)
    mpr = cpr * Ry * Fy * Zx_e
    lh = span - 2 * Sh
    vh = 2 * mpr / lh + w * lh / 2
    return mpr, vh, mpr + vh * Sh, vh + w * Sh


def test_rbs_hand_calculation():
    """W24X76 beam (d 23.9, bf 8.99, tf 0.68, Zx 200), a = 5, b = 18, c = 2 in., 26 ft."""
    r = seismic(load_project(EXAMPLES / "moment_seismic_rbs.ocnx"))
    zrbs = 200.0 - 2 * 2.0 * 0.68 * (23.9 - 0.68)
    mpr, vh, mf, vu = _hinge(zrbs, 5 + 18 / 2, 26 * 12)
    face = r["seismic.rbs_moment_at_face"]
    assert kip_in(face.demand) == pytest.approx(mf, rel=2e-3)
    assert kip_in(face.capacity) == pytest.approx(1.1 * 50 * 200, rel=2e-3)
    assert kip(r["seismic.beam_shear"].demand) == pytest.approx(vu, rel=2e-3)
    # φv Vn = 1.0 (0.6)(50)(23.9)(0.44)
    assert kip(r["seismic.beam_shear"].capacity) == pytest.approx(0.6 * 50 * 23.9 * 0.44,
                                                                  rel=2e-3)
    # a within 0.5bf..0.75bf, governed by the lower bound 4.495/5
    assert r["seismic.rbs_a"].ratio == pytest.approx(0.5 * 8.99 / 5.0, rel=1e-3)
    # column-beam ratio with W14X257 above and below, P_uc = 400 kip, two beams; the
    # gravity load reduces the hinge shear of the other beam by 2 w_u L_h/2
    mpc = 2 * 487.0 * (50 - 400 / 75.6)
    vg = 2.0 / 12 * (26 * 12 - 2 * 14) / 2
    mbe = 2 * mpr + (2 * vh - 2 * vg) * (14 + 16.4 / 2)
    ratio = r["seismic.column_beam_ratio"]
    assert kip_in(ratio.capacity) == pytest.approx(mpc, rel=3e-3)
    assert kip_in(ratio.demand) == pytest.approx(mbe, rel=3e-3)
    # limiting column flange thickness without continuity plates, b_bf/6 (Eq. E3-7)
    assert inch(r["seismic.continuity_plates"].demand) == pytest.approx(8.99 / 6, rel=2e-3)
    # panel zone thickness (dz + wz)/90
    pz = r["seismic.panel_zone_thickness"]
    assert inch(pz.demand) == pytest.approx((23.9 - 2 * 0.68 + 16.4 - 2 * 1.89) / 90,
                                            rel=2e-3)


def test_wuf_w_hinge_at_the_column_face():
    """W24X62 (Zx 153): C_pr = 1.4, S_h = 0, M_f = M_pr = 1.4 (1.1)(50)(153)."""
    r = seismic(load_project(EXAMPLES / "moment_seismic_wuf_w.ocnx"))
    mpr, vh, mf, vu = _hinge(153.0, 0.0, 26 * 12, cpr=1.4)
    assert mf == mpr and vu == vh
    assert kip(r["seismic.beam_shear"].demand) == pytest.approx(vu, rel=2e-3)
    assert "seismic.rbs_moment_at_face" not in r
    assert r["seismic.beam_weight"].ratio == pytest.approx(62 / 150, rel=1e-3)
    assert r["seismic.beam_flange_thickness"].ratio == pytest.approx(0.59, rel=1e-3)
    # single plate: t_p ≥ t_bw, welds for 0.6 R_y F_yp h_p t_p (§8.5), A572 Gr. 50 plate
    # R_y = 1.1
    assert inch(r["seismic.wuf_w_plate_thickness"].demand) == pytest.approx(0.43, rel=1e-3)
    weld = r["seismic.wuf_w_plate_weld"]
    assert kip(weld.demand) == pytest.approx(0.6 * 1.1 * 50 * 18 * 0.5, rel=2e-3)
    assert kip(weld.capacity) == pytest.approx(2 * 0.75 * 0.6 * 70 * 0.7071 * 7 / 16 * 18,
                                               rel=2e-3)


def test_welded_web_reduces_the_local_flange_force():
    """RBS and WUF-W: P_f = 0.85 M_f/d* for the J10 checks, M_f/d* for the panel zone with
    φ_v = 1.00 (AISC 341-22 §E3.6e.1, §E3.6f.1(a))."""
    project = load_project(EXAMPLES / "moment_seismic_wuf_w.ocnx")
    results = check_moment_envelope(project.moment_model(), project.load_combinations(),
                                    project.case_forces(), project.column_forces())
    r = {x.id: x for x in results if x.combo == "AISC 358"}
    _, _, mf, _ = _hinge(153.0, 0.0, 26 * 12, cpr=1.4)
    pf = mf / (23.7 - 0.59)
    assert kip(r["moment.column_web_local_yielding"].demand) == pytest.approx(0.85 * pf,
                                                                            rel=2e-3)
    pz = r["moment.column_panel_zone"]
    assert kip(pz.demand) == pytest.approx(2 * pf, rel=2e-3)
    assert any(step.expression.startswith("1") and step.symbol.startswith(r"\phi")
               for step in pz.steps)
    imf = seismic(project_with("moment_seismic_wuf_w", system="imf"))
    assert "seismic.panel_zone_thickness" not in imf


def test_bfp_hand_calculation():
    """W24X76, PL 1-1/4 x 11, 7 rows of 7/8 in. A490-X at 3 in., S_1 = 2.5 in., 28 ft."""
    r = seismic(load_project(EXAMPLES / "moment_seismic_bfp.ocnx"))
    sh = 2.5 + 3 * (7 - 1)
    _, _, mf, _ = _hinge(200.0, sh, 28 * 12)
    fpr = mf / (23.9 + 1.25)
    # beam flange net section, Eq. 7.5-1: d_hole = 15/16 + 1/16 in. in both flanges
    znet = 200.0 - 2 * (15 / 16 + 1 / 16) * 0.68 * (23.9 - 0.68)
    rupture = r["seismic.bfp_beam_flange_rupture"]
    assert kip_in(rupture.demand) == pytest.approx(1.1 * 50 * 200, rel=2e-3)
    assert kip_in(rupture.capacity) == pytest.approx(1.1 * 65 * znet, rel=2e-3)
    # maximum bolt diameter 1-1/8 in. (§7.4.4)
    assert r["seismic.bfp_bolt_diameter"].ratio == pytest.approx(0.875 / 1.125, rel=1e-6)
    ab = math.pi * 0.875**2 / 4
    rn = min(84 * ab, 2.4 * 65 * 0.875 * 0.68, 2.4 * 65 * 0.875 * 1.25)
    bolts = r["seismic.bfp_bolts"]
    assert kip(bolts.demand) == pytest.approx(fpr, rel=2e-3)
    assert kip(bolts.capacity) == pytest.approx(14 * 0.9 * rn, rel=2e-3)
    assert kip(r["seismic.bfp_plate_yielding"].capacity) == pytest.approx(50 * 11 * 1.25,
                                                                          rel=2e-3)
    an = min((11 - 2 * (15 / 16 + 1 / 16)) * 1.25, 0.85 * 11 * 1.25)
    assert kip(r["seismic.bfp_plate_rupture"].capacity) == pytest.approx(0.9 * 65 * an,
                                                                         rel=2e-3)
    # column depth: W36 with a concrete slab, W14 without (§7.3.2)
    assert r["seismic.column_depth"].ratio == pytest.approx(14 / 36, rel=1e-6)
    r = seismic(project_with("moment_seismic_bfp", slab=False))
    assert r["seismic.column_depth"].ratio == pytest.approx(1.0, rel=1e-6)


def test_bueep_hand_calculation():
    """4E: W24X62, PL 1-1/2 x 10, g 5.5, p_f,i = p_f,o = 2, 1-1/4 in. A490, 26 ft."""
    r = seismic(load_project(EXAMPLES / "moment_seismic_bueep.ocnx"))
    d, bf, tf = 23.7, 7.04, 0.59
    _, _, mf, vu = _hinge(153.0, min(d / 2, 3 * bf), 26 * 12)
    h0, h1 = d + 2 - tf / 2, d - tf - 2 - tf / 2
    ab = math.pi * 1.25**2 / 4
    rupture = r["seismic.end_plate_bolt_rupture"]
    assert kip_in(rupture.demand) == pytest.approx(mf, rel=2e-3)
    assert kip_in(rupture.capacity) == pytest.approx(0.9 * 2 * 113 * ab * (h0 + h1), rel=2e-3)
    # yield lines of the 4E plate (AISC 358-22 Table 6.2) with h to the center of the
    # compression flange and b_p,eff = b_bf + 1 in. = 8.04 in. < 10 in.
    bp, g, pf = bf + 1, 5.5, 2.0
    s = 0.5 * math.sqrt(bp * g)
    Y = bp / 2 * (h1 * (1 / pf + 1 / s) + h0 / pf - 0.5) + 2 / g * h1 * (pf + s)
    yielding = r["seismic.end_plate_yielding"]
    assert kip_in(yielding.capacity) == pytest.approx(50 * 1.5**2 * Y / 1.11, rel=3e-3)
    ffu = mf / (d - tf)
    assert kip(r["seismic.end_plate_shear_yielding"].demand) == pytest.approx(ffu / 2, rel=2e-3)
    # b_p taken not greater than b_bf + 1 in. (Eq. 6.7-7)
    assert kip(r["seismic.end_plate_shear_yielding"].capacity) == pytest.approx(
        0.6 * 50 * (bf + 1) * 1.5, rel=2e-3)
    bolts = r["seismic.end_plate_compression_bolts"]
    assert kip(bolts.demand) == pytest.approx(vu, rel=2e-3)
    assert kip(bolts.capacity) == pytest.approx(0.9 * 4 * 84 * ab, rel=2e-3)
    assert "seismic.end_plate_stiffener_thickness" not in r


def test_bseep_8es_stiffener():
    """8ES stiffener: t_s ≥ t_bw F_yb/F_ys and h_st/t_s ≤ 0.56 sqrt(E/F_ys)."""
    r = seismic(load_project(EXAMPLES / "moment_seismic_bseep_8es.ocnx"))
    st = r["seismic.end_plate_stiffener_thickness"]
    assert inch(st.demand) == pytest.approx(0.565, rel=2e-3)   # W30X116 t_w
    assert r["seismic.end_plate_stiffener_slenderness"].ratio == pytest.approx(
        (7.5 / 0.625) / (0.56 * math.sqrt(29000 / 50)), rel=2e-3)
    assert r["seismic.end_plate_pb"].ratio == pytest.approx(1.0, rel=1e-6)
    assert "seismic.end_plate_shear_yielding" not in r


def test_limits_fail_outside_prequalification():
    r = seismic(project_with("moment_seismic_rbs", rbs_c="3 in", span="12 ft"))
    assert r["seismic.rbs_c"].status.value == "ng"           # c > 0.25 bf
    assert r["seismic.span_depth"].status.value == "ng"      # 144/23.9 < 7
    r = seismic(project_with("moment_seismic_rbs", span="12 ft", system="imf"))
    assert r["seismic.span_depth"].status.value == "ok"      # IMF: ≥ 5
    assert "seismic.column_beam_ratio" not in r               # SMF only


def test_expected_strength_ratios():
    assert expected_ratios("ASTM A992") == (1.1, 1.1)
    assert expected_ratios("ASTM A36") == (1.5, 1.2)
    assert expected_ratios("ASTM A36", plate=True) == (1.3, 1.2)
    assert expected_ratios("ASTM A572 Gr. 50") == (1.1, 1.1)
    assert expected_ratios("ASTM A572 Gr. 50", plate=True) == (1.1, 1.2)
    assert expected_ratios("ASTM A709 Gr. 50W") == (1.1, 1.1)
    # not listed in Table A3.2: A572 Gr. 42 shapes, A992 and A913 plates
    assert expected_ratios("ASTM A572 Gr. 42") is None
    assert expected_ratios("ASTM A572 Gr. 42", plate=True) == (1.3, 1.0)
    assert expected_ratios("ASTM A992", plate=True) is None
    assert expected_ratios("ASTM A913 Gr. 50", plate=True) is None
    assert expected_ratios("unknown") is None
    assert nominal_depth("W36X150") == 36.0
    r = seismic(project_with("moment_seismic_wuf_w", Ry_beam=1.3))
    base = seismic(load_project(EXAMPLES / "moment_seismic_wuf_w.ocnx"))
    assert r["seismic.beam_shear"].demand > base["seismic.beam_shear"].demand


def test_width_to_thickness_limits():
    """AISC 341-22 Table D1.1b: flanges 0.30 / 0.38 sqrt(E/RyFy), moment-frame webs
    2.5 / 5.4 sqrt(E/RyFy)(1 - Ca)^2.3 with Ca = Pr/(Ry Fy Ag)."""
    root = math.sqrt(29000 / (1.1 * 50))
    r = seismic(load_project(EXAMPLES / "moment_seismic_wuf_w.ocnx"))
    assert r["seismic.column_flange_slenderness"].capacity == pytest.approx(0.30 * root,
                                                                            rel=1e-6)
    ca = 400 / (1.1 * 50 * 75.6)        # W14X257, P_r = 400 kip
    assert r["seismic.column_web_slenderness"].capacity == pytest.approx(
        2.5 * root * (1 - ca) ** 2.3, rel=2e-3)
    assert r["seismic.beam_web_slenderness"].capacity == pytest.approx(2.5 * root, rel=1e-6)
    r = seismic(project_with("moment_seismic_wuf_w", system="imf"))
    assert r["seismic.beam_flange_slenderness"].capacity == pytest.approx(0.38 * root,
                                                                          rel=1e-6)
    assert r["seismic.beam_web_slenderness"].capacity == pytest.approx(5.4 * root, rel=1e-6)


def test_continuity_plate_size():
    """AISC 341-22 §E3.6f.2: t ≥ 0.75 t_bf two-sided, reaching the beam flange tips, and
    b/t ≤ 0.56 sqrt(E/(Ry Fy)) with A572 Gr. 50 plates (Ry = 1.1)."""
    d = data("moment_seismic_rbs")
    d["moment_connection"].update(continuity_plate="1/2 in")
    r = seismic(Project.model_validate(d))
    assert "seismic.continuity_plates" not in r
    assert inch(r["seismic.continuity_plate_thickness"].demand) == pytest.approx(
        0.75 * 0.68, rel=1e-3)
    bs = (16.0 - 1.18) / 2                # W14X257 (b_f - t_w)/2
    assert inch(r["seismic.continuity_plate_width"].demand) == pytest.approx(
        (8.99 - 1.18) / 2, rel=2e-3)
    assert r["seismic.continuity_plate_slenderness"].demand == pytest.approx(bs / 0.5,
                                                                             rel=2e-3)
    assert r["seismic.continuity_plate_slenderness"].capacity == pytest.approx(
        0.56 * math.sqrt(29000 / (1.1 * 50)), rel=1e-6)


def test_project_validation():
    d = data("moment_seismic_rbs")
    d["moment_connection"]["seismic"].update(connection="bfp", bfp_s1="3 in")
    with pytest.raises(ValidationError, match="bolted_flange_plate"):
        Project.model_validate(d)
    d = data("moment_seismic_rbs")
    del d["moment_connection"]["seismic"]["rbs_c"]
    with pytest.raises(ValidationError, match=r"seismic\.rbs_c"):
        Project.model_validate(d)
    d = data("moment_seismic_bueep")
    d["moment_connection"]["seismic"]["connection"] = "bseep"
    d["moment_connection"]["seismic"]["stiffener_thickness"] = "1/2 in"
    with pytest.raises(ValidationError, match="extended_4_stiffened"):
        Project.model_validate(d)
    d = data("moment_seismic_rbs")
    d["materials"] = [{"name": "Acero X", "Fy": "50 ksi", "Fu": "65 ksi"}]
    d["moment_connection"]["beam_grade"] = "Acero X"
    with pytest.raises(ValidationError, match="R_y"):
        Project.model_validate(d)
    d["moment_connection"]["seismic"].update(Ry_beam=1.1, Rt_beam=1.1)
    assert Project.model_validate(d).moment_model().seismic.Ry_beam == 1.1
    # BFP: A36 or A572 Gr. 50 plates, A490/F2280 bolts with threads excluded (§7.4)
    for change, match in (({"grade": "ASTM A588"}, "A572 Gr. 50"),
                          ({"bolt": {"diameter": "7/8 in", "grade": "ASTM F3125 Gr. A325",
                                     "threads": "X"}}, "A490"),
                          ({"bolt": {"diameter": "7/8 in", "grade": "ASTM F3125 Gr. A490",
                                     "threads": "N"}}, "threads")):
        d = data("moment_seismic_bfp")
        d["moment_connection"].update(change)
        with pytest.raises(ValidationError, match=match):
            Project.model_validate(d)


def test_report_and_command(tmp_path):
    project = load_project(EXAMPLES / "moment_seismic_rbs.ocnx")
    report = build_report(project)
    assert any("AISC 358" in code for code in report.codes)
    assert any("M_pr" in a for a in report.assumptions)
    assert any(r.cells[1] == "AISC 358" for r in report.summary)
    out = tmp_path / "rbs"
    assert main(["moment", str(EXAMPLES / "moment_seismic_rbs.ocnx"), "-o", str(out),
                 "--html"]) == 0
    assert "Sección reducida" in out.with_suffix(".html").read_text(encoding="utf-8")


@pytest.mark.parametrize("name", NAMES)
def test_window_keeps_the_seismic_block(name):
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from openconex.gui.moment import MomentWindow
    QApplication.instance() or QApplication([])
    path = EXAMPLES / f"{name}.ocnx"
    window = MomentWindow(load_project(path), path)
    project = window.project_from_form()
    original = load_project(path).moment_connection.seismic
    got = project.moment_connection.seismic
    assert got.connection == original.connection
    assert got.system == original.system
    assert project.quantity(got.span, Kind.LENGTH) == pytest.approx(
        project.quantity(original.span, Kind.LENGTH))
    assert window.calculate() and window.report.ok
    window.seismic_group.setChecked(False)
    assert window.project_from_form().moment_connection.seismic is None


def test_rbs_cut_in_3d_and_drawing(tmp_path):
    pytest.importorskip("OCP")
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    from openconex.drawing.moment import moment_layout, write_moment_dxf
    from openconex.geometry3d.base_plate import write_step
    from openconex.geometry3d.moment import moment_parts
    project = load_project(EXAMPLES / "moment_seismic_rbs.ocnx")
    mc = project.moment_model()
    assert inch(moment_layout(mc).beam_length) >= 5 + 18
    beam = next(p for p in moment_parts(mc) if p.name == "beam")
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(beam.shape, props)
    assert props.Mass() > 0
    # removed volume: 4 circular segments of chord b = 18 and sagitta c = 2 in., through t_f
    R = (4 * 2.0**2 + 18.0**2) / (8 * 2.0)
    half = math.asin(9.0 / R)
    segment = R * R * (half - math.sin(half) * math.cos(half))
    length = inch(moment_layout(mc).beam_length)
    solid_in3 = props.Mass() / 25.4**3
    gross = length * (2 * 8.99 * 0.68 + (23.9 - 2 * 0.68) * 0.44)
    assert gross - solid_in3 == pytest.approx(4 * segment * 0.68, rel=0.02)
    assert write_step(moment_parts(mc), tmp_path / "rbs.step").stat().st_size > 0
    path = write_moment_dxf(mc, tmp_path / "rbs.dxf", project.info.unit_system(), "es")
    assert "RBS: a = " in path.read_text(encoding="utf-8")
