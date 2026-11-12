# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Generate the isometric line art used by the connection gallery.

The drawings are deliberately schematic: they show the members and highlight the
connection, not fabrication details.  Run from the repository root::

    python tools/make_connection_art.py
"""

from __future__ import annotations

import math
from pathlib import Path

ROOT = Path(__file__).parents[1]
OUT = ROOT / "src" / "openconex" / "data" / "connections"

W, H = 320, 220
CX, CY = 160, 170
COS30 = math.cos(math.radians(30))
SIN30 = 0.5

STEEL = ("#d9e2ec", "#607d8b")
STEEL_DARK = ("#b0bec5", "#546e7a")
CONNECTION = ("#bbdefb", "#1565c0")
BOLT = "#0d47a1"
CONCRETE = ("#e0d6cc", "#8d6e63")
WELD = "#ef6c00"
FUTURE = ("#eeeeee", "#9e9e9e")


def iso(x: float, y: float, z: float) -> tuple[float, float]:
    return CX + (x - y) * COS30, CY + (x + y) * SIN30 - z


def _poly(points: list[tuple[float, float]]) -> str:
    return " ".join(f"{x:.2f},{y:.2f}" for x, y in points)


class Scene:
    def __init__(self) -> None:
        self.parts: list[str] = []
        self._bounds: list[tuple[float, float]] = []

    def _track(self, points: list[tuple[float, float]]) -> None:
        self._bounds.extend(points)

    def polygon(self, points: list[tuple[float, float]], fill: str, stroke: str,
                width: float = 1.6, opacity: float = 1.0) -> None:
        self._track(points)
        self.parts.append(
            f'<polygon points="{_poly(points)}" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="{width}" opacity="{opacity}" stroke-linejoin="round"/>')

    def line(self, a: tuple[float, float], b: tuple[float, float], stroke: str,
             width: float = 1.6, dash: str | None = None) -> None:
        self._track([a, b])
        extra = f' stroke-dasharray="{dash}"' if dash else ""
        self.parts.append(
            f'<line x1="{a[0]:.2f}" y1="{a[1]:.2f}" x2="{b[0]:.2f}" y2="{b[1]:.2f}" '
            f'stroke="{stroke}" stroke-width="{width}"{extra} stroke-linecap="round"/>')

    def circle(self, point: tuple[float, float], radius: float, fill: str,
               stroke: str = "#263238", width: float = 1.0) -> None:
        self._track([(point[0] - radius, point[1] - radius),
                     (point[0] + radius, point[1] + radius)])
        self.parts.append(
            f'<circle cx="{point[0]:.2f}" cy="{point[1]:.2f}" r="{radius:.2f}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>')

    def text(self, point: tuple[float, float], text: str, color: str = "#455a64",
             size: int = 10, anchor: str = "start") -> None:
        width = len(text) * size * 0.58
        left = point[0] - width / 2 if anchor == "middle" else point[0]
        self._track([(left, point[1] - size), (left + width, point[1] + size * 0.3)])
        self.parts.append(
            f'<text x="{point[0]:.2f}" y="{point[1]:.2f}" fill="{color}" '
            f'font-family="Segoe UI, Arial, sans-serif" font-size="{size}" '
            f'text-anchor="{anchor}">{text}</text>')

    def render(self) -> str:
        if not self._bounds:
            return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
                    f'viewBox="0 0 {W} {H}"></svg>\n')
        xs = [x for x, _ in self._bounds]
        ys = [y for _, y in self._bounds]
        margin = 16
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        width = max(max_x - min_x, 1.0)
        height = max(max_y - min_y, 1.0)
        scale = min((W - 2 * margin) / width, (H - 2 * margin) / height)
        tx = (W - width * scale) / 2 - min_x * scale
        ty = (H - height * scale) / 2 - min_y * scale
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
            f'viewBox="0 0 {W} {H}">\n'
            f'<g transform="translate({tx:.2f},{ty:.2f}) scale({scale:.4f})">\n'
            + "\n".join(self.parts)
            + "\n</g>\n</svg>\n")


def box(scene: Scene, x: float, y: float, z: float, dx: float, dy: float, dz: float,
        colors: tuple[str, str] = STEEL, width: float = 1.4) -> None:
    fill, stroke = colors

    def p(a: float, b: float, c: float) -> tuple[float, float]:
        return iso(x + a * dx, y + b * dy, z + c * dz)

    right = [p(1, 0, 0), p(1, 1, 0), p(1, 1, 1), p(1, 0, 1)]
    front = [p(0, 1, 0), p(1, 1, 0), p(1, 1, 1), p(0, 1, 1)]
    top = [p(0, 0, 1), p(1, 0, 1), p(1, 1, 1), p(0, 1, 1)]
    scene.polygon(right, _shade(fill, 0.86), stroke, width)
    scene.polygon(front, fill, stroke, width)
    scene.polygon(top, _shade(fill, 1.08), stroke, width)


def _shade(hex_color: str, factor: float) -> str:
    value = hex_color.lstrip("#")
    r, g, b = (int(value[i:i + 2], 16) for i in (0, 2, 4))
    r, g, b = (max(0, min(255, int(channel * factor))) for channel in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


def bolt(scene: Scene, x: float, y: float, z: float, radius: float = 3.2) -> None:
    scene.circle(iso(x, y, z), radius, BOLT, "#0d47a1", 1.0)


def column(scene: Scene, x: float = 0, y: float = 0, z: float = 0,
           height: float = 170, size: float = 55,
           colors: tuple[str, str] = STEEL) -> None:
    box(scene, x, y, z, size, size, height, colors)


def beam(scene: Scene, x: float, y: float, z: float, length: float = 150,
         depth: float = 45, width: float = 38,
         colors: tuple[str, str] = STEEL) -> None:
    box(scene, x, y, z, length, width, depth, colors)


def base_plate(scene: Scene, *, future: bool = False) -> None:
    steel = FUTURE if future else STEEL
    connection = FUTURE if future else CONNECTION
    box(scene, -28, -28, -28, 118, 118, 28, CONCRETE)
    box(scene, -14, -14, 0, 90, 90, 5, connection)
    column(scene, 0, 0, 5, 120, 55, steel)
    for x, y in ((-7, -7), (57, -7), (-7, 57), (57, 57)):
        bolt(scene, x, y, 7)
    scene.line(iso(-1, -1, 5), iso(56, -1, 5), WELD, 2.2)
    scene.line(iso(-1, 56, 5), iso(56, 56, 5), WELD, 2.2)
    if future:
        scene.text((160, 205), "PRÓXIMAMENTE", "#9e9e9e", 9, "middle")


def base_embedded(scene: Scene) -> None:
    box(scene, -25, -25, -25, 105, 105, 25, CONCRETE)
    column(scene, 0, 0, 0, 120, 55, STEEL)
    box(scene, -12, -12, -25, 80, 80, 25, CONNECTION)
    for x, y in ((-5, -5), (55, -5), (-5, 55), (55, 55)):
        bolt(scene, x, y, -3)
    scene.line(iso(55, 0, -25), iso(55, 0, 0), WELD, 2.0)
    scene.line(iso(0, 55, -25), iso(0, 55, 0), WELD, 2.0)


def base_weak(scene: Scene) -> None:
    base_plate(scene)
    # Reduced anchor sections highlighted near the plate corners.
    for x, y in ((-7, -7), (57, -7), (-7, 57), (57, 57)):
        scene.line(iso(x, y, 0), iso(x, y, 28), "#ef6c00", 3.0)


def shear_column_base(scene: Scene) -> None:
    column(scene, 0, 0, 0, 180, 55)
    beam(scene, 55, 10, 100, 150, 45, 38)
    box(scene, 55, 10, 95, 6, 45, 60, CONNECTION)
    for z in (105, 125, 145):
        for y in (20, 45):
            bolt(scene, 62, y, z)
    scene.line(iso(61, 10, 100), iso(61, 10, 150), WELD, 2.0)


def shear_single_plate(scene: Scene) -> None:
    shear_column_base(scene)


def shear_extended_plate(scene: Scene) -> None:
    column(scene, 0, 0, 0, 190, 55)
    beam(scene, 55, 10, 105, 150, 45, 38)
    box(scene, 55, 10, 90, 6, 45, 78, CONNECTION)
    for z in (100, 120, 140, 160):
        for y in (17, 35, 53):
            bolt(scene, 62, y, z)
    scene.line(iso(61, 10, 92), iso(61, 10, 166), WELD, 2.0)


def shear_end_plate(scene: Scene) -> None:
    column(scene, 0, 0, 0, 180, 55)
    beam(scene, 55, 10, 100, 150, 45, 40)
    box(scene, 55, 8, 95, 6, 50, 55, CONNECTION)
    for z in (105, 125, 145):
        for y in (18, 45):
            bolt(scene, 62, y, z)
    scene.line(iso(58, 8, 98), iso(58, 8, 148), WELD, 2.2)


def shear_double_angle(scene: Scene) -> None:
    column(scene, 0, 0, 0, 180, 55)
    beam(scene, 55, 10, 100, 150, 45, 38)
    box(scene, 58, 10, 98, 40, 6, 55, CONNECTION)
    box(scene, 58, 49, 98, 40, 6, 55, CONNECTION)
    for z in (108, 128, 148):
        for y in (13, 52):
            bolt(scene, 65, y, z)
    scene.line(iso(59, 10, 100), iso(59, 10, 152), WELD, 2.0)


def shear_seated(scene: Scene) -> None:
    column(scene, 0, 0, 0, 190, 55)
    beam(scene, 55, 10, 105, 150, 45, 38)
    # seat angle: horizontal seat plus vertical leg
    box(scene, 55, 10, 95, 40, 45, 6, CONNECTION)
    box(scene, 55, 10, 100, 6, 45, 55, CONNECTION)
    # top stability angle
    box(scene, 55, 10, 145, 30, 45, 5, CONNECTION)
    for y in (20, 45):
        bolt(scene, 70, y, 105)
        bolt(scene, 70, y, 148)
    scene.line(iso(60, 10, 97), iso(60, 10, 152), WELD, 2.0)


def shear_stiffened_seat(scene: Scene) -> None:
    column(scene, 0, 0, 0, 190, 55)
    beam(scene, 55, 10, 108, 150, 45, 38)
    box(scene, 55, 6, 95, 45, 55, 6, CONNECTION)
    box(scene, 55, 25, 30, 40, 12, 65, CONNECTION)
    box(scene, 55, 10, 148, 30, 45, 5, CONNECTION)
    for y in (16, 48):
        bolt(scene, 75, y, 98)
    scene.line(iso(60, 6, 95), iso(60, 6, 155), WELD, 2.0)


def shear_skewed(scene: Scene) -> None:
    column(scene, 0, 0, 0, 180, 55)
    # Beam arriving at an angle in plan.
    for i in range(8):
        x = 55 + i * 18
        y = 8 + i * 8
        box(scene, x, y, 100, 18, 38, 38, STEEL)
    box(scene, 55, 8, 98, 38, 22, 55, CONNECTION)
    box(scene, 62, 32, 98, 38, 22, 55, CONNECTION)
    for z in (108, 128, 148):
        bolt(scene, 62, 12, z)
        bolt(scene, 70, 36, z)
    scene.line(iso(60, 8, 100), iso(60, 8, 152), WELD, 2.0)


def shear_beam_skewed(scene: Scene) -> None:
    # Supporting girder along y, skewed beam along x.
    box(scene, 20, -20, 75, 240, 40, 50, STEEL)
    for i in range(8):
        x = 55 + i * 18
        y = 20 + i * 8
        box(scene, x, y, 100, 18, 38, 38, STEEL)
    box(scene, 55, 20, 98, 38, 22, 55, CONNECTION)
    box(scene, 62, 44, 98, 38, 22, 55, CONNECTION)
    for z in (108, 128, 148):
        bolt(scene, 62, 24, z)
        bolt(scene, 70, 48, z)
    scene.line(iso(60, 20, 100), iso(60, 20, 152), WELD, 2.0)


def future_moment(scene: Scene) -> None:
    column(scene, 0, 0, 0, 180, 55, FUTURE)
    beam(scene, 55, 10, 95, 150, 45, 55, FUTURE)
    box(scene, 55, 5, 140, 35, 55, 6, FUTURE)
    box(scene, 55, 5, 95, 35, 55, 6, FUTURE)
    scene.text((160, 205), "PRÓXIMAMENTE", "#9e9e9e", 9, "middle")


def future_splice(scene: Scene) -> None:
    beam(scene, 20, 20, 90, 120, 40, 45, FUTURE)
    beam(scene, 150, 20, 90, 120, 40, 45, FUTURE)
    box(scene, 120, 10, 85, 30, 60, 6, FUTURE)
    box(scene, 120, 10, 135, 30, 60, 6, FUTURE)
    for x in (125, 140):
        for y in (20, 50):
            bolt(scene, x, y, 88)
            bolt(scene, x, y, 138)
    scene.text((160, 205), "PRÓXIMAMENTE", "#9e9e9e", 9, "middle")


def family_shear_beam(scene: Scene) -> None:
    # Girder along y, beam along x.
    box(scene, 20, -20, 75, 240, 40, 50, STEEL)
    beam(scene, 55, 20, 100, 150, 45, 38)
    box(scene, 55, 20, 95, 6, 45, 60, CONNECTION)
    for z in (105, 125, 145):
        for y in (28, 50):
            bolt(scene, 62, y, z)
    scene.line(iso(61, 20, 100), iso(61, 20, 152), WELD, 2.0)


def save(name: str, draw) -> None:
    scene = Scene()
    draw(scene)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.svg").write_text(scene.render(), encoding="utf-8")


def main() -> int:
    save("family_base_plate", base_plate)
    save("family_shear_column", shear_single_plate)
    save("family_shear_beam", family_shear_beam)
    save("family_moment", future_moment)
    save("family_splice", future_splice)
    save("base_plate_exposed", base_plate)
    save("base_plate_embedded", base_embedded)
    save("base_plate_weak", base_weak)
    save("shear_double_angle", shear_double_angle)
    save("shear_single_plate", shear_single_plate)
    save("shear_extended_plate", shear_extended_plate)
    save("shear_end_plate", shear_end_plate)
    save("shear_seated", shear_seated)
    save("shear_stiffened_seat", shear_stiffened_seat)
    save("shear_skewed_bent_plate", shear_skewed)
    save("shear_beam_skewed_bent_plate", shear_beam_skewed)
    print(f"wrote {len(list(OUT.glob('*.svg')))} SVGs to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
