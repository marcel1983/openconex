# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Generate 3D thumbnails for the connection gallery.

The base-plate thumbnails are used by the application.  The shear thumbnails
are generated into ``docs/verificacion/miniaturas/3d`` for review: the current
3D model represents the support as a thin plate and the connection is partly
hidden, so the gallery keeps the SVG drawings until that model is enriched.

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
     ("beam", "support", "column", "pedestal", "foundation"), "#1565c0"),
    ("base_plate", "embedded", "base_plate_embedded", 1.3,
     ("embedded_base_plate", "face_plate_front", "face_plate_back"), (), "#ef6c00"),
    ("base_plate", "weak", "base_plate_weak", 1.8, ("base_plate",),
     ("beam", "support", "column", "pedestal", "foundation"), "#1565c0"),
    ("base_plate", "exposed", "family_base_plate", 2.1, ("base_plate",),
     ("beam", "support", "column", "pedestal", "foundation"), "#1565c0"),
)

SHEAR_APP = (
    # family, subtype, asset, margin, explode
    ("shear_column", "double_angle", "shear_double_angle", 2.0, None),
    ("shear_column", "end_plate", "shear_end_plate", 2.0, None),
    ("shear_column", "seated", "shear_seated", 2.8, None),
    ("shear_column", "stiffened_seat", "shear_stiffened_seat", 2.8, None),
    ("shear_column", "skewed_bent_plate", "shear_skewed_bent_plate", 2.0, None),
)

SHEAR_REVIEW = (
    ("shear_column", "single_plate", "shear_single_plate", 2.2,
     {"beam": (120.0, 0.0, 0.0)}),
    ("shear_column", "extended_single_plate", "shear_extended_plate", 2.2,
     {"beam": (120.0, 0.0, 0.0)}),
    ("shear_beam", "single_plate", "shear_beam_single_plate", 2.2,
     {"beam": (120.0, 0.0, 0.0)}),
    ("shear_beam", "double_angle", "shear_beam_double_angle", 2.0, None),
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
    for family, subtype, asset, margin, explode in items:
        project = build_project(family, subtype)
        parts = parts_3d(project)
        names = tuple(part.name for part in parts
                      if part.name not in {"beam", "support"})
        omit = ("support", "top_angle") if subtype in {"seated", "stiffened_seat"} \
            else ("support",)
        pixmap = render_parts(parts, SIZE, margin=margin, highlight=names,
                              highlight_color="#ef6c00", swap_yz=True,
                              omit=omit, explode=explode)
        path = out_dir / f"{asset}.png"
        pixmap.save(str(path), "PNG")
        print(f"wrote {path.relative_to(ROOT)}")


def render_shear(app: QApplication) -> None:
    _render_shear(app, SHEAR_APP, APP_THUMBS)
    _render_shear(app, SHEAR_REVIEW, REVIEW_3D)


def render_comparison() -> None:
    """Write a small HTML contact sheet for the SVG / 3D comparison."""
    rows = [
        ("Placa base expuesta", "base_plate_exposed", True),
        ("Base empotrada Tipo I", "base_plate_embedded", True),
        ("Base débil", "base_plate_weak", True),
        ("Placa simple", "shear_single_plate", False),
        ("Placa extendida", "shear_extended_plate", False),
        ("Doble ángulo", "shear_double_angle", True),
        ("Placa de extremo", "shear_end_plate", True),
        ("Asiento", "shear_seated", True),
        ("Asiento rigidizado", "shear_stiffened_seat", True),
        ("Placa doblada", "shear_skewed_bent_plate", True),
    ]
    cells = []
    for label, asset, packaged in rows:
        svg = f"../../../src/openconex/data/connections/{asset}.svg"
        png = (f"../../../src/openconex/data/connections/thumbs/{asset}.png"
               if packaged else f"3d/{asset}.png")
        cells.append(
            f"<tr><th>{label}</th>"
            f"<td><img src=\"{svg}\" alt=\"{label} SVG\"></td>"
            f"<td><img src=\"{png}\" alt=\"{label} 3D\"></td></tr>")
    html = """<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<title>Miniaturas: SVG frente a 3D</title>
<style>
body { font-family: Segoe UI, Arial, sans-serif; margin: 24px; color: #1f2d3d; }
table { border-collapse: collapse; }
th, td { border-bottom: 1px solid #d6dee8; padding: 10px; text-align: left; }
th { width: 170px; }
img { width: 360px; height: 203px; object-fit: contain; background: #fafafa; }
</style></head><body>
<h1>Miniaturas: SVG frente a captura 3D</h1>
<p>Las capturas 3D de placa base, doble ángulo, placa de extremo, asiento y
placa doblada se usan en la galería. Placa simple y placa extendida quedan en
revisión: el modelo actual oculta la placa entre el alma y el apoyo.</p>
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
