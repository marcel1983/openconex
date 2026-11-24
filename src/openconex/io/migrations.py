# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Upgrade older ``.ocnx`` files to the current format before validation.

Every format version is recorded in :data:`CHANGES`. A version that only adds
fields with a default needs no step: pydantic fills the default when an older
file is read. A version that renames a field, changes its meaning or its unit,
or removes it registers a function in :data:`STEPS` that rewrites the raw JSON
from the previous version, so old files keep giving the same results.

``load_project`` calls :func:`migrate`; ``tests/outputs/test_project.py``
fails if :data:`~openconex.io.project.FORMAT_VERSION` grows without an entry
in :data:`CHANGES`. See ``docs/tecnico/02-convenciones.md``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

__all__ = ["CHANGES", "FIRST_RECORDED", "STEPS", "migrate"]

Data = dict[str, Any]

FIRST_RECORDED = 9
"""Oldest version with example files in the repository. The repository history
starts at version 10 (2026-11-05); version 9 files hold only base plates and
load unchanged."""

CHANGES: dict[int, str] = {
    9: "base plates",
    10: "fields added: shear_connection (beam-end shear connections, F5)",
    11: "fields added: moment_connection (flange plate and welded flange moment "
        "connections, F6)",
    12: "fields added: moment end plates (AISC Design Guides 16 and 4), column "
        "stiffening (Design Guide 13) and the column_V/column_P load case fields",
    13: "fields added: AISC 358-22 seismic option of moment connections; base plate "
        "pedestal as a column and embedded base Type I/II (two parallel changes, "
        "both additive)",
    14: "fields added: splice (beam and column splices, F7)",
}
"""What each format version changed with respect to the previous one."""

STEPS: dict[int, Callable[[Data], Data]] = {}
"""``STEPS[n]`` rewrites a version ``n - 1`` file as version ``n``. Only for
versions whose change is not purely additive."""


def migrate(data: Data, target: int) -> Data:
    """Return ``data`` upgraded step by step to format ``target``.

    The ``format_version`` field is left as read: the project remembers the
    version it came from, and saving it writes the current one.
    """
    version = int(data.get("format_version", target))
    for step in range(version + 1, target + 1):
        upgrade = STEPS.get(step)
        if upgrade is not None:
            data = upgrade(data)
    return data
