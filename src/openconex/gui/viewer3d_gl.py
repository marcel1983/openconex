# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""OpenGL canvas for the interactive 3D viewer.

The gallery keeps the deterministic QPainter canvas; this widget is used only
for the interactive tab.  A real depth buffer removes the painter-order
artifacts (serrated occlusion where a beam flange covers an angle, bolts inside
plates, coplanar faces).  If OpenGL is not available, ``Viewer3D`` falls back to
the QPainter canvas.
"""

from __future__ import annotations

import math
from array import array
from typing import Any

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QMatrix4x4,
    QPainter,
    QSurfaceFormat,
    QVector3D,
)
from PySide6.QtOpenGL import (
    QOpenGLBuffer,
    QOpenGLFramebufferObject,
    QOpenGLFramebufferObjectFormat,
    QOpenGLShader,
    QOpenGLShaderProgram,
    QOpenGLVertexArrayObject,
)
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtWidgets import QWidget

from .viewer3d import HINT, MeshPart, _CameraMixin, _normal, part_color

__all__ = ["OpenGLCanvas", "gl_available"]

# Constants not exposed by PySide6's QtOpenGL bindings.
GL_TRIANGLES = 0x0004
GL_FLOAT = 0x1406
GL_DEPTH_TEST = 0x0B71
GL_LESS = 0x0201
GL_MULTISAMPLE = 0x809D
GL_COLOR_BUFFER_BIT = 0x4000
GL_DEPTH_BUFFER_BIT = 0x0100
GL_LINES = 0x0001
GL_POLYGON_OFFSET_FILL = 0x8037

_VERTEX_SHADER = """#version 150
in vec3 a_pos;
in vec3 a_norm;
uniform mat4 u_mvp;
uniform mat4 u_view;
out vec3 v_norm;
void main() {
    gl_Position = u_mvp * vec4(a_pos, 1.0);
    v_norm = mat3(u_view) * a_norm;
}
"""

_FRAGMENT_SHADER = """#version 150
in vec3 v_norm;
uniform vec3 u_color;
uniform vec3 u_light;
uniform float u_flat;
out vec4 frag;
void main() {
    if (u_flat > 0.5) {
        frag = vec4(u_color, 1.0);
        return;
    }
    vec3 n = normalize(v_norm);
    if (!gl_FrontFacing) {
        n = -n;
    }
    float key = max(dot(n, normalize(u_light)), 0.0);
    float fill = max(dot(n, normalize(vec3(-0.45, -0.25, 0.60))), 0.0);
    float shade = 0.58 + 0.32 * key + 0.10 * fill;
    frag = vec4(u_color * shade, 1.0);
}
"""


def gl_available() -> bool:
    """Whether a desktop OpenGL context can be created for the viewer."""
    import os

    from PySide6.QtGui import QOpenGLContext
    from PySide6.QtWidgets import QApplication

    if os.environ.get("OPENCONEX_SOFTWARE_3D") == "1":
        return False
    app = QApplication.instance()
    platform = getattr(app, "platformName", lambda: "")()
    if app is None or platform in {"offscreen", "minimal"}:
        return False
    fmt = QSurfaceFormat()
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    fmt.setDepthBufferSize(24)
    ctx = QOpenGLContext()
    ctx.setFormat(fmt)
    if not ctx.create():
        return False
    actual = ctx.format()
    return (actual.majorVersion(), actual.minorVersion()) >= (3, 2)


class OpenGLCanvas(_CameraMixin, QOpenGLWidget):
    """Depth-buffered, flat-shaded view of the tessellated connection.

    A second pass draws the sharp edges of each solid as dark lines, so plates
    that touch (an angle on a beam web, a nut on a washer) read as separate
    pieces. Faces are pushed back with a polygon offset so that the lines are
    not hidden by the faces they bound.
    """

    failed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        fmt = QSurfaceFormat()
        fmt.setVersion(3, 3)
        fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
        fmt.setDepthBufferSize(24)
        self.setFormat(fmt)
        self._init_camera()
        self._meshes: list[MeshPart] = []
        self._message = "Sin modelo 3D."
        self._hidden: set[str] = set()
        self._selected: str | None = None
        self._program: QOpenGLShaderProgram | None = None
        self._vbo: QOpenGLBuffer | None = None
        self._vao: QOpenGLVertexArrayObject | None = None
        self._edge_vbo: QOpenGLBuffer | None = None
        self._edge_vao: QOpenGLVertexArrayObject | None = None
        self._edge_ranges: list[tuple[str, int, int]] = []
        self._gl: Any = None
        self._ready = False
        self._error = ""
        self._ranges: list[tuple[str, int, int]] = []
        self._fbo: QOpenGLFramebufferObject | None = None
        self._fbo_size = (0, 0)
        self.setMinimumSize(420, 320)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    # -- public API shared with the QPainter canvas -------------------------
    def set_meshes(self, meshes: list[MeshPart], message: str = "",
                   refit: bool = False) -> None:
        first = not self._meshes
        self._meshes = meshes
        self._message = message or ("Sin modelo 3D." if not meshes else "")
        self._fit(meshes, first, refit)
        if first and meshes:
            self.reset_view()
        if self._ready:
            self.makeCurrent()
            try:
                self._upload()
            finally:
                self.doneCurrent()
        self.update()

    def set_hidden(self, hidden: set[str]) -> None:
        self._hidden = set(hidden)
        self.update()

    def set_selected(self, name: str | None) -> None:
        self._selected = name
        self.update()

    # -- GL lifecycle -------------------------------------------------------
    def initializeGL(self) -> None:  # noqa: N802
        try:
            self._gl = self.context().functions()
            program = QOpenGLShaderProgram(self)
            program.bindAttributeLocation("a_pos", 0)
            program.bindAttributeLocation("a_norm", 1)
            if not program.addShaderFromSourceCode(
                    QOpenGLShader.ShaderTypeBit.Vertex, _VERTEX_SHADER):
                raise RuntimeError(program.log())
            if not program.addShaderFromSourceCode(
                    QOpenGLShader.ShaderTypeBit.Fragment, _FRAGMENT_SHADER):
                raise RuntimeError(program.log())
            if not program.link():
                raise RuntimeError(program.log())
            self._program = program
            self._vbo = QOpenGLBuffer(QOpenGLBuffer.Type.VertexBuffer)
            self._vbo.create()
            self._vao = QOpenGLVertexArrayObject()
            self._vao.create()
            self._edge_vbo = QOpenGLBuffer(QOpenGLBuffer.Type.VertexBuffer)
            self._edge_vbo.create()
            self._edge_vao = QOpenGLVertexArrayObject()
            self._edge_vao.create()
            self._ready = True
            self._upload()
        except Exception as exc:  # keep the window usable with the fallback
            self._error = str(exc)
            self._ready = False
            QTimer.singleShot(0, lambda: self.failed.emit(self._error))

    def _upload(self) -> None:
        if not self._ready or self._program is None or self._vbo is None \
                or self._vao is None:
            return
        data = array("f")
        ranges: list[tuple[str, int, int]] = []
        for mesh in self._meshes:
            first = len(data) // 6
            for p0, p1, p2 in mesh.triangles:
                n = _normal(p0, p1, p2)
                for point in (p0, p1, p2):
                    data.extend((point[0], point[1], point[2], n[0], n[1], n[2]))
            ranges.append((mesh.name, first, len(data) // 6 - first))
        self._fill(self._vbo, self._vao, data)
        self._ranges = ranges
        if self._edge_vbo is None or self._edge_vao is None:
            return
        lines = array("f")
        edge_ranges: list[tuple[str, int, int]] = []
        for mesh in self._meshes:
            first = len(lines) // 6
            for a, b in mesh.edges:
                lines.extend((a[0], a[1], a[2], 0.0, 0.0, 1.0,
                              b[0], b[1], b[2], 0.0, 0.0, 1.0))
            edge_ranges.append((mesh.name, first, len(lines) // 6 - first))
        self._fill(self._edge_vbo, self._edge_vao, lines)
        self._edge_ranges = edge_ranges

    def _fill(self, vbo: QOpenGLBuffer, vao: QOpenGLVertexArrayObject, data: array) -> None:
        assert self._program is not None
        raw = data.tobytes()
        vbo.bind()
        vbo.allocate(raw, len(raw))
        vao.bind()
        self._program.bind()
        self._program.enableAttributeArray(0)
        self._program.setAttributeBuffer(0, GL_FLOAT, 0, 3, 24)
        self._program.enableAttributeArray(1)
        self._program.setAttributeBuffer(1, GL_FLOAT, 12, 3, 24)
        self._program.release()
        vao.release()
        vbo.release()

    def _matrices(self) -> tuple[QMatrix4x4, QMatrix4x4]:
        width, height = max(1, self.width()), max(1, self.height())
        scale = min(width, height) * 0.42 * self._zoom / max(self._radius, 1e-9)
        half_w = width / (2 * scale)
        half_h = height / (2 * scale)
        offset_x = -self._pan.x() / scale
        offset_y = self._pan.y() / scale
        near, far = -2 * self._radius, 2 * self._radius
        # Manual orthographic matrix: the view z is -depth, so nearer points
        # have a smaller NDC z and the standard GL_LESS depth test applies.
        projection = QMatrix4x4(
            2 / (2 * half_w), 0, 0, -offset_x / half_w,
            0, 2 / (2 * half_h), 0, -offset_y / half_h,
            0, 0, 2 / (far - near), -(far + near) / (far - near),
            0, 0, 0, 1,
        )
        yaw = math.radians(self._yaw)
        pitch = math.radians(self._pitch)
        cy, sy = math.cos(yaw), math.sin(yaw)
        cp, sp = math.cos(pitch), math.sin(pitch)
        cx, cy0, cz = self._center
        view = QMatrix4x4(
            cy, -sy, 0, -cy * cx + sy * cy0,
            -sy * sp, -cy * sp, cp, sy * sp * cx + cy * sp * cy0 - cp * cz,
            -sy * cp, -cy * cp, -sp, sy * cp * cx + cy * cp * cy0 + sp * cz,
            0, 0, 0, 1,
        )
        return projection * view, view

    def _framebuffer(self, size: QSize) -> QOpenGLFramebufferObject | None:
        if (self._fbo is not None and self._fbo_size == (size.width(), size.height())
                and self._fbo.isValid()):
            return self._fbo
        try:
            fmt = QOpenGLFramebufferObjectFormat()
            fmt.setAttachment(QOpenGLFramebufferObject.Attachment.Depth)
            fmt.setSamples(4)
            fbo = QOpenGLFramebufferObject(size, fmt)
            if not fbo.isValid():
                fmt.setSamples(0)
                fbo = QOpenGLFramebufferObject(size, fmt)
            self._fbo = fbo if fbo.isValid() else None
            self._fbo_size = (size.width(), size.height())
        except Exception:
            self._fbo = None
        return self._fbo

    def paintGL(self) -> None:  # noqa: N802
        if self._gl is None:
            return
        dpr = self.devicePixelRatioF()
        pixel_size = QSize(max(1, int(self.width() * dpr)),
                           max(1, int(self.height() * dpr)))
        fbo = self._framebuffer(pixel_size)
        if fbo is not None:
            fbo.bind()
        self._gl.glViewport(0, 0, pixel_size.width(), pixel_size.height())
        self._gl.glClearColor(0.98, 0.98, 0.98, 1.0)
        self._gl.glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        if self._ready and self._meshes:
            self._gl.glEnable(GL_DEPTH_TEST)
            self._gl.glDepthFunc(GL_LESS)
            self._gl.glEnable(GL_MULTISAMPLE)
            mvp, view = self._matrices()
            assert self._program is not None
            assert self._vao is not None
            program = self._program
            program.bind()
            program.setUniformValue("u_mvp", mvp)  # type: ignore[call-overload]
            program.setUniformValue("u_view", view)  # type: ignore[call-overload]
            program.setUniformValue("u_light", QVector3D(-0.40, 0.50, 0.75))  # type: ignore[call-overload]
            program.setUniformValue1f("u_flat", 0.0)  # type: ignore[call-overload]
            # Push the faces back a little so that the outline wins the depth test.
            self._gl.glEnable(GL_POLYGON_OFFSET_FILL)
            self._gl.glPolygonOffset(1.0, 1.0)
            self._vao.bind()
            for name, first, count in self._ranges:
                if name in self._hidden:
                    continue
                color = part_color(name)
                if name == self._selected:
                    color = color.lighter(135)
                program.setUniformValue(  # type: ignore[call-overload]
                    "u_color", QVector3D(color.redF(), color.greenF(), color.blueF()))
                self._gl.glDrawArrays(GL_TRIANGLES, first, count)
            self._vao.release()
            self._gl.glDisable(GL_POLYGON_OFFSET_FILL)
            if self._edge_vao is not None and self._edge_ranges:
                program.setUniformValue1f("u_flat", 1.0)  # type: ignore[call-overload]
                self._edge_vao.bind()
                for name, first, count in self._edge_ranges:
                    if name in self._hidden or not count:
                        continue
                    color = part_color(name).darker(260 if name != self._selected else 180)
                    program.setUniformValue(  # type: ignore[call-overload]
                        "u_color", QVector3D(color.redF(), color.greenF(), color.blueF()))
                    self._gl.glDrawArrays(GL_LINES, first, count)
                self._edge_vao.release()
            program.release()
        if fbo is not None:
            fbo.release()
            image = fbo.toImage()
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            painter.drawImage(self.rect(), image)
            painter.end()
        self._draw_overlay()

    def _draw_overlay(self) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._message and not self._meshes:
            painter.setPen(QColor("#546e7a"))
            painter.setFont(QFont("Segoe UI", 10))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._message)
        elif self._show_hint:
            painter.setPen(QColor("#455a64"))
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(12, self.height() - 12, HINT)
        painter.end()
