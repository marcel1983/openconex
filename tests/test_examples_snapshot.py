# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Characterization test: the example projects give the recorded results.

Refactorings must not change any calculation. If a change is deliberate,
regenerate the reference with ``python tools/snapshot_examples.py`` and
review the diff of ``tests/reference/examples_snapshot.json``.
"""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "tests" / "reference" / "examples_snapshot.json"
REL_TOL = 1e-9
ABS_TOL = 1e-9
REGENERATE = "python tools/snapshot_examples.py"


def _tool():
    spec = importlib.util.spec_from_file_location(
        "openconex_snapshot_examples", ROOT / "tools" / "snapshot_examples.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TOOL = _tool()
RECORDED: dict[str, list[dict[str, object]]] = json.loads(REFERENCE.read_text(encoding="utf-8"))


def test_every_example_is_recorded():
    names = sorted(p.name for p in TOOL.EXAMPLES.glob("*.ocnx"))
    assert names == sorted(RECORDED), f"examples changed; run {REGENERATE}"


def _same(a: object, b: object) -> bool:
    if isinstance(a, float) and isinstance(b, float):
        if math.isinf(a) or math.isinf(b):
            return a == b
        return math.isclose(a, b, rel_tol=REL_TOL, abs_tol=ABS_TOL)
    return a == b


@pytest.mark.parametrize("name", sorted(RECORDED))
def test_example_results_unchanged(name: str):
    actual = TOOL.example_results(TOOL.EXAMPLES / name)
    expected = RECORDED[name]
    assert len(actual) == len(expected), (
        f"{name}: {len(actual)} results, recorded {len(expected)}; run {REGENERATE} "
        "if the change is deliberate")
    for i, (got, want) in enumerate(zip(actual, expected, strict=True)):
        diff = {key: (got[key], want[key]) for key in want if not _same(got[key], want[key])}
        assert not diff, (f"{name} result {i} ({want['id']}, {want['combo']}): "
                          f"(now, recorded) {diff}; run {REGENERATE} if deliberate")
