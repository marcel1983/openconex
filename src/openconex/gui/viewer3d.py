# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Interactive 3D viewer for base plate solids (OCP + QPainter)."""

from __future__ import annotations

import math
from collections.abc import Callable

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

__all__ = ["Viewer3D", "part_color", "render_parts"]


def part_color(name: str) -> QColor:
    """Stable colour per semantic part name."""
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
        return QColor("#607d8b")
    return QColor("#78909c")


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
        triangles: list[tuple[float, QPolygonF, QColor, str]] = []
        for mesh in self._meshes:
            if mesh.name in self._hidden:
                continue
            color = (self._highlight_color if mesh.name in self._highlight
                     else part_color(mesh.name))
            for p0, p1, p2 in mesh.triangles:
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
                normal = _normal(p0, p1, p2)
                light = abs(normal[0] * 0.35 + normal[1] * -0.45 + normal[2] * 0.82)
                shade = 0.55 + 0.45 * min(light, 1.0)
                tint = QColor(color)
                tint = tint.lighter(int(100 + shade * 70)) if self._selected == mesh.name \
                    else tint.darker(int(120 - shade * 40))
                polygon = QPolygonF([QPointF(point[0], point[1]) for point in points])
                triangles.append((depth, polygon, tint, mesh.name))
        triangles.sort(key=lambda item: item[0])
        painter.setPen(QPen(QColor(30, 35, 40, 90), 0.35))
        for _depth, polygon, tint, name in triangles:
            painter.setBrush(QBrush(tint))
            if name == self._selected:
                painter.setPen(QPen(QColor("#ff6f00"), 1.4))
            else:
                painter.setPen(QPen(QColor(30, 35, 40, 80), 0.35))
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
    """Map the shear model's y-up axes to the viewer's z-up axes."""
    swapped: list[MeshPart] = []
    for mesh in meshes:
        triangles = [((p0[0], p0[2], p0[1]),
                      (p1[0], p1[2], p1[1]),
                      (p2[0], p2[2], p2[1]))
                     for p0, p1, p2 in mesh.triangles]
        swapped.append(MeshPart(mesh.name, tuple(triangles)))
    return swapped


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
    meshes = tessellate_parts(parts)
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
                 parent: QWidget | None = None, swap_yz: bool = False) -> None:
        super().__init__(parent)
        self._build = build
        self._swap_yz = swap_yz
        self._generation = 0
        self._signals = _WorkerSignals()
        self._signals.done.connect(self._on_done)
        self._pool = QThreadPool.globalInstance()
        self._build_ui()

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
        self._status = QLabel("Seleccione un proyecto y pulse Actualizar.")
        self._status.setWordWrap(True)
        bar.addWidget(self._status, 1)
        layout.addLayout(bar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self._canvas = _ViewCanvas()
        reset.clicked.connect(self._canvas.reset_view)
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

    def load_model(self) -> None:
        self._generation += 1
        generation = self._generation
        self._status.setText("Generando modelo 3D…")
        self._canvas.set_hidden(set())
        self._canvas.set_selected(None)
        self._canvas.set_meshes([], "Generando modelo 3D…")
        self._pool.start(_MeshWorker(generation, self._build, self._signals))

    def set_meshes(self, meshes: list[MeshPart], message: str = "") -> None:
        """Populate the viewer synchronously (used by tests and callers)."""
        if self._swap_yz:
            meshes = _swap_yz_meshes(meshes)
        self._canvas.set_meshes(meshes, message)
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
            self._canvas.set_meshes([], f"No se pudo generar el modelo 3D:\n{error}")
            self._status.setText("No se pudo generar el modelo 3D.")
            return
        self.set_meshes(meshes)

    def _on_item_changed(self, _item: QListWidgetItem) -> None:
        hidden = set()
        for row in range(self._list.count()):
            item = self._list.item(row)
            if item.checkState() != Qt.CheckState.Checked:
                hidden.add(item.text())
        self._canvas.set_hidden(hidden)

    def _on_current_changed(self, current: QListWidgetItem | None,
                            _previous: QListWidgetItem | None) -> None:
        self._canvas.set_selected(None if current is None else current.text())
