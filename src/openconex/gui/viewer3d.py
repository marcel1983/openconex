# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Interactive 3D viewer for the connection solids (OCP + OpenGL or QPainter).

The viewer follows the form: every change restarts a short timer and, when it
fires, the window's ``snapshot`` (the project read from the form) is meshed in
a worker thread.  Only one worker runs at a time, edits made meanwhile are
coalesced into a single follow-up update, and the meshes of the last models
are cached by the project content, so undoing a change is instant.  The
previous model stays on screen until the new one is ready.
"""

from __future__ import annotations

import math
import time
from collections import OrderedDict
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import (
    QObject,
    QPointF,
    QRunnable,
    QSize,
    Qt,
    QThreadPool,
    QTimer,
    Signal,
)
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
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
from openconex.geometry3d.mesh import (
    MeshPart,
    _explode_meshes,
    _normal,
    _swap_yz_meshes,
    mesh_bounds,
    subdivide_meshes,
    tessellate_parts,
    y_up_to_z_up,
)
from openconex.geometry3d.mesh import cache_key as _default_key
from openconex.geometry3d.mesh import keeps_framing as _keeps_framing
from openconex.help import help_text

__all__ = ["AUTO_DELAY_MS", "Viewer3D", "part_color", "render_parts", "view_angles",
           "y_up_to_z_up"]

VIEW_ANGLES = {
    "iso": (35.0, 25.0),
    "front": (0.0, 0.0),
    "top": (0.0, 89.0),
    "side": (90.0, 0.0),
}

AUTO_DELAY_MS = 300
"""Pause after the last edit before the 3D model is regenerated [ms]."""

CACHE_SIZE = 8
"""Models (by project content) whose meshes are kept for instant re-display."""

HINT = "Arrastre para girar · rueda para zoom · doble clic para ajustar"


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
    if "rebar" in lower:
        return QColor("#455a64")
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


class _CameraMixin:
    """Orbit camera shared by the QPainter and OpenGL canvases."""

    _meshes: list[MeshPart]

    def _init_camera(self) -> None:
        self._home = VIEW_ANGLES["iso"]
        self._flip_yaw = False
        self._yaw, self._pitch = self._home
        self._zoom = 1.0
        self._pan = QPointF()
        self._center = (0.0, 0.0, 0.0)
        self._radius = 1.0
        self._last: QPointF | None = None
        self._mode = ""
        self._show_hint = True

    def set_flip_yaw(self, flip: bool) -> None:
        """Mirror the standard yaw angles (models drawn with the beam toward -y)."""
        self._flip_yaw = bool(flip)
        self._home = self._angles("iso")

    def _angles(self, name: str) -> tuple[float, float]:
        yaw, pitch = view_angles(name)
        return (180.0 - yaw if self._flip_yaw else yaw), pitch

    def _fit(self, meshes: list[MeshPart], first: bool, refit: bool) -> None:
        bounds = mesh_bounds(meshes)
        if bounds is None:
            if first:
                self._center, self._radius = (0.0, 0.0, 0.0), 1.0
            return
        center, radius = bounds
        if first or refit or not _keeps_framing(self._center, self._radius, center, radius):
            self._center, self._radius = center, radius

    def reset_view(self) -> None:
        self._yaw, self._pitch = self._home
        self._zoom = 1.0
        self._pan = QPointF()
        self.update()  # type: ignore[attr-defined]

    def set_view(self, name: str) -> None:
        self._yaw, self._pitch = self._angles(name)
        self._zoom = 1.0
        self._pan = QPointF()
        self.update()  # type: ignore[attr-defined]

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self._last = event.position()
        self._mode = "rotate" if event.button() == Qt.MouseButton.LeftButton else "pan"
        self.setCursor(Qt.CursorShape.ClosedHandCursor)  # type: ignore[attr-defined]

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
        self.update()  # type: ignore[attr-defined]

    def mouseReleaseEvent(self, _event) -> None:  # noqa: N802
        self._last = None
        self._mode = ""
        self.setCursor(Qt.CursorShape.OpenHandCursor)  # type: ignore[attr-defined]

    def mouseDoubleClickEvent(self, _event) -> None:  # noqa: N802
        self.reset_view()

    def wheelEvent(self, event) -> None:  # noqa: N802
        factor = 1.0015 ** event.angleDelta().y()
        self._zoom = max(0.2, min(8.0, self._zoom * factor))
        self.update()  # type: ignore[attr-defined]


class _ViewCanvas(_CameraMixin, QWidget):
    """Orthographic canvas with painter's-algorithm triangle rendering."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._init_camera()
        self._meshes: list[MeshPart] = []
        self._normals: list[tuple[tuple[float, float, float], ...]] = []
        self._hidden: set[str] = set()
        self._highlight: set[str] = set()
        self._highlight_color = QColor("#1565c0")
        self._selected: str | None = None
        self._message = "Sin modelo 3D."
        self.setMinimumSize(420, 320)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def set_meshes(self, meshes: list[MeshPart], message: str = "",
                   refit: bool = False) -> None:
        first = not self._meshes
        self._meshes = meshes
        # Face normals do not change while the camera moves: compute them once.
        self._normals = [tuple(_normal(*triangle) for triangle in mesh.triangles)
                         for mesh in meshes]
        self._message = message or ("Sin modelo 3D." if not meshes else "")
        self._fit(meshes, first, refit)
        if first and meshes:
            self.reset_view()
        self.update()

    def set_hidden(self, hidden: set[str]) -> None:
        self._hidden = set(hidden)
        self.update()

    def set_selected(self, name: str | None) -> None:
        self._selected = name
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
        vx, vy, vz = cpitch * syaw, cpitch * cyaw, spitch
        lx, ly, lz = -0.35, 0.45, 0.82
        triangles: list[tuple[float, int, QPolygonF, QColor]] = []
        for part_index, mesh in enumerate(self._meshes):
            if mesh.name in self._hidden:
                continue
            color = (self._highlight_color if mesh.name in self._highlight
                     else part_color(mesh.name))
            selected = self._selected == mesh.name
            normals = (self._normals[part_index] if part_index < len(self._normals)
                       else tuple(_normal(*t) for t in mesh.triangles))
            tints: dict[int, QColor] = {}
            for (p0, p1, p2), normal in zip(mesh.triangles, normals, strict=False):
                if normal[0] * vx + normal[1] * vy + normal[2] * vz <= 1e-9:
                    continue
                polygon = QPolygonF()
                depth = 0.0
                for point in (p0, p1, p2):
                    x, y, z = point[0] - ox, point[1] - oy, point[2] - oz
                    x1 = x * cyaw - y * syaw
                    y1 = x * syaw + y * cyaw
                    polygon.append(QPointF(cx + x1 * scale,
                                           cy - (z * cpitch - y1 * spitch) * scale))
                    depth += z * spitch + y1 * cpitch
                light = max(0.0, normal[0] * lx + normal[1] * ly + normal[2] * lz)
                shade = 0.55 + 0.45 * min(light, 1.0)
                # QColor.lighter/darker take whole percentages: share one
                # QColor per percentage instead of creating one per triangle.
                factor = int(100 + shade * 70) if selected else int(120 - shade * 40)
                tint = tints.get(factor)
                if tint is None:
                    tint = color.lighter(factor) if selected else color.darker(factor)
                    tints[factor] = tint
                # A tiny part bias keeps coplanar faces from flickering while
                # the model rotates.
                triangles.append((depth / 3 + part_index * 0.001, part_index, polygon, tint))
        triangles.sort(key=lambda item: (item[0], item[1]))
        for _depth, _part, polygon, tint in triangles:
            painter.setBrush(QBrush(tint))
            # Same-colour outline closes antialiasing seams without drawing
            # the triangulation as a wireframe.
            painter.setPen(QPen(tint, 1.0))
            painter.drawPolygon(polygon)
        if self._show_hint:
            painter.setPen(QColor("#455a64"))
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(12, height - 12, HINT)
        painter.end()


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


_NO_VALUE = object()


class _WorkerSignals(QObject):
    done = Signal(int, object, str)


class _MeshWorker(QRunnable):
    """Build the solids and mesh them off the GUI thread."""

    def __init__(self, generation: int, build: Callable[..., list[Part]], value: Any,
                 subdivide: bool, signals: _WorkerSignals) -> None:
        super().__init__()
        self._generation = generation
        self._build = build
        self._value = value
        self._subdivide = subdivide
        self._signals = signals

    def run(self) -> None:
        started = time.perf_counter()
        try:
            parts = self._build() if self._value is _NO_VALUE else self._build(self._value)
            meshes = tessellate_parts(parts, max_edge=None, edges=True)
            painter = subdivide_meshes(meshes) if self._subdivide else None
            error = ""
        except Exception as exc:  # keep the GUI alive if OCP or a part fails
            meshes, painter = [], None
            error = str(exc) or type(exc).__name__
        self._signals.done.emit(self._generation,
                                (meshes, painter, time.perf_counter() - started), error)


class Viewer3D(QWidget):
    """3D tab: automatic asynchronous meshing, part visibility and selection.

    ``build`` returns the OCP parts. With ``snapshot``, the viewer reads the
    model in the GUI thread (``snapshot()``, typically the project read from
    the form), calls ``build(value)`` in a worker thread and caches the meshes
    by ``key(value)``. Without it, ``build()`` is called in the worker on
    every update. ``y_up`` rotates models whose vertical axis is y (shear
    connections). ``explode`` offsets are in the model axes.
    """

    model_updated = Signal()
    """Emitted when a new model is on screen (or failed to build)."""

    def __init__(self, build: Callable[..., list[Part]],
                 parent: QWidget | None = None, *,
                 snapshot: Callable[[], Any] | None = None,
                 key: Callable[[Any], str] | None = None,
                 y_up: bool = False,
                 explode: dict[str, tuple[float, float, float]]
                 | Callable[[], dict[str, tuple[float, float, float]] | None]
                 | None = None,
                 use_opengl: bool | None = None,
                 delay_ms: int = AUTO_DELAY_MS) -> None:
        super().__init__(parent)
        self._build = build
        self._snapshot = snapshot
        self._key = key or _default_key
        self._y_up = y_up
        self._generation = 0
        self._running = False
        self._pending: bool | None = None
        """``None``: nothing queued; otherwise the ``force`` flag of the queued update."""
        self._stale = snapshot is not None
        self._signals = _WorkerSignals()
        self._signals.done.connect(self._on_done)
        self._pool = QThreadPool.globalInstance()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(delay_ms)
        self._timer.timeout.connect(self._on_timer)
        self._cache: OrderedDict[str, list[MeshPart]] = OrderedDict()
        self._current_key: str | None = None
        self._pending_key: str | None = None
        self._explode_spec = explode
        self._exploded = False
        self._model: list[MeshPart] | None = None
        self._painter_model: list[MeshPart] | None = None
        self._hidden: set[str] = set()
        self._selected: str | None = None
        self._use_opengl = _opengl_available() if use_opengl is None else use_opengl
        self._explode_button: QPushButton | None = None
        self._build_ui()
        self._update_explode_visibility()

    # -- construction -----------------------------------------------------------
    def _make_canvas(self) -> Any:
        canvas: Any = None
        if self._use_opengl:
            try:
                from .viewer3d_gl import OpenGLCanvas

                canvas = OpenGLCanvas()
                canvas.failed.connect(self._on_gl_failed)
            except Exception:
                self._use_opengl = False
                canvas = None
        if canvas is None:
            canvas = _ViewCanvas()
        canvas.set_flip_yaw(self._y_up)
        canvas.reset_view()
        return canvas

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
        for label, name in (("Iso", "iso"), ("Frente", "front"),
                            ("Planta", "top"), ("Lado", "side")):
            view = QPushButton(label)
            view.setToolTip(help_text(f"viewer.{name}"))
            view.clicked.connect(lambda _=False, name=name: self._canvas.set_view(name))
            bar.addWidget(view)
        if self._explode_spec is not None:
            self._explode_button = QPushButton("Separar")
            self._explode_button.setCheckable(True)
            self._explode_button.setToolTip(help_text("viewer.explode"))
            self._explode_button.toggled.connect(self._on_explode_toggled)
            bar.addWidget(self._explode_button)
        self._auto = QCheckBox("Automático")
        self._auto.setChecked(True)
        self._auto.setToolTip(help_text("viewer.auto"))
        self._auto.toggled.connect(self._on_auto_toggled)
        self._auto.setVisible(self._snapshot is not None)
        bar.addWidget(self._auto)
        self._status = QLabel("El modelo 3D se genera al abrir esta pestaña."
                              if self._snapshot is not None
                              else "Seleccione un proyecto y pulse Actualizar.")
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
        self._canvas.set_meshes([], "El modelo 3D se genera automáticamente."
                                if self._snapshot is not None
                                else "Pulse Actualizar para generar el modelo 3D.")

    # -- camera and view controls ----------------------------------------------
    def _reset_view(self) -> None:
        self._canvas.reset_view()

    def set_explode_spec(self, spec) -> None:
        self._explode_spec = spec
        self._update_explode_visibility()
        if self._exploded:
            self._refresh_canvas(refit=True)

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
        self._refresh_canvas(refit=True)

    def _current_explode(self) -> dict[str, tuple[float, float, float]] | None:
        if not self._exploded:
            return None
        spec = self._explode_spec
        return spec() if callable(spec) else spec

    def _canvas_meshes(self) -> list[MeshPart]:
        if self._model is None:
            return []
        meshes = self._model
        if not self._use_opengl:
            # The painter's algorithm needs the long triangles split.
            if self._painter_model is None:
                self._painter_model = subdivide_meshes(self._model)
            meshes = self._painter_model
        meshes = _explode_meshes(meshes, self._current_explode())
        return y_up_to_z_up(meshes) if self._y_up else meshes

    def _refresh_canvas(self, message: str = "", refit: bool = False) -> None:
        self._canvas.set_meshes(self._canvas_meshes(), message, refit)

    # -- automatic updates --------------------------------------------------------
    @property
    def auto_update(self) -> bool:
        return self._auto.isChecked()

    def set_auto_update(self, enabled: bool) -> None:
        self._auto.setChecked(enabled)

    def _on_auto_toggled(self, enabled: bool) -> None:
        if enabled and self._stale:
            self.schedule_update()

    def schedule_update(self, *_args: object) -> None:
        """Regenerate the model shortly after the last call (connect to form edits)."""
        if self._snapshot is None:
            return
        self._stale = True
        if self.auto_update:
            self._timer.start()

    def _on_timer(self) -> None:
        if self.isVisible():
            self.update_model()
        # Hidden: stays stale and is rebuilt when the tab is shown.

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if self._stale and self._snapshot is not None and (
                self.auto_update or self._model is None):
            QTimer.singleShot(0, self.update_model)

    @property
    def is_busy(self) -> bool:
        """A worker is meshing or an update is waiting for the timer."""
        return self._running or self._pending is not None or self._timer.isActive()

    # -- model loading ----------------------------------------------------------
    def load_model(self) -> None:
        """Rebuild the model now, without using the cache (button Actualizar)."""
        self.update_model(force=True)

    def update_model(self, force: bool = False) -> None:
        """Show the current model: from the cache, or meshed in the background."""
        self._timer.stop()
        if self._running:
            # One worker at a time: queue a single follow-up that will read the
            # form again when the current one finishes.
            self._pending = bool(force or self._pending)
            return
        value: Any = _NO_VALUE
        key: str | None = None
        if self._snapshot is not None:
            try:
                value = self._snapshot()
            except Exception as exc:
                self._stale = False
                self._show_problem(f"Modelo 3D sin actualizar: {exc}")
                return
            try:
                key = self._key(value)
            except Exception:
                key = None
        self._stale = False
        if not force and key is not None:
            if key == self._current_key and self._model is not None:
                return
            cached = self._cache.get(key)
            if cached is not None:
                self._cache.move_to_end(key)
                self._show(cached, None, key, "desde la caché")
                return
        self._generation += 1
        self._running = True
        self._pending_key = key
        self._status.setText("Actualizando modelo 3D…" if self._model
                             else "Generando modelo 3D…")
        if self._model is None:
            self._canvas.set_meshes([], "Generando modelo 3D…")
        self._pool.start(_MeshWorker(self._generation, self._build, value,
                                     not self._use_opengl, self._signals))

    def _show_problem(self, text: str) -> None:
        """Keep the last good model on screen and explain why it is not current."""
        self._status.setText(text)
        if self._model is None:
            self._canvas.set_meshes([], text)
        self.model_updated.emit()

    def _on_done(self, generation: int, result: tuple, error: str) -> None:
        self._running = False
        if generation == self._generation:
            meshes, painter, seconds = result
            key = self._pending_key
            if error:
                if self._model is None:
                    self._canvas.set_meshes([], f"No se pudo generar el modelo 3D:\n{error}")
                    self._status.setText("No se pudo generar el modelo 3D.")
                else:
                    self._status.setText(f"No se pudo actualizar el modelo 3D: {error}")
                self._current_key = None
                self.model_updated.emit()
            else:
                if key is not None:
                    self._cache[key] = meshes
                    self._cache.move_to_end(key)
                    while len(self._cache) > CACHE_SIZE:
                        self._cache.popitem(last=False)
                self._show(meshes, painter, key, f"{seconds:.2f} s".replace(".", ","))
        if self._pending is not None:
            force = self._pending
            self._pending = None
            self.update_model(force=force)

    def set_meshes(self, meshes: list[MeshPart], message: str = "") -> None:
        """Populate the viewer synchronously (used by tests and callers)."""
        self._generation += 1  # a running worker's result is now stale
        self._show(meshes, None, None, "", message)

    def _show(self, meshes: list[MeshPart], painter: list[MeshPart] | None,
              key: str | None, note: str, message: str = "") -> None:
        refit = self._model is None
        self._model = meshes
        self._painter_model = painter
        self._current_key = key
        names = [mesh.name for mesh in meshes]
        self._hidden &= set(names)
        if self._selected not in names:
            self._selected = None
        self._refresh_canvas(message, refit=refit)
        self._canvas.set_hidden(self._hidden)
        self._canvas.set_selected(self._selected)
        self._fill_list(names)
        triangles = sum(len(mesh.triangles) for mesh in meshes)
        status = f"{len(meshes)} piezas · {triangles} triángulos"
        self._status.setText(f"{status} · {note}" if note else status)
        self.model_updated.emit()

    def _fill_list(self, names: list[str]) -> None:
        current = [self._list.item(row).text() for row in range(self._list.count())]
        self._list.blockSignals(True)
        if current != names:
            self._list.clear()
            for name in names:
                item = QListWidgetItem(name)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setForeground(QBrush(part_color(name)))
                self._list.addItem(item)
        for row in range(self._list.count()):
            item = self._list.item(row)
            item.setCheckState(Qt.CheckState.Unchecked if item.text() in self._hidden
                               else Qt.CheckState.Checked)
            if item.text() == self._selected:
                self._list.setCurrentRow(row)
        if self._selected is None:
            self._list.setCurrentRow(-1)
        self._list.blockSignals(False)

    # -- OpenGL fallback --------------------------------------------------------
    def _on_gl_failed(self, _reason: str) -> None:
        if not self._use_opengl:
            return
        old = self._canvas
        self._use_opengl = False
        new = _ViewCanvas()
        new.set_flip_yaw(self._y_up)
        new.set_meshes(self._canvas_meshes())
        new._hidden = set(self._hidden)
        new._selected = self._selected
        for attribute in ("_yaw", "_pitch", "_zoom", "_pan", "_center", "_radius"):
            if hasattr(old, attribute):
                setattr(new, attribute, getattr(old, attribute))
        new.update()
        self._splitter.replaceWidget(0, new)
        old.deleteLater()
        self._canvas = new
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
