# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""HTML report: self-contained file with MathML equations (no internet needed)."""

from __future__ import annotations

from functools import cache
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape
from latex2mathml.converter import convert
from markupsafe import Markup, escape

from openconex.i18n import tr
from openconex.report.builder import Report

__all__ = ["latex_to_mathml", "render_html", "write_html"]


@cache
def _env() -> Environment:
    return Environment(loader=PackageLoader("openconex.report", "templates"),
                       autoescape=select_autoescape(["html", "j2"]), trim_blocks=True,
                       lstrip_blocks=True)


def latex_to_mathml(latex: str) -> Markup:
    """Inline MathML for a LaTeX fragment; falls back to escaped text."""
    if not latex:
        return Markup("")
    try:
        return Markup(convert(latex))
    except Exception:
        return Markup(f"<code>{escape(latex)}</code>")


def render_html(report: Report) -> str:
    template = _env().get_template("report.html.j2")
    return template.render(r=report, t=lambda key, **kw: tr(key, report.language, **kw),
                           math=latex_to_mathml)


def write_html(report: Report, path: str | Path) -> Path:
    path = Path(path)
    path.write_text(render_html(report), encoding="utf-8")
    return path
