# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Triangulated meshes from OpenCASCADE parts for the 3D viewer."""

from __future__ import annotations

from dataclasses import dataclass

from openconex.geometry3d.base_plate import Part

__all__ = ["MeshPart", "tessellate_parts"]

Point = tuple[float, float, float]
Triangle = tuple[Point, Point, Point]


@dataclass(frozen=True)
class MeshPart:
    name: str
    triangles: tuple[Triangle, ...]


def tessellate_parts(parts: list[Part], deflection: float = 0.5) -> list[MeshPart]:
    """Triangulate every part; faces without a mesh are skipped."""
    from OCP.BRep import BRep_Tool
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.TopAbs import TopAbs_FACE
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
                    triangles.append((nodes[a - 1], nodes[b - 1], nodes[c - 1]))
            explorer.Next()
        if triangles:
            meshes.append(MeshPart(part.name, tuple(triangles)))
    return meshes
