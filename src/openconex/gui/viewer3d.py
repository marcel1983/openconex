# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Interactive 3D viewer for base plate solids (OCP + QPainter)."""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QPointF, QRunnable, QSize, Qt, QThreadPool, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from openconex.geometry3d.base_plate import Part
from openconex.geometry3d.mesh import MeshPart, tessellate_parts
from openconex.help import help_text

__all__ = ["Viewer3D", "part_color", "render_parts", "view_angles"]

VIEW_ANGLES = {
    "iso": (35.0, 25.0),
    "front": (0.0, 0.0),
    "top": (0.0, 89.0),
    "side": (90.0, 0.0),
}


def view_angles(name: str) -> tuple[float, float]:
    """Camera angles for a standard view name."""
    return VIEW_ANGLES[name]


def part_color(name: str) -> QColor:
    """Stable colour per semantic part name.

    Connection elements share a warm highlight so they stand out from the
    grey-blue beam, support and column; bolts stay dark.
    """
    lower = name.casefold()
    if "column" in lower:
        return QColor("#1565c0")
    if "lug" in lower:
        return QColor("#ef6c00")
    if "anchor" in lower or "washer" in lower or "nut" in lower:
        return QColor("#c62828")
    if "grout" in lower:
        return QColor("#bcaaa4")
    if "pedestal" in lower or "foundation" in lower:
        return QColor("#8d6e63")
    if "face_plate" in lower or "embedded" in lower:
        return QColor("#546e7a")
    if "base_plate" in lower:
        return QColor("#ef6c00")
    if ("bolt" in lower or "angle" in lower or "seat" in lower
            or "stiffener" in lower or "bent_plate" in lower
            or "doubler" in lower or lower == "plate" or "end_plate" in lower):
        return QColor("#ef6c00")
    return QColor("#607d8b")


class _ViewCanvas(QWidget):
    """Orthographic canvas with painter's-algorithm triangle rendering."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._meshes: list[MeshPart] = []
        self._hidden: set[str] = set()
        self._highlight: set[str] = set()
        self._highlight_color = QColor("#1565c0")
        self._selected: str | None = None
        self._yaw = 35.0
        self._pitch = 25.0
        self._zoom = 1.0
        self._pan = QPointF()
        self._center = (0.0, 0.0, 0.0)
        self._radius = 1.0
        self._message = "Sin modelo 3D."
        self._last: QPointF | None = None
        self._mode = ""
        self._show_hint = True
        self.setMinimumSize(420, 320)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def set_meshes(self, meshes: list[MeshPart], message: str = "") -> None:
        first = not self._meshes
        self._meshes = meshes
        self._message = message or ("Sin modelo 3D." if not meshes else "")
        points = [point for mesh in meshes for tri in mesh.triangles for point in tri]
        if points:
            xs, ys, zs = zip(*points, strict=False)
            self._center = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2,
                            (min(zs) + max(zs)) / 2)
            self._radius = max(
                math.dist(point, self._center) for point in points) or 1.0
        else:
            self._center = (0.0, 0.0, 0.0)
            self._radius = 1.0
        if first:
            self.reset_view()
        self.update()

    def set_hidden(self, hidden: set[str]) -> None:
        self._hidden = set(hidden)
        self.update()

    def set_selected(self, name: str | None) -> None:
        self._selected = name
        self.update()

    def reset_view(self) -> None:
        self._yaw = 35.0
        self._pitch = 25.0
        self._zoom = 1.0
        self._pan = QPointF()
        self.update()

    def set_view(self, name: str) -> None:
        self._yaw, self._pitch = view_angles(name)
        self._zoom = 1.0
        self._pan = QPointF()
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#fafafa"))
        if not self._meshes:
            painter.setPen(QColor("#546e7a"))
            painter.setFont(QFont("Segoe UI", 10))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._message)
            return
        width, height = self.width(), self.height()
        scale = min(width, height) * 0.42 * self._zoom / self._radius
        cx, cy = width / 2 + self._pan.x(), height / 2 + self._pan.y()
        yaw = math.radians(self._yaw)
        pitch = math.radians(self._pitch)
        cyaw, syaw = math.cos(yaw), math.sin(yaw)
        cpitch, spitch = math.cos(pitch), math.sin(pitch)
        ox, oy, oz = self._center
        # Outward normal of a face must point toward the camera; culling the
        # rest removes hidden surfaces and most painter-order flicker.
        view = (cpitch * syaw, cpitch * cyaw, spitch)
        light_dir = (-0.35, 0.45, 0.82)
        triangles: list[tuple[float, int, QPolygonF, QColor, str]] = []
        for part_index, mesh in enumerate(self._meshes):
            if mesh.name in self._hidden:
                continue
            color = (self._highlight_color if mesh.name in self._highlight
                     else part_color(mesh.name))
            for p0, p1, p2 in mesh.triangles:
                normal = _normal(p0, p1, p2)
                if (normal[0] * view[0] + normal[1] * view[1]
                        + normal[2] * view[2]) <= 1e-9:
                    continue
                points = []
                for point in (p0, p1, p2):
                    x, y, z = point[0] - ox, point[1] - oy, point[2] - oz
                    x1 = x * cyaw - y * syaw
                    y1 = x * syaw + y * cyaw
                    z1 = z
                    screen_x = cx + x1 * scale
                    screen_y = cy - (z1 * cpitch - y1 * spitch) * scale
                    depth = z1 * spitch + y1 * cpitch
                    points.append((screen_x, screen_y, depth))
                depth = sum(point[2] for point in points) / 3
                light = max(0.0, normal[0] * light_dir[0]
                            + normal[1] * light_dir[1]
                            + normal[2] * light_dir[2])
                shade = 0.55 + 0.45 * min(light, 1.0)
                tint = QColor(color)
                tint = tint.lighter(int(100 + shade * 70)) if self._selected == mesh.name \
                    else tint.darker(int(120 - shade * 40))
                polygon = QPolygonF([QPointF(point[0], point[1]) for point in points])
                # A tiny part bias keeps coplanar faces from flickering while
                # the model rotates.
                triangles.append((depth + part_index * 0.001, part_index,
                                  polygon, tint, mesh.name))
        triangles.sort(key=lambda item: (item[0], item[1]))
        for _depth, _part, polygon, tint, _name in triangles:
            painter.setBrush(QBrush(tint))
            # Same-colour outline closes antialiasing seams without drawing
            # the triangulation as a wireframe.
            painter.setPen(QPen(tint, 1.0))
            painter.drawPolygon(polygon)
        if self._show_hint:
            painter.setPen(QColor("#455a64"))
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(12, height - 12, "Arrastre para girar · rueda para zoom · "
                                               "doble clic para ajustar")
        painter.end()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self._last = event.position()
        self._mode = "rotate" if event.button() == Qt.MouseButton.LeftButton else "pan"
        self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._last is None:
            return
        delta = event.position() - self._last
        self._last = event.position()
        if self._mode == "rotate":
            self._yaw += delta.x() * 0.55
            self._pitch = max(-89.0, min(89.0, self._pitch + delta.y() * 0.55))
        elif self._mode == "pan":
            self._pan += delta
        self.update()

    def mouseReleaseEvent(self, _event) -> None:  # noqa: N802
        self._last = None
        self._mode = ""
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mouseDoubleClickEvent(self, _event) -> None:  # noqa: N802
        self.reset_view()

    def wheelEvent(self, event) -> None:  # noqa: N802
        factor = 1.0015 ** event.angleDelta().y()
        self._zoom = max(0.2, min(8.0, self._zoom * factor))
        self.update()


def _swap_yz_meshes(meshes: list[MeshPart]) -> list[MeshPart]:
    """Map the shear model's y-up axes to the viewer's z-up axes.

    Swapping y and z is a reflection: the vertex order is reversed so the
    outward normals keep their orientation and back-face culling stays valid.
    """
    swapped: list[MeshPart] = []
    for mesh in meshes:
        triangles = [((p0[0], p0[2], p0[1]),
                      (p2[0], p2[2], p2[1]),
                      (p1[0], p1[2], p1[1]))
                     for p0, p1, p2 in mesh.triangles]
        swapped.append(MeshPart(mesh.name, tuple(triangles)))
    return swapped


def _explode_meshes(meshes: list[MeshPart],
                    explode: dict[str, tuple[float, float, float]] | None
                    ) -> list[MeshPart]:
    """Move the parts named in ``explode``; a trailing * matches a prefix."""
    if not explode:
        return meshes
    moved: list[MeshPart] = []
    for mesh in meshes:
        shift = explode.get(mesh.name)
        if shift is None:
            for key, value in explode.items():
                if key.endswith("*") and mesh.name.startswith(key[:-1]):
                    shift = value
                    break
        if shift is None:
            moved.append(mesh)
            continue
        dx, dy, dz = shift
        triangles = [((p0[0] + dx, p0[1] + dy, p0[2] + dz),
                      (p1[0] + dx, p1[1] + dy, p1[2] + dz),
                      (p2[0] + dx, p2[1] + dy, p2[2] + dz))
                     for p0, p1, p2 in mesh.triangles]
        moved.append(MeshPart(mesh.name, tuple(triangles)))
    return moved


def render_parts(parts: list[Part], size: QSize, *, yaw: float = 35.0,
                 pitch: float = 25.0, zoom: float = 1.0, margin: float = 1.8,
                 hide: tuple[str, ...] = ("beam", "support", "support_context", "column",
                                          "pedestal", "foundation"),
                 highlight: tuple[str, ...] = (),
                 highlight_color: str = "#1565c0",
                 swap_yz: bool = False,
                 omit: tuple[str, ...] = (),
                 explode: dict[str, tuple[float, float, float]] | None = None) -> QPixmap:
    """Render a static connection thumbnail with the viewer's painter.

    The camera is centred on the connection parts (everything except the main
    members in ``hide``) and pulled back by ``margin`` so some member context
    remains visible.  It is used by the gallery thumbnail generator.
    """
    meshes = tessellate_parts(parts, max_edge=25.0)
    if swap_yz:
        meshes = _swap_yz_meshes(meshes)
    if explode:
        moved = []
        for mesh in meshes:
            shift = explode.get(mesh.name)
            if shift is None:
                moved.append(mesh)
                continue
            dx, dy, dz = shift
            triangles = [((p0[0] + dx, p0[1] + dy, p0[2] + dz),
                          (p1[0] + dx, p1[1] + dy, p1[2] + dz),
                          (p2[0] + dx, p2[1] + dy, p2[2] + dz))
                         for p0, p1, p2 in mesh.triangles]
            moved.append(MeshPart(mesh.name, tuple(triangles)))
        meshes = moved
    canvas = _ViewCanvas()
    canvas.resize(size)
    canvas.set_meshes(meshes)
    hidden = set(hide) | set(omit)
    canvas._hidden = set(omit)
    focus = [mesh for mesh in meshes if mesh.name not in hidden] or meshes
    points = [point for mesh in focus for tri in mesh.triangles for point in tri]
    if points:
        xs, ys, zs = zip(*points, strict=False)
        canvas._center = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2,
                          (min(zs) + max(zs)) / 2)
        radius = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)) / 2
        canvas._radius = max(radius * margin, 1.0)
    canvas._yaw = yaw
    canvas._pitch = pitch
    canvas._zoom = zoom
    canvas._highlight = set(highlight)
    canvas._highlight_color = QColor(highlight_color)
    canvas._show_hint = False
    return canvas.grab()


def _normal(p0: tuple[float, float, float], p1: tuple[float, float, float],
            p2: tuple[float, float, float]) -> tuple[float, float, float]:
    ax, ay, az = p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]
    bx, by, bz = p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2]
    nx, ny, nz = ay * bz - az * by, az * bx - ax * bz, ax * by - ay * bx
    length = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
    return nx / length, ny / length, nz / length


def _opengl_available() -> bool:
    """Whether the interactive GL canvas can be used in this session."""
    import os

    from PySide6.QtWidgets import QApplication

    if os.environ.get("OPENCONEX_SOFTWARE_3D") == "1":
        return False
    app = QApplication.instance()
    if app is None:
        return False
    platform = getattr(app, "platformName", lambda: "")()
    if platform in {"offscreen", "minimal"}:
        # Do not even import QtOpenGLWidgets: on headless Qt it can leave a
        # shared QObject behind and crash the process during teardown.
        return False
    try:
        from .viewer3d_gl import gl_available

        return gl_available()
    except Exception:
        return False


class _WorkerSignals(QObject):
    done = Signal(int, object, str)


class _MeshWorker(QRunnable):
    def __init__(self, generation: int, build: Callable[[], list[Part]],
                 signals: _WorkerSignals) -> None:
        super().__init__()
        self._generation = generation
        self._build = build
        self._signals = signals

    def run(self) -> None:
        try:
            meshes = tessellate_parts(self._build())
            error = ""
        except Exception as exc:  # keep the GUI alive if OCP or a part fails
            meshes = []
            error = str(exc)
        self._signals.done.emit(self._generation, meshes, error)


class Viewer3D(QWidget):
    """3D tab: asynchronous meshing, part visibility and selection."""

    def __init__(self, build: Callable[[], list[Part]],
                 parent: QWidget | None = None, swap_yz: bool = False,
                 explode: dict[str, tuple[float, float, float]]
                 | Callable[[], dict[str, tuple[float, float, float]] | None]
                 | None = None,
                 use_opengl: bool | None = None) -> None:
        super().__init__(parent)
        self._build = build
        self._swap_yz = swap_yz
        self._generation = 0
        self._signals = _WorkerSignals()
        self._signals.done.connect(self._on_done)
        self._pool = QThreadPool.globalInstance()
        self._explode_spec = explode
        self._exploded = False
        self._base_meshes: list[MeshPart] = []
        self._hidden: set[str] = set()
        self._selected: str | None = None
        self._use_opengl = _opengl_available() if use_opengl is None else use_opengl
        self._explode_button: QPushButton | None = None
        self._build_ui()
        self._update_explode_visibility()

    # -- construction -----------------------------------------------------------
    def _make_canvas(self) -> Any:
        if self._use_opengl:
            try:
                from .viewer3d_gl import OpenGLCanvas

                canvas = OpenGLCanvas()
                canvas.failed.connect(self._on_gl_failed)
                return canvas
            except Exception:
                self._use_opengl = False
        return _ViewCanvas()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        bar = QHBoxLayout()
        refresh = QPushButton("Actualizar")
        refresh.clicked.connect(self.load_model)
        reset = QPushButton("Ajustar vista")
        refresh.setToolTip(help_text("viewer.refresh"))
        reset.setToolTip(help_text("viewer.reset"))
        bar.addWidget(refresh)
        bar.addWidget(reset)
        for label, key in (("Iso", "iso"), ("Frente", "front"),
                           ("Planta", "top"), ("Lado", "side")):
            view = QPushButton(label)
            view.setToolTip(help_text(f"viewer.{key}"))
            view.clicked.connect(lambda _=False, name=key: self._canvas.set_view(name))
            bar.addWidget(view)
        if self._explode_spec is not None:
            self._explode_button = QPushButton("Separar")
            self._explode_button.setCheckable(True)
            self._explode_button.setToolTip(help_text("viewer.explode"))
            self._explode_button.toggled.connect(self._on_explode_toggled)
            bar.addWidget(self._explode_button)
        self._status = QLabel("Seleccione un proyecto y pulse Actualizar.")
        self._status.setWordWrap(True)
        bar.addWidget(self._status, 1)
        layout.addLayout(bar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter = splitter
        self._canvas: Any = self._make_canvas()
        reset.clicked.connect(self._reset_view)
        splitter.addWidget(self._canvas)
        side = QWidget()
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(4, 0, 0, 0)
        side_layout.addWidget(QLabel("Piezas"))
        self._list = QListWidget()
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._list.itemChanged.connect(self._on_item_changed)
        self._list.currentItemChanged.connect(self._on_current_changed)
        side_layout.addWidget(self._list, 1)
        side.setMinimumWidth(180)
        side.setMaximumWidth(260)
        splitter.addWidget(side)
        splitter.setSizes([700, 220])
        layout.addWidget(splitter, 1)
        self._canvas.set_meshes([], "Pulse Actualizar para generar el modelo 3D.")

    # -- camera and view controls ----------------------------------------------
    def _reset_view(self) -> None:
        self._canvas.reset_view()

    def set_explode_spec(self, spec) -> None:
        self._explode_spec = spec
        self._update_explode_visibility()
        if self._exploded:
            self._refresh_canvas()

    def _update_explode_visibility(self) -> None:
        if self._explode_button is None:
            return
        spec = self._explode_spec() if callable(self._explode_spec) else self._explode_spec
        available = spec is not None
        self._explode_button.setVisible(available)
        if not available:
            self._exploded = False
            self._explode_button.setChecked(False)

    def _on_explode_toggled(self, checked: bool) -> None:
        self._exploded = bool(checked)
        self._refresh_canvas()

    def _current_explode(self) -> dict[str, tuple[float, float, float]] | None:
        if not self._exploded:
            return None
        spec = self._explode_spec
        return spec() if callable(spec) else spec

    def _canvas_meshes(self) -> list[MeshPart]:
        return _explode_meshes(self._base_meshes, self._current_explode())

    def _refresh_canvas(self, message: str = "") -> None:
        self._canvas.set_meshes(self._canvas_meshes(), message)

    # -- model loading ----------------------------------------------------------
    def load_model(self) -> None:
        self._generation += 1
        generation = self._generation
        self._status.setText("Generando modelo 3D…")
        self._base_meshes = []
        self._hidden = set()
        self._selected = None
        self._canvas.set_hidden(set())
        self._canvas.set_selected(None)
        self._canvas.set_meshes([], "Generando modelo 3D…")
        self._pool.start(_MeshWorker(generation, self._build, self._signals))

    def set_meshes(self, meshes: list[MeshPart], message: str = "") -> None:
        """Populate the viewer synchronously (used by tests and callers)."""
        if self._swap_yz:
            meshes = _swap_yz_meshes(meshes)
        self._base_meshes = meshes
        self._hidden = set()
        self._selected = None
        self._refresh_canvas(message)
        self._canvas.set_hidden(set())
        self._canvas.set_selected(None)
        self._list.blockSignals(True)
        self._list.clear()
        for mesh in meshes:
            item = QListWidgetItem(mesh.name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            item.setForeground(QBrush(part_color(mesh.name)))
            self._list.addItem(item)
        self._list.blockSignals(False)
        triangles = sum(len(mesh.triangles) for mesh in meshes)
        self._status.setText(f"{len(meshes)} piezas · {triangles} triángulos")

    def _on_done(self, generation: int, meshes: list[MeshPart], error: str) -> None:
        if generation != self._generation:
            return
        if error:
            self._base_meshes = []
            self._canvas.set_meshes([], f"No se pudo generar el modelo 3D:\n{error}")
            self._status.setText("No se pudo generar el modelo 3D.")
            return
        self.set_meshes(meshes)

    # -- OpenGL fallback --------------------------------------------------------
    def _on_gl_failed(self, _reason: str) -> None:
        if not self._use_opengl:
            return
        old = self._canvas
        new = _ViewCanvas()
        new.set_meshes(self._canvas_meshes())
        new._hidden = set(self._hidden)
        new._selected = self._selected
        for attribute in ("_yaw", "_pitch", "_zoom", "_pan"):
            if hasattr(old, attribute):
                setattr(new, attribute, getattr(old, attribute))
        new._center = getattr(old, "_center", new._center)
        new._radius = getattr(old, "_radius", new._radius)
        new.update()
        self._splitter.replaceWidget(0, new)
        old.deleteLater()
        self._canvas = new
        self._use_opengl = False
        self._status.setText("Vista simplificada: OpenGL no disponible.")

    # -- list interactions ------------------------------------------------------
    def _on_item_changed(self, _item: QListWidgetItem) -> None:
        hidden = set()
        for row in range(self._list.count()):
            item = self._list.item(row)
            if item.checkState() != Qt.CheckState.Checked:
                hidden.add(item.text())
        self._hidden = hidden
        self._canvas.set_hidden(hidden)

    def _on_current_changed(self, current: QListWidgetItem | None,
                            _previous: QListWidgetItem | None) -> None:
        self._selected = None if current is None else current.text()
        self._canvas.set_selected(self._selected)
