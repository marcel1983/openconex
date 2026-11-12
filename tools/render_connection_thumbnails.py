# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Generate 3D thumbnails for the connection gallery.

The packaged thumbnails live in ``src/openconex/data/connections/thumbs`` and
are used by the gallery before falling back to the SVG.  The shear cards use
an exploded view: the column family adds a short context column and the
beam-to-beam family shows the support web.  The solid model draws the support
as a thin plate, which is hard to read at card size.  The skewed bent plate
stays on SVG because its 3D model is not clear; its review image is generated
into ``docs/verificacion/miniaturas/3d``.

Run with the optional 3D and GUI extras::

    python tools/render_connection_thumbnails.py --set base_plate
    python tools/render_connection_thumbnails.py --set shear
    python tools/render_connection_thumbnails.py --set comparison
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication

from openconex.geometry3d.shear import shear_parts
from openconex.gui.exporting import parts_3d
from openconex.gui.start_data import build_project
from openconex.gui.viewer3d import render_parts

ROOT = Path(__file__).parents[1]
APP_THUMBS = ROOT / "src" / "openconex" / "data" / "connections" / "thumbs"
REVIEW = ROOT / "docs" / "verificacion" / "miniaturas"
REVIEW_3D = REVIEW / "3d"
SIZE = QSize(640, 360)

BASE_PLATE = (
    # family, subtype, asset, margin, highlight, hide, highlight colour
    ("base_plate", "exposed", "base_plate_exposed", 1.8, ("base_plate",),
     ("beam", "support", "column", "pedestal", "foundation"), "#ef6c00"),
    ("base_plate", "embedded", "base_plate_embedded", 1.3,
     ("embedded_base_plate", "face_plate_front", "face_plate_back"), (), "#ef6c00"),
    ("base_plate", "weak", "base_plate_weak", 1.8, ("base_plate",),
     ("beam", "support", "column", "pedestal", "foundation"), "#ef6c00"),
    ("base_plate", "exposed", "family_base_plate", 2.1, ("base_plate",),
     ("beam", "support", "column", "pedestal", "foundation"), "#ef6c00"),
)

SHEAR_APP = (
    # family, subtype, asset, margin, explode, context column
    ("shear_column", "double_angle", "shear_double_angle", 2.2,
     {"beam": (0.0, -250.0, 0.0)}, "column"),
    ("shear_column", "single_plate", "shear_single_plate", 2.0,
     {"beam": (0.0, -200.0, 0.0)}, "column"),
    ("shear_column", "extended_single_plate", "shear_extended_plate", 2.0,
     {"beam": (0.0, -200.0, 0.0)}, "column"),
    ("shear_column", "end_plate", "shear_end_plate", 2.0,
     {"beam": (80.0, -260.0, 0.0), "end_plate": (80.0, 0.0, 0.0)}, "column"),
    ("shear_column", "seated", "shear_seated", 1.4,
     {"beam": (80.0, 0.0, 220.0)}, "column"),
    ("shear_column", "stiffened_seat", "shear_stiffened_seat", 1.4,
     {"beam": (80.0, 0.0, 240.0)}, "column"),
)

SHEAR_BEAM_APP = (
    # Same connection types against a supporting beam web: no column context.
    ("shear_beam", "double_angle", "shear_beam_double_angle", 2.2,
     {"beam": (0.0, -250.0, 0.0)}, None),
    ("shear_beam", "single_plate", "shear_beam_single_plate", 2.0,
     {"beam": (0.0, -200.0, 0.0)}, None),
    ("shear_beam", "extended_single_plate", "shear_beam_extended_single_plate", 2.0,
     {"beam": (0.0, -200.0, 0.0)}, None),
    ("shear_beam", "end_plate", "shear_beam_end_plate", 2.0,
     {"beam": (80.0, -260.0, 0.0), "end_plate": (80.0, 0.0, 0.0)}, None),
    ("shear_beam", "seated", "shear_beam_seated", 1.4,
     {"beam": (80.0, 0.0, 220.0)}, None),
    ("shear_beam", "stiffened_seat", "shear_beam_stiffened_seat", 1.4,
     {"beam": (80.0, 0.0, 240.0)}, None),
)

FAMILY_SHEAR = (
    ("shear_column", "double_angle", "family_shear_column", 2.4,
     {"beam": (0.0, -250.0, 0.0)}, "column"),
    ("shear_beam", "double_angle", "family_shear_beam", 2.4,
     {"beam": (0.0, -250.0, 0.0)}, None),
)

SHEAR_REVIEW = (
    ("shear_column", "skewed_bent_plate", "shear_skewed_bent_plate", 2.0,
     None, None),
)


def _highlight(parts, names: tuple[str, ...]) -> tuple[str, ...]:
    wanted = set(names)
    return tuple(part.name for part in parts if part.name in wanted)


def render_base_plates(app: QApplication) -> None:
    APP_THUMBS.mkdir(parents=True, exist_ok=True)
    for family, subtype, asset, margin, highlight, hide, colour in BASE_PLATE:
        project = build_project(family, subtype)
        parts = parts_3d(project)
        pixmap = render_parts(parts, SIZE, margin=margin, hide=hide,
                              highlight=_highlight(parts, highlight),
                              highlight_color=colour)
        path = APP_THUMBS / f"{asset}.png"
        pixmap.save(str(path), "PNG")
        print(f"wrote {path.relative_to(ROOT)}")


def _render_shear(app: QApplication, items, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for family, subtype, asset, margin, explode, context in items:
        project = build_project(family, subtype)
        parts = shear_parts(project.shear_model(), context=context)
        if context:
            # The context column replaces the thin support plate in the
            # thumbnails; keeping both makes their coplanar faces flicker.
            parts = [part for part in parts if part.name != "support"]
        names = tuple(part.name for part in parts
                      if part.name not in {"beam", "support", "support_context"})
        moves = dict(explode or {})
        if subtype == "end_plate":
            shift = moves.get("end_plate", (0.0, 0.0, 0.0))[0]
            for part in parts:
                if part.name.startswith("support_bolt"):
                    moves[part.name] = (shift, 0.0, 0.0)
        pixmap = render_parts(parts, SIZE, margin=margin, highlight=names,
                              highlight_color="#ef6c00", swap_yz=True,
                              explode=moves or None)
        path = out_dir / f"{asset}.png"
        pixmap.save(str(path), "PNG")
        print(f"wrote {path.relative_to(ROOT)}")


def render_shear(app: QApplication) -> None:
    _render_shear(app, SHEAR_APP, APP_THUMBS)
    _render_shear(app, SHEAR_BEAM_APP, APP_THUMBS)
    _render_shear(app, FAMILY_SHEAR, APP_THUMBS)
    _render_shear(app, SHEAR_REVIEW, REVIEW_3D)


def render_comparison() -> None:
    """Write a small HTML contact sheet for the SVG / 3D comparison."""
    rows = [
        # label, asset, packaged, SVG reference (None: no own SVG yet)
        ("Placa base expuesta", "base_plate_exposed", True, None),
        ("Base empotrada Tipo I", "base_plate_embedded", True, None),
        ("Base débil", "base_plate_weak", True, None),
        ("Placa simple", "shear_single_plate", True, None),
        ("Placa extendida", "shear_extended_plate", True, None),
        ("Doble ángulo", "shear_double_angle", True, None),
        ("Placa de extremo", "shear_end_plate", True, None),
        ("Asiento", "shear_seated", True, None),
        ("Asiento rigidizado", "shear_stiffened_seat", True, None),
        ("Viga-viga, placa simple", "shear_beam_single_plate", True, False),
        ("Viga-viga, placa extendida", "shear_beam_extended_single_plate", True, False),
        ("Viga-viga, doble ángulo", "shear_beam_double_angle", True, False),
        ("Viga-viga, placa de extremo", "shear_beam_end_plate", True, False),
        ("Viga-viga, asiento", "shear_beam_seated", True, False),
        ("Viga-viga, asiento rigidizado", "shear_beam_stiffened_seat", True, False),
        ("Placa doblada", "shear_skewed_bent_plate", False, "shear_skewed_bent_plate"),
    ]
    cells = []
    for label, asset, packaged, svg_asset in rows:
        if svg_asset is False:
            svg_cell = '<span class="none">Sin SVG propio</span>'
        else:
            reference = svg_asset or asset
            svg = f"../../../src/openconex/data/connections/{reference}.svg"
            svg_cell = f'<img src="{svg}" alt="{label} SVG">'
        png = (f"../../../src/openconex/data/connections/thumbs/{asset}.png"
               if packaged else f"3d/{asset}.png")
        cells.append(
            f"<tr><th>{label}</th>"
            f"<td>{svg_cell}</td>"
            f"<td><img src=\"{png}\" alt=\"{label} 3D\"></td></tr>")
    html = """<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<title>Miniaturas: SVG frente a ilustración 3D</title>
<style>
body { font-family: Segoe UI, Arial, sans-serif; margin: 24px; color: #1f2d3d; }
table { border-collapse: collapse; }
th, td { border-bottom: 1px solid #d6dee8; padding: 10px; text-align: left; }
th { width: 170px; }
img { width: 360px; height: 203px; object-fit: contain; background: #fafafa; }
.none { color: #90a4ae; font-style: italic; }
</style></head><body>
<h1>Miniaturas: SVG frente a ilustración 3D</h1>
<p>Las ilustraciones 3D de placa base y de las conexiones de corte se usan en la
galería, con vista explosionada para separar la viga y dejar visible la placa,
el asiento o los ángulos. Las tarjetas viga-columna añaden una columna de
contexto; las viga-viga muestran el alma del apoyo. La placa doblada queda en
revisión: el modelo actual no representa con claridad el apoyo en esviaje, así
que la galería mantiene su isométrico SVG.</p>
<table><thead><tr><th>Tipo</th><th>SVG</th><th>3D</th></tr></thead>
<tbody>""" + "\n".join(cells) + """</tbody></table>
</body></html>
"""
    REVIEW.mkdir(parents=True, exist_ok=True)
    path = REVIEW / "comparacion.html"
    path.write_text(html, encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--set", choices=("base_plate", "shear", "comparison", "all"),
                        default="base_plate")
    args = parser.parse_args()
    app = QApplication([])
    if args.set in {"base_plate", "all"}:
        render_base_plates(app)
    if args.set in {"shear", "all"}:
        render_shear(app)
    if args.set in {"comparison", "all"}:
        render_comparison()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
