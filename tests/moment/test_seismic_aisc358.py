# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Prequalified seismic moment connections (AISC 358-22, AISC 341-22).

No published AISC Seismic Design Manual example is transcribed yet; the values below
are independent hand calculations, in kip and inch, from the AISC Shapes Database
dimensions and the equations of AISC 358-22 (§2.4.3, §5.8, §6.8, §7.6) and AISC 341-22
(§E3.4a, §E3.6e, §E3.6f). They check the implementation of the equations, not the
equations themselves (see docs/tecnico/07-validacion.md).
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


def _hinge(Zx_e, Sh, span, w=2.0 / 12, Ry=1.1, Fy=50.0, Fu=65.0):
    cpr = min((Fy + Fu) / (2 * Fy), 1.2)
    mpr = cpr * Ry * Fy * Zx_e
    lh = span - 2 * Sh
    vu = 2 * mpr / lh + w * lh / 2
    return mpr, vu, mpr + vu * Sh


def test_rbs_hand_calculation():
    """W24X76 beam (d 23.9, bf 8.99, tf 0.68, Zx 200), a = 5, b = 18, c = 2 in., 26 ft."""
    r = seismic(load_project(EXAMPLES / "moment_seismic_rbs.ocnx"))
    zrbs = 200.0 - 2 * 2.0 * 0.68 * (23.9 - 0.68)
    mpr, vu, mf = _hinge(zrbs, 5 + 18 / 2, 26 * 12)
    face = r["seismic.rbs_moment_at_face"]
    assert kip_in(face.demand) == pytest.approx(mf, rel=2e-3)
    assert kip_in(face.capacity) == pytest.approx(1.1 * 50 * 200, rel=2e-3)
    assert kip(r["seismic.beam_shear"].demand) == pytest.approx(vu, rel=2e-3)
    # φv Vn = 1.0 (0.6)(50)(23.9)(0.44)
    assert kip(r["seismic.beam_shear"].capacity) == pytest.approx(0.6 * 50 * 23.9 * 0.44,
                                                                  rel=2e-3)
    # a within 0.5bf..0.75bf, governed by the lower bound 4.495/5
    assert r["seismic.rbs_a"].ratio == pytest.approx(0.5 * 8.99 / 5.0, rel=1e-3)
    # column-beam ratio with W14X257 above and below, P_uc = 400 kip, two beams
    mpc = 2 * 487.0 * (50 - 400 / 75.6)
    mpb = 2 * (mpr + vu * (14 + 16.4 / 2))
    ratio = r["seismic.column_beam_ratio"]
    assert kip_in(ratio.capacity) == pytest.approx(mpc, rel=3e-3)
    assert kip_in(ratio.demand) == pytest.approx(mpb, rel=3e-3)
    # continuity plates: 0.4 sqrt(1.8 bf tf) with equal RyFy, and bf/6
    need = max(0.4 * math.sqrt(1.8 * 8.99 * 0.68), 8.99 / 6)
    assert inch(r["seismic.continuity_plates"].demand) == pytest.approx(need, rel=2e-3)
    # panel zone thickness (dz + wz)/90
    pz = r["seismic.panel_zone_thickness"]
    assert inch(pz.demand) == pytest.approx((23.9 - 2 * 0.68 + 16.4 - 2 * 1.89) / 90,
                                            rel=2e-3)


def test_wuf_w_hinge_at_the_column_face():
    """W24X62 (Zx 153): S_h = 0, M_f = M_pr = 1.15 (1.1)(50)(153)."""
    r = seismic(load_project(EXAMPLES / "moment_seismic_wuf_w.ocnx"))
    _, vu, _ = _hinge(153.0, 0.0, 26 * 12)
    assert kip(r["seismic.beam_shear"].demand) == pytest.approx(vu, rel=2e-3)
    assert "seismic.rbs_moment_at_face" not in r
    assert r["seismic.beam_weight"].ratio == pytest.approx(62 / 150, rel=1e-3)
    assert r["seismic.beam_flange_thickness"].ratio == pytest.approx(0.59, rel=1e-3)


def test_bfp_hand_calculation():
    """W24X76, PL 1-1/4 x 11, 7 rows of 7/8 in. A490-X at 3 in., S_1 = 2.5 in., 28 ft."""
    r = seismic(load_project(EXAMPLES / "moment_seismic_bfp.ocnx"))
    sh = 2.5 + 3 * (7 - 1)
    _, _, mf = _hinge(200.0, sh, 28 * 12)
    fpr = mf / (23.9 + 1.25)
    dmax = 8.99 / 2 * (1 - 1.1 * 50 / (1.1 * 65)) - 0.125
    assert inch(r["seismic.bfp_bolt_diameter"].capacity) == pytest.approx(dmax, rel=2e-3)
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


def test_bueep_hand_calculation():
    """4E: W24X62, PL 1-1/2 x 10, g 5.5, p_f,i = p_f,o = 2, 1-1/4 in. A490, 26 ft."""
    r = seismic(load_project(EXAMPLES / "moment_seismic_bueep.ocnx"))
    d, bf, tf = 23.7, 7.04, 0.59
    _, vu, mf = _hinge(153.0, min(d / 2, 3 * bf), 26 * 12)
    h0, h1 = d + 2 - tf / 2, d - tf - 2 - tf / 2
    ab = math.pi * 1.25**2 / 4
    rupture = r["seismic.end_plate_bolt_rupture"]
    assert kip_in(rupture.demand) == pytest.approx(mf, rel=2e-3)
    assert kip_in(rupture.capacity) == pytest.approx(0.9 * 2 * 113 * ab * (h0 + h1), rel=2e-3)
    # yield lines of the 4E plate (DG16 Table 4-2) with h to the compression flange face
    bp, g, pf = 10.0, 5.5, 2.0
    s = 0.5 * math.sqrt(bp * g)
    H1, H0 = d - tf - pf, d + pf
    Y = bp / 2 * (H1 * (1 / pf + 1 / s) + H0 / pf - 0.5) + 2 / g * H1 * (pf + s)
    yielding = r["seismic.end_plate_yielding"]
    assert kip_in(yielding.capacity) == pytest.approx(50 * 1.5**2 * Y / 1.11, rel=3e-3)
    ffu = mf / (d - tf)
    assert kip(r["seismic.end_plate_shear_yielding"].demand) == pytest.approx(ffu / 2, rel=2e-3)
    assert kip(r["seismic.end_plate_shear_yielding"].capacity) == pytest.approx(
        0.6 * 50 * bp * 1.5, rel=2e-3)
    bolts = r["seismic.end_plate_compression_bolts"]
    assert kip(bolts.demand) == pytest.approx(vu, rel=2e-3)
    assert kip(bolts.capacity) == pytest.approx(0.9 * 4 * 84 * ab, rel=2e-3)
    assert "seismic.end_plate_stiffener_thickness" not in r


def test_bseep_8es_stiffener():
    """8ES stiffener: t_s ≥ t_bw F_yb/F_ys and h_st/t_s ≤ 0.56 sqrt(E/F_ys)."""
    r = seismic(load_project(EXAMPLES / "moment_seismic_bseep_8es.ocnx"))
    st = r["seismic.end_plate_stiffener_thickness"]
    assert inch(st.demand) == pytest.approx(0.545, rel=2e-3)   # W30X108 t_w
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
    assert expected_ratios("unknown") is None
    assert nominal_depth("W36X150") == 36.0
    r = seismic(project_with("moment_seismic_wuf_w", Ry_beam=1.3))
    base = seismic(load_project(EXAMPLES / "moment_seismic_wuf_w.ocnx"))
    assert r["seismic.beam_shear"].demand > base["seismic.beam_shear"].demand


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
