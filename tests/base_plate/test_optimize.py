# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Optimization of exposed base plate dimensions."""

from dataclasses import replace
from pathlib import Path

from openconex.connections.base_plate.check import check_envelope, optimize_base_plate
from openconex.io.project import load_project
from openconex.units import Kind, from_internal

EXAMPLES = Path(__file__).parents[2] / "examples"


def _passes(bp, project):
    results, _ = check_envelope(bp, project.load_combinations(), project.case_forces())
    return not any(result.status.value == "ng" for result in results)


def test_optimize_reduces_an_oversized_plate():
    project = load_project(EXAMPLES / "base_plate_dg1_4_7_11.ocnx")
    bp = project.base_plate_model()
    oversized = replace(bp, N=bp.N * 1.5, B=bp.B * 1.5, tp=bp.tp * 2)
    optimized = optimize_base_plate(oversized, project.load_combinations(),
                                    project.case_forces())
    assert _passes(optimized, project)
    assert optimized.N * optimized.B * optimized.tp < \
        oversized.N * oversized.B * oversized.tp
    assert (optimized.N, optimized.B, optimized.tp) != (oversized.N, oversized.B, oversized.tp)


def test_optimize_keeps_a_valid_plate_valid():
    project = load_project(EXAMPLES / "base_plate_dg1_4_7_11.ocnx")
    bp = project.base_plate_model()
    optimized = optimize_base_plate(bp, project.load_combinations(), project.case_forces())
    assert _passes(optimized, project)
    assert from_internal(optimized.tp, Kind.THICKNESS, "in") >= 0.25
