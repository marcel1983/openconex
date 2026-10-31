# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""DXF figures for a Type I embedded base (DG1 Chapter 5)."""

from __future__ import annotations

from pathlib import Path

from openconex.connections.base_plate.check import BasePlate
from openconex.drawing.base_plate import BasePlateDrawing, _i_shape, _Sheet
from openconex.i18n import tr
from openconex.units import UnitSystem

__all__ = ["embedded_base_dxf", "write_embedded_base_dxf"]


def _plan(s: _Sheet, bp: BasePlate, fw: float, fl: float, h: float, lang: str) -> float:
    col = bp.column
    d, bf, tf, tw = s.u(col.d), s.u(col.bf), s.u(col.tf), s.u(col.tw)
    s.rect(-fw / 2, -fl / 2, fw / 2, fl / 2, "BP-CONCRETO")
    _i_shape(s, d, bf, tf, tw, 0, 0, "BP-COLUMNA")
    x0, x1 = -d / 2 + tf, d / 2 - tf
    s.rect(x0, tw / 2, x1, bf / 2, "BP-PLACA")
    s.rect(x0, -bf / 2, x1, -tw / 2, "BP-PLACA")
    top = fl / 2
    s.hdim(-fw / 2, fw / 2, -fl / 2, -top - 6 * h)
    s.vdim(-fl / 2, fl / 2, -fw / 2, -fw / 2 - 6 * h)
    s.hdim(-d / 2, d / 2, bf / 2, top + 3 * h)
    s.text(tr("drawing.plan", lang), -fw / 2, -top - 10 * h, 1.4 * h)
    s.text(f"{col.name} — {tr('drawing.column', lang)}", -fw / 2, -top - 12 * h)
    return -top - 14 * h


def _elevation(s: _Sheet, bp: BasePlate, fw: float, emb: float, depth: float, h: float,
               lang: str, y0: float) -> None:
    col = bp.column
    d, tf = s.u(col.d), s.u(col.tf)
    stub = s.u(col.d) * 1.2
    tp = s.u(bp.embedded_base.face_plate_thickness)
    top = y0
    s.rect(-fw / 2, top - depth, fw / 2, top, "BP-CONCRETO")
    s.rect(-d / 2, top - emb, d / 2, top + stub, "BP-COLUMNA")
    # The face bearing plates sit on the top of the foundation, not at the
    # bottom of the embedment (DG1 Figure 5-1 and Section 5.3).
    s.rect(-d / 2 + tf, top, d / 2 - tf, top + tp, "BP-PLACA")
    s.msp.add_line((-fw / 2, top), (fw / 2, top),
                   dxfattribs={"layer": "BP-CONCRETO"})
    s.hdim(-fw / 2, fw / 2, top - depth, top - depth - 5 * h)
    s.vdim(top - emb, top, -fw / 2, -fw / 2 - 6 * h)
    s.text(tr("drawing.elevation", lang), -fw / 2, top - depth - 10 * h, 1.4 * h)
    s.text(f"{col.name} — {tr('drawing.column', lang)}", -fw / 2, top - depth - 12 * h)


def embedded_base_dxf(bp: BasePlate, units: UnitSystem, lang: str = "es",
                      options: BasePlateDrawing | None = None, view: str = "all"):
    """Build the embedded-base DXF. ``view`` is ``all``, ``plan`` or ``elevation``."""
    embedded = bp.embedded_base
    opt = options or BasePlateDrawing()
    s = _Sheet(units, lang)
    fw = s.u(embedded.foundation_width)
    fl = s.u(opt.pedestal_B) if opt.pedestal_B else fw
    s.setup_dims(max(fw, fl) / 40)
    h = s.text_h
    emb = s.u(embedded.embedment)
    depth = emb + max(12 * h, s.u(304.8))
    if view == "all":
        bottom = _plan(s, bp, fw, fl, h, lang)
        _elevation(s, bp, fw, emb, depth, h, lang, bottom - 8 * h)
    elif view == "plan":
        _plan(s, bp, fw, fl, h, lang)
    elif view == "elevation":
        _elevation(s, bp, fw, emb, depth, h, lang, 0.0)
    else:
        raise ValueError("view must be 'all', 'plan' or 'elevation'")
    return s.doc


def write_embedded_base_dxf(bp: BasePlate, path: str | Path, units: UnitSystem,
                            lang: str = "es", options: BasePlateDrawing | None = None,
                            view: str = "all") -> Path:
    doc = embedded_base_dxf(bp, units, lang, options, view)
    path = Path(path)
    doc.saveas(path)
    return path
