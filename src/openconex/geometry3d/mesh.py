# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Triangulated meshes from OpenCASCADE parts for the 3D viewer."""

from __future__ import annotations

import math
from dataclasses import dataclass

from openconex.geometry3d.base_plate import Part

__all__ = ["MeshPart", "tessellate_parts"]

Point = tuple[float, float, float]
Triangle = tuple[Point, Point, Point]

# Large planar faces are only two triangles.  The painter's algorithm sorts by
# triangle depth, so a huge face can be drawn over a nearer small part.  Split
# long triangles to keep the depth comparison local.  The viewer uses the
# default (interactive); the gallery asks for a finer 25 mm mesh.
MAX_EDGE = 40.0


@dataclass(frozen=True)
class MeshPart:
    name: str
    triangles: tuple[Triangle, ...]


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


def _subdivide_triangles(triangles: list[Triangle],
                         max_edge: float) -> tuple[Triangle, ...]:
    return tuple(part for triangle in triangles
                 for part in _subdivide(triangle, max_edge))


def tessellate_parts(parts: list[Part], deflection: float = 0.35,
                     max_edge: float = MAX_EDGE) -> list[MeshPart]:
    """Triangulate every part; faces without a mesh are skipped."""
    from OCP.BRep import BRep_Tool
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopLoc import TopLoc_Location
    from OCP.TopoDS import TopoDS

    meshes: list[MeshPart] = []
    for part in parts:
        BRepMesh_IncrementalMesh(part.shape, deflection)
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
            meshes.append(MeshPart(part.name,
                                   _subdivide_triangles(triangles, max_edge)))
    return meshes
