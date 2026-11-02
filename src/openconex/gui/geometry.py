# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Graphical plan and elevation editor for base plates."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from openconex.units import Kind, UnitSystem, format_value

__all__ = ["GeometryEditor", "GeometryValues"]

PLATE_PEN = QColor("#37474f")
PLATE_BRUSH = QColor("#eceff1")
COLUMN_PEN = QColor("#1565c0")
COLUMN_BRUSH = QColor("#bbdefb")
ANCHOR_PEN = QColor("#b71c1c")
ANCHOR_BRUSH = QColor("#ffcdd2")
PEDESTAL_PEN = QColor("#6d4c41")
LUG_PEN = QColor("#ef6c00")
HANDLE = QColor("#00897b")


@dataclass
class GeometryValues:
    """Current form geometry in internal units (N, mm, MPa)."""

    N: float | None
    B: float | None
    tp: float | None
    grout: float | None
    f: float | None
    rod_spacing: float | None
    hef: float | None
    rods_per_side: int
    column_d: float | None
    column_bf: float | None
    column_label: str
    pedestal_N: float | None
    pedestal_B: float | None
    lug_width: float | None
    lug_direction: str
    units: UnitSystem


class _FitView(QGraphicsView):
    """Graphics view that keeps the whole scene visible when resized."""

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self.scene() is not None:
            self.fitInView(self.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)


class _HandleItem(QGraphicsEllipseItem):
    """Draggable handle; reports its final scene position on release."""

    def __init__(self, kind: str, radius: float,
                 callback: Callable[[str, QPointF], None]) -> None:
        super().__init__(-radius, -radius, 2 * radius, 2 * radius)
        self.kind = kind
        self._callback = callback
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setBrush(QBrush(HANDLE))
        self.setPen(QPen(QColor("#ffffff")))
        self.setZValue(20)
        self.setCursor(Qt.CursorShape.SizeAllCursor)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        super().mouseReleaseEvent(event)
        self._callback(self.kind, self.pos())


def _pen(color: QColor, width: float = 0.0, style=Qt.PenStyle.SolidLine) -> QPen:
    pen = QPen(color, width, style)
    pen.setCosmetic(True)
    return pen


def _text(scene: QGraphicsScene, text: str, x: float, y: float,
          size: int = 9) -> None:
    item = scene.addSimpleText(text, QFont("Segoe UI", size))
    item.setBrush(QBrush(QColor("#263238")))
    item.setPos(x, y)


def _dimension(value: float, values: GeometryValues) -> str:
    return format_value(value, Kind.LENGTH, values.units, precision=4)


class GeometryEditor(QWidget):
    """Two-way plan/elevation editor for the base plate form."""

    def __init__(self, read: Callable[[], GeometryValues | None],
                 apply: Callable[[dict[str, float]], None],
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._read = read
        self._apply = apply
        self._current: GeometryValues | None = None
        self._undo: list[tuple[dict[str, float], dict[str, float]]] = []
        self._redo: list[tuple[dict[str, float], dict[str, float]]] = []
        self._build()
        self.refresh()

    # -- construction -----------------------------------------------------------
    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        bar = QHBoxLayout()
        self._undo_button = QPushButton("Deshacer")
        self._undo_button.setShortcut("Ctrl+Z")
        self._undo_button.clicked.connect(self.undo)
        self._redo_button = QPushButton("Rehacer")
        self._redo_button.setShortcut("Ctrl+Y")
        self._redo_button.clicked.connect(self.redo)
        bar.addWidget(self._undo_button)
        bar.addWidget(self._redo_button)
        hint = QLabel("Arrastre los bordes de la placa, los anclajes o los hitos de "
                      "elevación para cambiar las dimensiones.")
        hint.setWordWrap(True)
        bar.addWidget(hint, 1)
        layout.addLayout(bar)

        splitter = QSplitter(Qt.Orientation.Vertical)
        plan = QWidget()
        plan_layout = QVBoxLayout(plan)
        plan_layout.setContentsMargins(0, 0, 0, 0)
        plan_layout.addWidget(QLabel("Planta"))
        self._plan_scene = QGraphicsScene(self)
        self._plan_view = _FitView(self._plan_scene, self)
        self._plan_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._plan_view.setBackgroundBrush(QBrush(QColor("#fafafa")))
        plan_layout.addWidget(self._plan_view, 1)
        splitter.addWidget(plan)

        elevation = QWidget()
        elevation_layout = QVBoxLayout(elevation)
        elevation_layout.setContentsMargins(0, 0, 0, 0)
        elevation_layout.addWidget(QLabel("Elevación"))
        self._elevation_scene = QGraphicsScene(self)
        self._elevation_view = _FitView(self._elevation_scene, self)
        self._elevation_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._elevation_view.setBackgroundBrush(QBrush(QColor("#fafafa")))
        elevation_layout.addWidget(self._elevation_view, 1)
        splitter.addWidget(elevation)
        splitter.setSizes([460, 300])
        layout.addWidget(splitter, 1)
        self._update_buttons()

    # -- public API -------------------------------------------------------------
    def refresh(self) -> None:
        self._current = self._read()
        self._draw_plan()
        self._draw_elevation()
        self._update_buttons()

    def clear_history(self) -> None:
        self._undo.clear()
        self._redo.clear()
        self._update_buttons()

    def undo(self) -> None:
        if not self._undo:
            return
        before, after = self._undo.pop()
        self._redo.append((before, after))
        self._set_current(before)
        self._apply(before)
        QTimer.singleShot(0, self.refresh)
        self._update_buttons()

    def redo(self) -> None:
        if not self._redo:
            return
        before, after = self._redo.pop()
        self._undo.append((before, after))
        self._set_current(after)
        self._apply(after)
        QTimer.singleShot(0, self.refresh)
        self._update_buttons()

    # -- editing ----------------------------------------------------------------
    def _set_current(self, values: dict[str, float]) -> None:
        if self._current is None:
            return
        for key, value in values.items():
            if hasattr(self._current, key):
                setattr(self._current, key, value)

    def _editable(self, values: GeometryValues | None) -> dict[str, float]:
        if values is None:
            return {}
        keys = ("N", "B", "tp", "grout", "f", "rod_spacing", "hef",
                "pedestal_N", "pedestal_B")
        return {key: float(getattr(values, key)) for key in keys
                if getattr(values, key) is not None}

    def _commit(self, changes: dict[str, float]) -> None:
        before = self._editable(self._current)
        after = dict(before)
        for key, value in changes.items():
            if key in before:
                after[key] = max(float(value), 0.1)
        changed = {key: value for key, value in after.items()
                   if abs(value - before.get(key, value)) > 1e-6}
        if not changed:
            return
        self._undo.append((before, after))
        self._redo.clear()
        self._set_current(changed)
        self._apply(changed)
        QTimer.singleShot(0, self.refresh)
        self._update_buttons()

    def _on_handle(self, kind: str, position: QPointF) -> None:
        values = self._current
        if values is None:
            return
        min_b = max((values.column_bf or 0.0) * 1.2, 100.0)
        min_n = max((values.column_d or 0.0) * 1.2, 100.0)
        min_spacing = max((values.column_bf or 0.0) * 0.8, 50.0)
        min_f = max((values.column_d or 0.0) / 2 + 20.0, 50.0)
        if kind in ("edge_left", "edge_right"):
            self._commit({"B": max(2 * abs(position.x()), min_b)})
        elif kind in ("edge_top", "edge_bottom"):
            self._commit({"N": max(2 * abs(position.y()), min_n)})
        elif kind.startswith("anchor"):
            self._commit({"rod_spacing": max(2 * abs(position.x()), min_spacing),
                          "f": max(abs(position.y()), min_f)})
        elif kind == "plate_top" and values.tp is not None:
            self._commit({"tp": max(abs(position.y()), 1.0)})
        elif kind == "grout_bottom" and values.grout is not None:
            self._commit({"grout": max(abs(position.y()), 0.1)})
        elif kind == "hef_bottom" and values.hef is not None and values.grout:
            self._commit({"hef": max(abs(position.y()) - values.grout, 0.1)})
        elif kind == "pedestal_left" or kind == "pedestal_right":
            minimum = (values.B or 100.0) * 1.05
            self._commit({"pedestal_B": max(2 * abs(position.x()), minimum)})
        elif kind == "pedestal_top" or kind == "pedestal_bottom":
            minimum = (values.N or 100.0) * 1.05
            self._commit({"pedestal_N": max(2 * abs(position.y()), minimum)})

    def _update_buttons(self) -> None:
        self._undo_button.setEnabled(bool(self._undo))
        self._redo_button.setEnabled(bool(self._redo))

    # -- drawing ----------------------------------------------------------------
    def _message(self, scene: QGraphicsScene, text: str) -> None:
        scene.clear()
        item = scene.addSimpleText(text, QFont("Segoe UI", 10))
        item.setBrush(QBrush(QColor("#546e7a")))
        item.setPos(-item.boundingRect().width() / 2, -item.boundingRect().height() / 2)
        scene.setSceneRect(item.boundingRect().adjusted(-30, -30, 30, 30))
        if scene is self._plan_scene:
            self._plan_view.fitInView(scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        else:
            self._elevation_view.fitInView(scene.sceneRect(),
                                           Qt.AspectRatioMode.KeepAspectRatio)

    def _draw_plan(self) -> None:
        scene = self._plan_scene
        scene.clear()
        values = self._current
        if values is None or not values.N or not values.B:
            self._message(scene, "Complete N y B para ver la planta.")
            return
        B, N = float(values.B), float(values.N)
        column_b = values.column_bf or B * 0.45
        column_d = values.column_d or N * 0.45
        span = max(B, N, values.pedestal_B or 0, values.pedestal_N or 0,
                   values.lug_width or 0) * 1.55
        scene.setSceneRect(-span / 2, -span / 2, span, span)

        if values.pedestal_B and values.pedestal_N:
            scene.addRect(-values.pedestal_B / 2, -values.pedestal_N / 2,
                          values.pedestal_B, values.pedestal_N,
                          _pen(PEDESTAL_PEN, style=Qt.PenStyle.DashLine))
            pedestal_handles = (
                ("pedestal_left", -values.pedestal_B / 2, 0),
                ("pedestal_right", values.pedestal_B / 2, 0),
                ("pedestal_top", 0, -values.pedestal_N / 2),
                ("pedestal_bottom", 0, values.pedestal_N / 2))
        else:
            pedestal_handles = ()
        scene.addRect(-B / 2, -N / 2, B, N, _pen(PLATE_PEN), QBrush(PLATE_BRUSH))
        scene.addRect(-column_b / 2, -column_d / 2, column_b, column_d,
                      _pen(COLUMN_PEN), QBrush(COLUMN_BRUSH))

        if values.f and values.rod_spacing:
            spacing = float(values.rod_spacing)
            f = float(values.f)
            count = max(values.rods_per_side, 2)
            xs = ([ -spacing / 2 + index * spacing / (count - 1)
                    for index in range(count)] if count > 1 else [0.0])
            radius = max(span * 0.008, 4.0)
            for y in (-f, f):
                for x in xs:
                    scene.addEllipse(x - radius, y - radius, 2 * radius, 2 * radius,
                                     _pen(ANCHOR_PEN), QBrush(ANCHOR_BRUSH))
            for x in (-spacing / 2, spacing / 2):
                for y in (-f, f):
                    handle = _HandleItem("anchor", radius * 1.6, self._on_handle)
                    handle.setPos(x, y)
                    scene.addItem(handle)

        if values.lug_width:
            width = float(values.lug_width)
            if values.lug_direction in ("strong", "both"):
                scene.addRect(-width / 2, N / 2 - width, width, width,
                              _pen(LUG_PEN), QBrush(QColor("#ffe0b2")))
            if values.lug_direction in ("weak", "both"):
                scene.addRect(-B / 2, -width / 2, width, width,
                              _pen(LUG_PEN), QBrush(QColor("#ffe0b2")))

        handle_r = max(span * 0.007, 4.0)
        for kind, x, y in (("edge_left", -B / 2, 0), ("edge_right", B / 2, 0),
                           ("edge_top", 0, -N / 2), ("edge_bottom", 0, N / 2)):
            item = _HandleItem(kind, handle_r, self._on_handle)
            item.setPos(x, y)
            scene.addItem(item)
        for kind, x, y in pedestal_handles:
            item = _HandleItem(kind, handle_r, self._on_handle)
            item.setPos(x, y)
            scene.addItem(item)

        _text(scene, f"Planta · {values.column_label or 'columna'}",
              -span / 2 + 8, -span / 2 + 8, 10)
        _text(scene, f"N = {_dimension(N, values)}", -span / 2 + 8, N / 2 + 8)
        _text(scene, f"B = {_dimension(B, values)}", -B / 2, span / 2 - 24)
        if values.f and values.rod_spacing:
            _text(scene, f"f = {_dimension(values.f, values)}",
                  B / 2 + 8, -N / 2 + 8)
            _text(scene, f"separación = {_dimension(values.rod_spacing, values)}",
                  -span / 2 + 8, -N / 2 - 22)
        self._plan_view.fitInView(scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def _draw_elevation(self) -> None:
        scene = self._elevation_scene
        scene.clear()
        values = self._current
        if values is None or not values.tp or values.grout is None:
            self._message(scene, "Complete tp y mortero para ver la elevación.")
            return
        B = float(values.B or 600.0)
        tp = float(values.tp)
        grout = float(values.grout)
        hef = float(values.hef or 0.0)
        column_b = float(values.column_bf or B * 0.45)
        column_h = max(B * 0.55, 250.0)
        span = max(B, column_h, hef + grout + tp) * 1.45
        top = -tp - column_h
        bottom = grout + max(hef, 0.0)
        scene.setSceneRect(-span / 2, top - 60, span, bottom - top + 120)

        if values.pedestal_B:
            scene.addRect(-values.pedestal_B / 2, grout, values.pedestal_B,
                          max(B * 0.25, 100.0), _pen(PEDESTAL_PEN,
                                                      style=Qt.PenStyle.DashLine))
        scene.addRect(-B / 2, -tp, B, tp, _pen(PLATE_PEN), QBrush(PLATE_BRUSH))
        scene.addRect(-B / 2, 0, B, grout, _pen(PEDESTAL_PEN),
                      QBrush(QColor("#d7ccc8")))
        scene.addRect(-column_b / 2, top, column_b, column_h,
                      _pen(COLUMN_PEN), QBrush(COLUMN_BRUSH))

        if values.rod_spacing:
            spacing = float(values.rod_spacing)
            for x in (-spacing / 2, spacing / 2):
                scene.addLine(x, -tp, x, grout + hef, _pen(ANCHOR_PEN))
                scene.addEllipse(x - 6, -tp - 6, 12, 12, _pen(ANCHOR_PEN),
                                 QBrush(ANCHOR_BRUSH))

        handle_r = max(span * 0.007, 4.0)
        for kind, x, y in (("plate_top", B / 2 * 0.75, -tp),
                           ("grout_bottom", B / 2 * 0.75, grout),
                           ("hef_bottom", B / 2 * 0.75, grout + hef)):
            item = _HandleItem(kind, handle_r, self._on_handle)
            item.setPos(x, y)
            scene.addItem(item)

        _text(scene, f"Elevación · tp = {_dimension(tp, values)}",
              -span / 2 + 8, top - 24, 10)
        _text(scene, f"mortero = {_dimension(grout, values)}",
              -span / 2 + 8, grout + 8)
        if values.hef:
            _text(scene, f"hef = {_dimension(values.hef, values)}",
                  -span / 2 + 8, grout + hef + 8)
        self._elevation_view.fitInView(scene.sceneRect(),
                                       Qt.AspectRatioMode.KeepAspectRatio)
