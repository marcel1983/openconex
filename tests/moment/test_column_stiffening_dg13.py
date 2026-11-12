# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Column stiffening against AISC Design Guide 13 (1999, rev. 2003), Example 6-3.

W18x50 beam directly welded to a W14x53 column (F_y = 50 ksi), M_u = 250 ft-kips,
P_u = 300 kips in the column, story shear neglected; A36 stiffeners and doubler
plate, E70 electrodes. Partial-depth stiffeners PL 3/8 x 3 x 0'-6 1/2 with a 3/4 in.
corner clip. LRFD, kips.
"""

import dataclasses

import pytest

from openconex.connections.moment.fr_moment import (
    FlangeDetail,
    MomentConnection,
    WebPlate,
    check_moment_connection,
)
from openconex.core.loads import Method
from openconex.core.model import BoltSpec
from openconex.core.shapes import aisc_shapes
from openconex.units import Kind, from_internal, to_internal


def inch(v):
    return to_internal(v, "in", Kind.LENGTH)


def kip(v):
    return from_internal(v, Kind.FORCE, "kip")


def ksi(v):
    return to_internal(v, "ksi", Kind.STRESS)


BEAM = aisc_shapes().get("W18X50")
WEB = WebPlate(bolt=BoltSpec(diameter=inch(0.875)), rows=3, spacing=inch(3), length=inch(9),
               thickness=inch(0.375), lev=inch(1.5), leh=inch(2), weld=inch(0.25),
               Fy=ksi(50), Fu=ksi(65))
BASE = MomentConnection(
    detail=FlangeDetail.WELDED_FLANGE, beam=BEAM.to_ishape("ASTM A992"), beam_Sx=BEAM["Sx"],
    column=aisc_shapes().get("W14X53").to_ishape("ASTM A992"), web=WEB, plate_Fy=ksi(36),
    plate_Fu=ksi(58), continuity_plate=inch(0.375), continuity_plate_width=inch(3),
    continuity_plate_full_depth=False, continuity_plate_length=inch(6.5),
    continuity_plate_weld=inch(0.25), panel_zone=True)
# Solution A: PL 5/8 doubler, fillet welded (5/8 in. bevel) with 1/4 in. welds; 1/4 in. welds
# of the stiffeners to the web and doubler
SOLUTION_A = dataclasses.replace(BASE, doubler_plate=inch(0.625), doubler_weld=inch(0.25),
                                 continuity_plate_web_weld=inch(0.25))
# Solution B: PL 1/4 doubler with CJP welds; 3/16 in. welds of the stiffeners to the web
SOLUTION_B = dataclasses.replace(BASE, doubler_plate=inch(0.25),
                                 continuity_plate_web_weld=inch(3 / 16))
M = to_internal(250, "kip*ft", Kind.MOMENT)


def results(mc):
    return {r.id: r for r in check_moment_connection(
        mc, to_internal(30, "kip", Kind.FORCE), M, Method.LRFD, column_shear=0.0,
        column_axial=to_internal(300, "kip", Kind.FORCE))}


def steps(result):
    return {s.symbol: s.value for s in result.steps}


def test_solution_a():
    r = results(SOLUTION_A)
    # local limit states are taken by the stiffeners; R_ust = 172 - 123 = 49 kips
    assert not r["moment.column_flange_local_bending"].applicable
    force = r["moment.continuity_plates"]
    # P_uf = 250(12)/(17.99 - 0.570) = 172.2 kips; the Guide rounds R_ust to 49 kips
    assert kip(force.demand) == pytest.approx(49, abs=1.0)
    # A_st = 2(3/8)(3 - 3/4) = 1.69 in.^2 > A_st,min = 49/(0.9 x 36) = 1.51 in.^2
    assert kip(force.capacity) == pytest.approx(0.9 * 36 * 1.6875, rel=1e-3)
    assert kip(force.demand) / (0.9 * 36) == pytest.approx(1.51, abs=0.03)
    width = r["moment.continuity_plate_width"]
    assert from_internal(width.demand, Kind.LENGTH, "in") == pytest.approx(2.31, abs=0.006)
    thickness = r["moment.continuity_plate_thickness"]
    assert from_internal(thickness.demand, Kind.LENGTH, "in") == pytest.approx(0.285, abs=0.001)
    # the 16th ed. database gives d = 13.9 in. for the W14x53 (13.92 in. in the Guide)
    length = r["moment.continuity_plate_length"]
    assert from_internal(length.demand, Kind.LENGTH, "in") == pytest.approx(6.30, abs=0.015)
    # l_min = 49/(0.9 x 0.6 x 36 x 3/8 x 2) + 3/4 = 4.11 in.
    # (lengths with the published R_ust = 49 kips)
    shear = r["moment.continuity_plate_shear"]
    per_inch = kip(shear.capacity) / (6.5 - 0.75)
    assert 49 / per_inch + 0.75 == pytest.approx(4.11, abs=0.01)
    # w_min = 0.943(36)(3/8)/70 = 0.182 in.
    weld = r["moment.continuity_plate_flange_weld"]
    assert weld.ratio * 0.25 == pytest.approx(0.182, abs=0.001)
    # l_min = 49/(0.75 x 0.6 x 70 x 1/4 x 2 x sqrt 2) + 3/4 = 2.95 in.
    web_weld = r["moment.continuity_plate_web_weld"]
    per_inch = kip(web_weld.capacity) / (6.5 - 0.75)
    assert 49 / per_inch + 0.75 == pytest.approx(2.95, abs=0.01)
    # the 0.370 in. column web governs over the 5/8 in. A36 doubler. The Guide writes
    # l_min = 49/[4(0.9 x 0.6 x 50 x 0.370)] + 3/4 = 1.23 in., but 1.23 in. omits the clip
    # (1.98 in. with it; Solution B adds it: 3.27 in.)
    web = r["moment.continuity_plate_web_shear"]
    per_inch = kip(web.capacity) / (6.5 - 0.75)
    assert 49 / per_inch == pytest.approx(1.23, abs=0.01)
    # doubler: t_min = h sqrt(F_y)/418 = 0.181 in.; V_udp = 172 - 139 = 33 kips,
    # t_eff = 0.122 in. and w_min = max(0.107, 0.122 sqrt 2) = 0.172 in.
    buckling = r["moment.doubler_plate_buckling"]
    assert from_internal(buckling.demand, Kind.LENGTH, "in") == pytest.approx(0.181, abs=0.001)
    doubler_weld = steps(r["moment.doubler_plate_weld"])
    assert kip(doubler_weld["V_{udp}"]) == pytest.approx(33, abs=1.0)
    assert from_internal(doubler_weld["t_{eff}"], Kind.LENGTH, "in") == pytest.approx(
        0.122, abs=0.002)
    assert from_internal(r["moment.doubler_plate_weld"].demand, Kind.LENGTH,
                         "in") == pytest.approx(0.172, abs=0.003)
    # panel zone with the doubler: 0.9 x 0.6 x 13.92 (50 x 0.370 + 36 x 0.625) = 308 kips
    panel = r["moment.column_panel_zone"]
    assert kip(panel.demand) == pytest.approx(172, abs=0.5)
    assert kip(panel.capacity) == pytest.approx(0.9 * 0.6 * 13.9 * (50 * 0.37 + 36 * 0.625),
                                                rel=5e-3)
    assert all(v.ratio <= 1 for v in r.values() if v.applicable)


def test_solution_b():
    r = results(SOLUTION_B)
    # the 1/4 in. A36 doubler governs over the column web: l_min = 3.27 in.
    web = r["moment.continuity_plate_web_shear"]
    per_inch = kip(web.capacity) / (6.5 - 0.75)
    assert 49 / per_inch + 0.75 == pytest.approx(3.27, abs=0.01)
    # 3/16 in. welds to the web: l_min = 3.68 in.
    web_weld = r["moment.continuity_plate_web_weld"]
    per_inch = kip(web_weld.capacity) / (6.5 - 0.75)
    assert 49 / per_inch + 0.75 == pytest.approx(3.68, abs=0.01)
    assert "moment.doubler_plate_weld" not in r  # CJP
    assert all(v.ratio <= 1 for v in r.values() if v.applicable)


def test_unreinforced_column_example_6_1():
    """Example 6-1: φR_v = 139 kips < V_u = 172 kips; φR_n = 123 kips (flange bending)."""
    r = results(dataclasses.replace(BASE, continuity_plate=0.0))
    assert kip(r["moment.column_panel_zone"].capacity) == pytest.approx(139, abs=0.5)
    assert kip(r["moment.column_flange_local_bending"].capacity) == pytest.approx(123, abs=0.5)
    assert r["moment.column_panel_zone"].ratio > 1


def test_full_depth_stiffeners_add_both_ends():
    """Eq. 4.3-5: with beams on both flanges, (R_ust)1 + (R_ust)2 and l - 2 clip."""
    mc = dataclasses.replace(SOLUTION_A, continuity_plate_full_depth=True,
                             continuity_plate_length=0.0, two_sided=True)
    r = results(mc)
    shear = r["moment.continuity_plate_shear"]
    assert kip(shear.demand) == pytest.approx(2 * kip(r["moment.continuity_plates"].demand))
    clear = 13.9 - 2 * 0.66
    assert kip(shear.capacity) == pytest.approx(0.9 * 0.6 * 36 * (clear - 1.5) * 2 * 0.375,
                                                rel=5e-3)
    assert "moment.continuity_plate_length" not in r


def test_project_example_report_3d_and_window(tmp_path):
    import os
    from pathlib import Path

    from openconex.io.project import load_project
    from openconex.report.builder import build_report
    path = Path(__file__).parents[2] / "examples" / "moment_welded_flange_stiffened.ocnx"
    project = load_project(path)
    report = build_report(project)
    assert report.ok and report.case_headers[-2:] == ["V_c", "P_c"]
    ids = {r.id for r in report.results if r.applicable}
    assert {"moment.continuity_plate_web_weld", "moment.doubler_plate_weld",
            "moment.column_panel_zone"} <= ids
    try:
        from openconex.geometry3d.moment import moment_parts
        names = {p.name for p in moment_parts(project.moment_model())}
        assert {"doubler_plate", "continuity_plate1a", "continuity_plate2b"} <= names
    except ImportError:
        pass
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from openconex.gui.moment import MomentWindow
    QApplication.instance() or QApplication([])
    window = MomentWindow(project, path)
    again = window.project_from_form()
    assert again.moment_connection == project.moment_connection
    assert again.cases == project.cases
    assert window.calculate() and window.report.ok
