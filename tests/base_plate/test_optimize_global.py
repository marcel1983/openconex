# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Global optimization of exposed base plates (issue #62)."""

import itertools
from dataclasses import replace
from pathlib import Path

import pytest

from openconex.cli import main
from openconex.connections.base_plate.check import check_envelope
from openconex.connections.base_plate.optimize import (
    _resize,
    optimize,
    optimize_global,
    steel_weight,
)
from openconex.core.checks import Status
from openconex.io.project import load_project
from openconex.units import Kind, to_internal

EXAMPLES = Path(__file__).parents[2] / "examples"


def _inputs(name="base_plate_dg1_4_7_11.ocnx"):
    project = load_project(EXAMPLES / name)
    return project, project.base_plate_model(), project.load_combinations(), \
        project.case_forces()


def _passes(bp, combos, forces):
    results, _ = check_envelope(bp, combos, forces)
    return not any(r.status is Status.NG for r in results)


@pytest.mark.parametrize("name", [
    "base_plate_dg1_4_7_11.ocnx", "base_plate_shear_lug.ocnx", "base_plate_pedestal.ocnx",
    "base_plate_template_sap2000.ocnx", "base_plate_weak_base.ocnx"])
def test_global_result_passes_every_combination_and_is_not_heavier(name):
    _, bp, combos, forces = _inputs(name)
    result = optimize_global(bp, combos, forces)
    assert _passes(result.best, combos, forces)
    assert steel_weight(result.best) <= steel_weight(bp) + 1e-9
    local = optimize(bp, combos, forces, "local").best
    assert steel_weight(result.best) <= steel_weight(local) + 1e-9


def test_global_result_is_reproducible():
    _, bp, combos, forces = _inputs()
    first = optimize_global(bp, combos, forces)
    second = optimize_global(bp, combos, forces)
    assert first.best == second.best
    assert first.trace == second.trace


def test_global_explores_layouts_and_records_the_trace():
    _, bp, combos, forces = _inputs()
    result = optimize_global(bp, combos, forces)
    labels = [row.label for row in result.trace]
    assert labels[:2] == ["initial", "local"]
    assert len({(row.rod_diameter, row.rods_per_side) for row in result.trace}) > 5
    assert result.improved
    assert result.best.rod.diameter != bp.rod.diameter or \
        result.best.rods_per_side != bp.rods_per_side or result.best.N != bp.N


def test_global_optimum_matches_brute_force_on_a_small_grid():
    """Optimality: for one layout the descent finds the lightest feasible grid plate."""
    _, bp, combos, forces = _inputs()
    inch = to_internal(1, "in", Kind.LENGTH)
    eighth = to_internal(0.125, "in", Kind.THICKNESS)
    result = optimize_global(bp, combos, forces, diameters=[bp.rod.diameter],
                             rods_per_side=[2])
    edge_N, edge_B = bp.N / 2 - bp.f, (bp.B - bp.rod_spacing) / 2
    best = None
    for n, b, t in itertools.product(range(18, 25), range(16, 23), range(12, 17)):
        trial = replace(_resize(bp, n * inch, b * inch, edge_N, edge_B), tp=t * eighth)
        if _passes(trial, combos, forces):
            weight = steel_weight(trial)
            best = weight if best is None else min(best, weight)
    assert best is not None
    assert steel_weight(result.best) <= best + 1e-6


def test_global_rejects_embedded_bases():
    _, bp, combos, forces = _inputs("base_plate_embedded_base.ocnx")
    with pytest.raises(ValueError, match="exposed"):
        optimize(bp, combos, forces, "global")
    with pytest.raises(ValueError, match="mode"):
        optimize(bp, combos, forces, "random")


def test_cli_global_optimization_prints_trace_and_saves(tmp_path, capsys):
    target = tmp_path / "optimized.ocnx"
    assert main(["baseplate", str(EXAMPLES / "base_plate_dg1_4_7_11.ocnx"), "-o",
                 str(tmp_path / "out"), "--optimize", "global", "--save", str(target)]) == 0
    out = capsys.readouterr().out
    assert "layout" in out and "initial" in out and "Optimized:" in out
    project = load_project(target)
    bp = project.base_plate_model()
    assert _passes(bp, project.load_combinations(), project.case_forces())
    _, original, *_ = _inputs()
    assert steel_weight(bp) < steel_weight(original)
