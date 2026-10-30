# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
import datetime as dt

import pytest
from docx import Document

from openconex.report.builder import build_base_plate_report
from openconex.report.docx import latex_to_text, write_docx
from openconex.report.html import latex_to_mathml, render_html
from openconex.report.pdf import pdf_available, write_pdf

TODAY = dt.date(2026, 10, 30)


def test_report_content(project):
    r = build_base_plate_report(project, TODAY)
    assert r.ok
    assert len(r.summary) == len(r.checks) == 7
    assert {b.check_id for b in r.checks} >= {"base_plate.bearing", "anchor.steel_tension"}
    assert all(b.lines for b in r.checks)
    worst = max(r.checks, key=lambda b: b.ratio)
    assert worst.ratio == pytest.approx(0.976, abs=0.001)


@pytest.mark.parametrize(("lang", "title", "status"), [("es", "Memoria de cálculo", "Cumple"),
                                                       ("en", "Design calculation report", "OK")])
def test_html_language(project, lang, title, status):
    project.info.language = lang
    html = render_html(build_base_plate_report(project, TODAY))
    assert f"<title>{title}" in html
    assert f">{status}<" in html
    assert "<math" in html  # equations rendered as MathML, no internet needed
    assert "2026-10-30" in html


def test_units_follow_project(project):
    project.info.units = "SI_kN_m"
    html = render_html(build_base_plate_report(project, TODAY))
    assert "kN" in html and "kip" not in html


def test_report_flags_failures(project):
    project.base_plate.tp = "1 in"
    r = build_base_plate_report(project, TODAY)
    assert not r.ok
    assert any(row.status == "ng" for row in r.summary)


def test_latex_helpers():
    assert latex_to_text(r"\phi R_n = \frac{a}{b}") == "φ R_n = (a)/(b)"
    assert latex_to_text(r"\sqrt{\frac{4 T_u b'}{\phi p F_u}}") == "√((4 T_u b')/(φ p F_u))"
    assert latex_to_text(r"M_{pl} \le 1.7 f'_c") == "M_pl ≤ 1.7 f'_c"
    assert str(latex_to_mathml("")) == ""
    assert "<math" in str(latex_to_mathml(r"\frac{1}{2}"))


def test_docx(tmp_path, project):
    path = write_docx(build_base_plate_report(project, TODAY), tmp_path / "r.docx")
    doc = Document(str(path))
    headings = [p.text for p in doc.paragraphs if p.style.name.startswith("Heading")]
    assert any(h.startswith("5. Verificaciones") for h in headings)
    assert len(doc.tables) >= 5 + 7


@pytest.mark.skipif(not pdf_available(), reason="Qt WebEngine not installed (openconex[pdf])")
def test_pdf(tmp_path, project):
    path = write_pdf(build_base_plate_report(project, TODAY), tmp_path / "r.pdf")
    data = path.read_bytes()
    assert data.startswith(b"%PDF") and data.count(b"/Type /Page") >= 3
