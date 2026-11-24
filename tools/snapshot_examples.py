# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Record the check results of every example project.

``tests/test_examples_snapshot.py`` recomputes each project in ``examples/``
and compares every :class:`~openconex.core.checks.CheckResult` (identifier,
combination, clause, demand, capacity, status) with the file written here.
A refactoring that moves a single number makes the test fail; a deliberate
change of the calculation regenerates the file and the diff shows what moved.

Run from the repository root::

    python tools/snapshot_examples.py

The output is ``tests/reference/examples_snapshot.json``.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
OUTPUT = ROOT / "tests" / "reference" / "examples_snapshot.json"


def example_results(path: Path) -> list[dict[str, object]]:
    """Every check result of one example project, in report order."""
    from openconex.io.project import load_project
    from openconex.report.builder import build_report

    report = build_report(load_project(path), dt.date(2026, 1, 1))
    return [
        {"id": r.id, "combo": r.combo, "clause": r.clause, "demand": r.demand,
         "capacity": r.capacity, "ratio_limit": r.ratio_limit, "status": r.status.value}
        for r in report.results
    ]


def snapshot() -> dict[str, list[dict[str, object]]]:
    """Results of all the projects in ``examples/``, keyed by file name."""
    return {path.name: example_results(path) for path in sorted(EXAMPLES.glob("*.ocnx"))}


def main() -> int:
    data = snapshot()
    # One result per line: a deliberate change shows up as a readable diff.
    blocks = []
    for name, rows in data.items():
        lines = ",\n".join(f"  {json.dumps(row, ensure_ascii=False)}" for row in rows)
        blocks.append(f" {json.dumps(name)}: [\n{lines}\n ]")
    OUTPUT.write_text("{\n" + ",\n".join(blocks) + "\n}\n", encoding="utf-8")
    count = sum(len(rows) for rows in data.values())
    print(f"{OUTPUT.relative_to(ROOT)}: {len(data)} projects, {count} results")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
