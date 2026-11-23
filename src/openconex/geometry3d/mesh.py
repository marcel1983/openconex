# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Triangulated meshes from OpenCASCADE parts for the 3D viewer."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from openconex.geometry3d.base_plate import Part

__all__ = ["MAX_EDGE", "MeshPart", "cache_key", "feature_edges", "keeps_framing",
           "mesh_bounds", "subdivide_meshes", "tessellate_parts", "y_up_to_z_up"]

Point = tuple[float, float, float]
Triangle = tuple[Point, Point, Point]
Segment = tuple[Point, Point]

# Large planar faces are only two triangles.  The painter's algorithm sorts by
# triangle depth, so a huge face can be drawn over a nearer small part.  Split
# long triangles to keep the depth comparison local.  Only the QPainter canvas
# (fallback and gallery) needs it: the OpenGL canvas has a depth buffer and
# draws the triangles exactly as OpenCASCADE produced them.
MAX_EDGE = 40.0

# Angular deflection of the tessellation [rad]: about 21 facets on a bolt, so
# rods and bolts look round without a visible polygon.
ANGULAR_DEFLECTION = 0.3

# Edges whose adjacent faces meet at more than this angle are drawn as lines.
# It must stay above the facet angle of curved faces (ANGULAR_DEFLECTION ≈ 17°)
# so that cylinders show only their outline, not their facets.
SHARP_ANGLE = 35.0


@dataclass(frozen=True)
class MeshPart:
    name: str
    triangles: tuple[Triangle, ...]
    edges: tuple[Segment, ...] = ()
    """Sharp (feature) edges of the solid, for the outline pass."""


def _midpoint(a: Point, b: Point) -> Point:
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2)


def _split(a: Point, b: Point, c: Point) -> tuple[Triangle, Triangle]:
    """Split the edge a-b, preserving the winding of (a, b, c)."""
    m = _midpoint(a, b)
    return (a, m, c), (m, b, c)


def _subdivide(triangle: Triangle, max_edge: float,
               depth: int = 0) -> list[Triangle]:
    p0, p1, p2 = triangle
    edges = ((p0, p1, p2), (p1, p2, p0), (p2, p0, p1))
    lengths = (math.dist(p0, p1), math.dist(p1, p2), math.dist(p2, p0))
    index = max(range(3), key=lengths.__getitem__)
    if lengths[index] <= max_edge or depth >= 12:
        return [triangle]
    a, b, c = edges[index]
    return [part for child in _split(a, b, c)
            for part in _subdivide(child, max_edge, depth + 1)]


def _subdivide_triangles(triangles: tuple[Triangle, ...] | list[Triangle],
                         max_edge: float) -> tuple[Triangle, ...]:
    return tuple(part for triangle in triangles
                 for part in _subdivide(triangle, max_edge))


def subdivide_meshes(meshes: list[MeshPart], max_edge: float = MAX_EDGE) -> list[MeshPart]:
    """Meshes for the painter's algorithm: long triangles split, edges kept."""
    return [MeshPart(mesh.name, _subdivide_triangles(mesh.triangles, max_edge), mesh.edges)
            for mesh in meshes]


def _unit_normal(p0: Point, p1: Point, p2: Point) -> Point | None:
    ax, ay, az = p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]
    bx, by, bz = p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2]
    nx, ny, nz = ay * bz - az * by, az * bx - ax * bz, ax * by - ay * bx
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    if length <= 1e-12:
        return None
    return nx / length, ny / length, nz / length


def feature_edges(triangles: tuple[Triangle, ...] | list[Triangle],
                  angle: float = SHARP_ANGLE) -> tuple[Segment, ...]:
    """Edges of a closed triangle mesh where the surface folds by more than ``angle``.

    Edges shared by coplanar triangles (the internal triangulation, or two
    faces that a boolean fuse left side by side) are not features. Edges with
    a single triangle are kept: they are the outline of an open patch.
    """
    cos_limit = math.cos(math.radians(angle))
    normals: dict[tuple[Point, Point], list[Point]] = {}
    ends: dict[tuple[Point, Point], Segment] = {}

    def key(point: Point) -> Point:
        return (round(point[0], 4), round(point[1], 4), round(point[2], 4))

    for triangle in triangles:
        normal = _unit_normal(*triangle)
        if normal is None:
            continue
        for a, b in ((triangle[0], triangle[1]), (triangle[1], triangle[2]),
                     (triangle[2], triangle[0])):
            ka, kb = key(a), key(b)
            edge = (ka, kb) if ka <= kb else (kb, ka)
            normals.setdefault(edge, []).append(normal)
            ends.setdefault(edge, (a, b))
    out: list[Segment] = []
    for edge, faces in normals.items():
        if len(faces) == 1:
            out.append(ends[edge])
            continue
        first = faces[0]
        if any(first[0] * other[0] + first[1] * other[1] + first[2] * other[2] < cos_limit
               for other in faces[1:]):
            out.append(ends[edge])
    return tuple(out)


def tessellate_parts(parts: list[Part], deflection: float = 0.35,
                     max_edge: float | None = MAX_EDGE, *,
                     angular: float = ANGULAR_DEFLECTION,
                     edges: bool = False) -> list[MeshPart]:
    """Triangulate every part; faces without a mesh are skipped.

    ``max_edge=None`` keeps the OpenCASCADE triangles (OpenGL canvas); a value
    splits long triangles for the painter's algorithm. ``edges=True`` also
    returns the sharp edges of each solid for the outline pass.
    """
    from OCP.BRep import BRep_Tool
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopLoc import TopLoc_Location
    from OCP.TopoDS import TopoDS

    meshes: list[MeshPart] = []
    for part in parts:
        BRepMesh_IncrementalMesh(part.shape, deflection, False, angular, True)
        explorer = TopExp_Explorer(part.shape, TopAbs_FACE)
        triangles: list[Triangle] = []
        while explorer.More():
            face = TopoDS.Face(explorer.Current())
            reversed_face = face.Orientation() == TopAbs_REVERSED
            location = TopLoc_Location()
            triangulation = BRep_Tool.Triangulation_s(face, location)
            if triangulation is not None:
                transform = location.Transformation()
                nodes = []
                for index in range(1, triangulation.NbNodes() + 1):
                    point = triangulation.Node(index).Transformed(transform)
                    nodes.append((point.X(), point.Y(), point.Z()))
                for index in range(1, triangulation.NbTriangles() + 1):
                    a, b, c = triangulation.Triangle(index).Get()
                    if reversed_face:
                        triangles.append((nodes[a - 1], nodes[c - 1], nodes[b - 1]))
                    else:
                        triangles.append((nodes[a - 1], nodes[b - 1], nodes[c - 1]))
            explorer.Next()
        if triangles:
            outline = feature_edges(triangles) if edges else ()
            mesh = (tuple(triangles) if max_edge is None
                    else _subdivide_triangles(triangles, max_edge))
            meshes.append(MeshPart(part.name, mesh, outline))
    return meshes


def mesh_bounds(meshes: list[MeshPart]) -> tuple[tuple[float, float, float], float] | None:
    """Centre of the bounding box and radius of the enclosing sphere."""
    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []
    for mesh in meshes:
        for triangle in mesh.triangles:
            for point in triangle:
                xs.append(point[0])
                ys.append(point[1])
                zs.append(point[2])
    if not xs:
        return None
    center = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2)
    radius = math.sqrt(max((x - center[0]) ** 2 + (y - center[1]) ** 2
                           + (z - center[2]) ** 2 for x, y, z in zip(xs, ys, zs,
                                                                     strict=True)))
    return center, radius or 1.0


def keeps_framing(old_center: tuple[float, float, float], old_radius: float,
                   center: tuple[float, float, float], radius: float) -> bool:
    """Whether a model update can keep the camera target and scale.

    Small edits (a plate a bit thicker, one more bolt) should not make the
    view jump; the camera is refitted only when the new model would no longer
    fit, or would look much smaller than before.
    """
    return (math.dist(old_center, center) + radius <= 1.1 * old_radius
            and radius >= 0.6 * old_radius)


def y_up_to_z_up(meshes: list[MeshPart]) -> list[MeshPart]:
    """Rotate a y-up model (shear connections) so that z is vertical.

    (x, y, z) → (x, −z, y) is a rotation of +90° about x, not a reflection:
    the connection is shown as built (plates on their real side of the web,
    the skew in its real direction) and the triangle winding stays valid.
    """
    def turn(point):
        return (point[0], -point[2], point[1])

    return [MeshPart(mesh.name,
                     tuple((turn(p0), turn(p1), turn(p2)) for p0, p1, p2 in mesh.triangles),
                     tuple((turn(a), turn(b)) for a, b in mesh.edges))
            for mesh in meshes]


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

        def move(point, dx=dx, dy=dy, dz=dz):
            return (point[0] + dx, point[1] + dy, point[2] + dz)

        moved.append(MeshPart(
            mesh.name,
            tuple((move(p0), move(p1), move(p2)) for p0, p1, p2 in mesh.triangles),
            tuple((move(a), move(b)) for a, b in mesh.edges)))
    return moved


def _normal(p0: tuple[float, float, float], p1: tuple[float, float, float],
            p2: tuple[float, float, float]) -> tuple[float, float, float]:
    ax, ay, az = p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]
    bx, by, bz = p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2]
    nx, ny, nz = ay * bz - az * by, az * bx - ax * bz, ax * by - ay * bx
    length = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
    return nx / length, ny / length, nz / length


def cache_key(value: Any) -> str:
    """Cache key of a snapshot: the JSON of a pydantic model, else its repr."""
    dump = getattr(value, "model_dump_json", None)
    if callable(dump):
        try:
            return str(dump(exclude={"cases", "combinations", "generator"}))
        except Exception:
            return str(dump())
    return repr(value)
