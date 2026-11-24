# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Global optimization of an exposed base plate.

The search explores alternative anchor layouts (rod diameter and rods per row)
and, for each, the plate plan N × B and thickness tp. The edge distances of
the anchors to the plate edges are kept from the initial design, so the rods
move with the plate edges. A candidate is accepted only if every check of
every load combination passes (``Status.NG`` nowhere, including interference
and pedestal checks). The objective is the steel weight of the plate and the
anchor rods; ties are broken by N, B, tp and the rod diameter, so the result is
deterministic and reproducible.

The local mode (``optimize_base_plate`` in :mod:`.check`) only reduces N, B
and tp of the current layout, with the rods fixed; its result is also a
candidate of the global search, so the global result is never heavier than the
local one. Both are run by the CLI and the GUI through :func:`optimize`.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace

from openconex.core.checks import Status
from openconex.core.loads import Forces, LoadCombination
from openconex.core.model import BoltSpec, required
from openconex.units import Kind, to_internal

from .check import BasePlate, check_envelope, optimize_base_plate
from .interference import required_plate_edge

__all__ = [
    "STEEL_DENSITY",
    "Candidate",
    "OptimizationResult",
    "optimize",
    "optimize_global",
    "steel_weight",
]

STEEL_DENSITY = 7.85e-6
"""kg/mm³."""
STANDARD_RODS_IN = (0.75, 0.875, 1.0, 1.25, 1.5, 1.75, 2.0)
"""Common anchor rod diameters, AISC Manual Table 14-2 sizes [in]."""


@dataclass(frozen=True)
class Candidate:
    """One explored layout and the best plate found for it."""

    label: str
    rod_diameter: float
    rods_per_side: int
    N: float
    B: float
    tp: float
    ok: bool
    weight: float
    """Steel weight of the plate and rods [kg]."""
    governing: str = ""
    """Governing check id."""
    ratio: float = math.inf
    evaluations: int = 0


@dataclass(frozen=True)
class OptimizationResult:
    mode: str
    initial: BasePlate
    best: BasePlate
    trace: tuple[Candidate, ...]

    @property
    def improved(self) -> bool:
        return steel_weight(self.best) < steel_weight(self.initial) - 1e-9


def steel_weight(bp: BasePlate, grout: float = 38.1) -> float:
    """Weight of the plate and the anchor rods [kg]; rods run from h_ef to above the nut."""
    plate = bp.N * bp.B * bp.tp
    d = bp.rod.diameter
    length = (bp.hef or 12 * d) + grout + bp.tp + 3 * d
    rods = bp.rods * math.pi * d * d / 4 * length
    return (plate + rods) * STEEL_DENSITY


class _Evaluator:
    def __init__(self, combos: list[LoadCombination], case_forces: Mapping[str, Forces]):
        self.combos, self.case_forces = combos, case_forces
        self.count = 0
        self._cache: dict[tuple, tuple[bool, str, float]] = {}

    def __call__(self, bp: BasePlate) -> tuple[bool, str, float]:
        key = (round(bp.N, 6), round(bp.B, 6), round(bp.tp, 6), round(bp.f, 6),
               round(bp.rod_spacing, 6), round(bp.rod.diameter, 6), bp.rods_per_side)
        if key in self._cache:
            return self._cache[key]
        self.count += 1
        try:
            results, governing = check_envelope(bp, self.combos, self.case_forces)
        except ValueError:
            value = (False, "error", math.inf)
        else:
            ok = not any(r.status is Status.NG for r in results)
            worst = required(governing, "governing check")
            value = (ok, worst.id, worst.ratio)
        self._cache[key] = value
        return value


def _resize(bp: BasePlate, N: float, B: float, edge_N: float, edge_B: float) -> BasePlate:
    """Plate N × B with the rods at the initial edge distances."""
    spacing = max(B - 2 * edge_B, 0.0) if bp.rods_per_side > 1 else 0.0
    return replace(bp, N=N, B=B, f=max(N / 2 - edge_N, 0.0), rod_spacing=spacing)


def _snap(value: float, step: float) -> float:
    return math.ceil(value / step - 1e-9) * step


def _layout(bp: BasePlate, diameter: float, rods_per_side: int) -> BasePlate:
    rod = BoltSpec(diameter=diameter, grade=bp.rod.grade, bolts=bp.rod.bolts)
    return replace(bp, rod=rod, rods_per_side=rods_per_side)


def _descend(bp: BasePlate, passes: Callable[[BasePlate], bool], edge_N: float,
             edge_B: float, step: float,
             tp_step: float, min_plan: float, min_tp: float) -> BasePlate:
    """Coordinate descent on N, B and tp for one layout, from a feasible plate."""
    current = bp
    changed = True
    while changed:
        changed = False
        for name in ("N", "B", "tp"):
            increment = tp_step if name == "tp" else step
            limit = min_tp if name == "tp" else min_plan
            while getattr(current, name) - increment >= limit - 1e-9:
                if name == "tp":
                    trial = replace(current, tp=current.tp - increment)
                elif name == "N":
                    trial = _resize(current, current.N - increment, current.B, edge_N, edge_B)
                else:
                    trial = _resize(current, current.N, current.B - increment, edge_N, edge_B)
                if not passes(trial):
                    break
                current = trial
                changed = True
    return current


def optimize_global(bp: BasePlate, combinations: Iterable[LoadCombination],
                    case_forces: Mapping[str, Forces], *, step: float | None = None,
                    diameters: Iterable[float] | None = None,
                    rods_per_side: Iterable[int] | None = None,
                    max_growth: int = 24) -> OptimizationResult:
    """Lightest exposed base plate over anchor layouts and plate sizes.

    ``diameters`` defaults to the standard rod sizes from the current one up
    to 2 in, plus the current diameter; ``rods_per_side`` to the current
    count and 2 to 4 rods per row.
    """
    if bp.embedded_base is not None:
        raise ValueError("global optimization is only available for exposed base plates")
    combos = list(combinations)
    evaluate = _Evaluator(combos, case_forces)
    step = step or to_internal(1.0, "in", Kind.LENGTH)
    tp_step = to_internal(0.125, "in", Kind.THICKNESS)
    min_tp = to_internal(0.375, "in", Kind.THICKNESS)
    col = bp.column
    min_plan = max(col.d, col.bf) + 2 * step
    edge_N = bp.N / 2 - bp.f
    edge_B = (bp.B - bp.rod_spacing) / 2 if bp.rods_per_side > 1 else bp.B / 2

    if diameters is None:
        sizes = {to_internal(d, "in", Kind.LENGTH) for d in STANDARD_RODS_IN}
        diameters = sorted({d for d in sizes if d >= bp.rod.diameter - 1e-6}
                           | {bp.rod.diameter})
    if rods_per_side is None:
        rods_per_side = [1] if bp.rods_per_side == 1 else sorted({bp.rods_per_side, 2, 3, 4})
    layouts = [(d, k) for d in sorted(set(diameters)) for k in sorted(set(rods_per_side))]

    def passes(candidate: BasePlate) -> bool:
        return evaluate(candidate)[0]

    trace: list[Candidate] = []

    def record(label: str, plate: BasePlate, before: int) -> None:
        ok, governing, ratio = evaluate(plate)
        trace.append(Candidate(label, plate.rod.diameter, plate.rods_per_side, plate.N,
                               plate.B, plate.tp, ok, steel_weight(plate), governing, ratio,
                               evaluate.count - before))

    record("initial", bp, 0)
    feasible: list[BasePlate] = []
    if trace[0].ok:
        feasible.append(bp)
        before = evaluate.count
        local = optimize_base_plate(bp, combos, case_forces, step)
        record("local", local, before)
        feasible.append(local)
    for diameter, k in layouts:
        before = evaluate.count
        start = _layout(bp, diameter, k)
        need = required_plate_edge(start)
        e_N, e_B = max(edge_N, need), max(edge_B, need) if k > 1 else edge_B
        start = _resize(start, start.N, start.B, e_N, e_B)
        grow = 0
        while not passes(start) and grow < max_growth:
            grow += 1
            start = _resize(start, _snap(start.N + step, step), _snap(start.B + step, step),
                            e_N, e_B)
            start = replace(start, tp=max(start.tp, bp.tp) + (tp_step if grow % 2 else 0.0))
        if not passes(start):
            record(f"{k}×{_label(diameter)}", start, before)
            continue
        best = _descend(start, passes, e_N, e_B, step, tp_step, min_plan, min_tp)
        record(f"{k}×{_label(diameter)}", best, before)
        feasible.append(best)
    if not feasible:
        return OptimizationResult("global", bp, bp, tuple(trace))
    winner = min(feasible, key=lambda p: (round(steel_weight(p), 6), p.N, p.B, p.tp,
                                          p.rod.diameter, p.rods_per_side))
    return OptimizationResult("global", bp, winner, tuple(trace))


def _label(diameter: float) -> str:
    inches = diameter / 25.4
    return f"Ø{inches:g} in"


def optimize(bp: BasePlate, combinations: Iterable[LoadCombination],
             case_forces: Mapping[str, Forces], mode: str = "local") -> OptimizationResult:
    """Shared engine of the CLI and the GUI: ``local`` or ``global``."""
    combos = list(combinations)
    if mode == "global":
        return optimize_global(bp, combos, case_forces)
    if mode != "local":
        raise ValueError(f"unknown optimization mode {mode!r}; use 'local' or 'global'")
    if bp.embedded_base is not None:
        raise ValueError("optimization is only available for exposed base plates")
    best = optimize_base_plate(bp, combos, case_forces)
    evaluate = _Evaluator(combos, case_forces)
    trace = []
    for label, plate in (("initial", bp), ("local", best)):
        ok, governing, ratio = evaluate(plate)
        trace.append(Candidate(label, plate.rod.diameter, plate.rods_per_side, plate.N,
                               plate.B, plate.tp, ok, steel_weight(plate), governing, ratio))
    return OptimizationResult("local", bp, best, tuple(trace))
