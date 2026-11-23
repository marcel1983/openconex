# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Scene math of the 3D viewer: pure Python, no Qt or OpenCASCADE needed."""

import pytest

from openconex.geometry3d.mesh import (
    MeshPart,
    _explode_meshes,
    _normal,
    _swap_yz_meshes,
    cache_key,
    feature_edges,
    keeps_framing,
    mesh_bounds,
    subdivide_meshes,
    y_up_to_z_up,
)

A, B, C, D = (0.0, 0.0, 0.0), (100.0, 0.0, 0.0), (100.0, 100.0, 0.0), (0.0, 100.0, 0.0)


def _cube(size: float = 1.0) -> list:
    s = size
    p = [(x * s, y * s, z * s) for x in (0, 1) for y in (0, 1) for z in (0, 1)]
    quads = [(0, 2, 6, 4), (1, 5, 7, 3), (0, 4, 5, 1), (2, 3, 7, 6), (0, 1, 3, 2), (4, 6, 7, 5)]
    tris = []
    for a, b, c, d in quads:
        tris += [(p[a], p[b], p[c]), (p[a], p[c], p[d])]
    return tris


def test_cube_has_twelve_feature_edges_and_outward_normals():
    triangles = _cube(10.0)
    assert len(feature_edges(triangles)) == 12
    for tri in triangles:
        n = _normal(*tri)
        mid = [sum(p[i] for p in tri) / 3 - 5.0 for i in range(3)]
        assert sum(a * b for a, b in zip(n, mid, strict=True)) > 0


def test_square_outline_without_diagonal():
    edges = feature_edges([(A, B, C), (A, C, D)])
    assert len(edges) == 4
    assert all({e[0], e[1]} != {A, C} for e in edges)
    assert feature_edges([(A, A, B)]) == ()  # degenerate triangles are ignored


def test_subdivision_keeps_area_winding_and_edges():
    mesh = MeshPart("plate", ((A, B, C),), ((A, B),))
    split = subdivide_meshes([mesh], max_edge=40.0)[0]
    assert len(split.triangles) > 1 and split.edges == mesh.edges
    assert all(max(abs(p[0] - q[0]) + abs(p[1] - q[1]) for p, q in
                   ((t[0], t[1]), (t[1], t[2]), (t[2], t[0]))) <= 80.0
               for t in split.triangles)
    assert all(_normal(*t) == pytest.approx((0.0, 0.0, 1.0)) for t in split.triangles)


def test_y_up_rotation_and_reflection():
    face = MeshPart("plate", (((0.0, 0.0, 1.0), (1.0, 0.0, 1.0), (0.0, 1.0, 1.0)),),
                    (((0.0, 0.0, 1.0), (1.0, 0.0, 1.0)),))
    turned = y_up_to_z_up([face])[0]
    assert turned.triangles[0][1] == (1.0, -1.0, 0.0)
    assert turned.edges[0][1] == (1.0, -1.0, 0.0)
    assert _normal(*turned.triangles[0]) == pytest.approx((0.0, -1.0, 0.0))
    # The gallery's y↔z swap is a reflection: it flips the winding to compensate.
    swapped = _swap_yz_meshes([face])[0]
    assert _normal(*swapped.triangles[0]) == pytest.approx((0.0, 1.0, 0.0))


def test_explode_moves_triangles_and_edges():
    mesh = MeshPart("support_bolt1a", ((A, B, C),), ((A, B),))
    moved = _explode_meshes([mesh], {"support_bolt*": (0.0, 0.0, 5.0)})[0]
    assert moved.triangles[0][0] == (0.0, 0.0, 5.0)
    assert moved.edges[0][1] == (100.0, 0.0, 5.0)
    assert _explode_meshes([mesh], None) == [mesh]
    assert _explode_meshes([mesh], {"beam": (1.0, 0.0, 0.0)}) == [mesh]


def test_bounds_and_framing():
    assert mesh_bounds([]) is None
    center, radius = mesh_bounds([MeshPart("cube", tuple(_cube(2.0)))])
    assert center == (1.0, 1.0, 1.0)
    assert radius == pytest.approx(3 ** 0.5)
    assert keeps_framing(center, radius, (1.05, 1.0, 1.0), radius * 0.95)
    assert not keeps_framing(center, radius, center, radius * 1.5)  # no longer fits
    assert not keeps_framing(center, radius, center, radius * 0.3)  # much smaller


def test_cache_key_ignores_loads():
    class Model:
        def model_dump_json(self, exclude=None):
            return "geometry" if exclude and "cases" in exclude else "everything"

    assert cache_key(Model()) == "geometry"
    assert cache_key(12.5) == "12.5"
