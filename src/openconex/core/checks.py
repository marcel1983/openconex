# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Design-check results and their calculation trace.

Every check returns a :class:`CheckResult`. Reports, the GUI and batch
summaries only *render* the trace; they never recompute anything.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, computed_field

from openconex.units import Kind

__all__ = ["CheckResult", "Status", "TraceStep", "governing"]


class Status(StrEnum):
    OK = "ok"
    NG = "ng"
    NOT_APPLICABLE = "n/a"


class TraceStep(BaseModel):
    """One line of the calculation: symbol = expression = value."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    """Symbol in LaTeX, e.g. ``\\phi R_n``."""
    expression: str = ""
    """Symbolic expression in LaTeX, e.g. ``0.75 F_u A_e``."""
    value: float
    """Result in internal units (see :mod:`openconex.units`)."""
    kind: Kind = Kind.DIMENSIONLESS
    clause: str = ""
    """Code reference, e.g. ``AISC 360-22 Eq. J4-2``."""
    inputs: dict[str, tuple[float, Kind]] = Field(default_factory=dict)
    """Values substituted into the expression (internal units)."""


class CheckResult(BaseModel):
    """Outcome of one design check for one load combination."""

    model_config = ConfigDict(frozen=True)

    id: str
    """Stable identifier, e.g. ``bolt.shear``."""
    text_id: str
    """Translation key for the check title (i18n catalogs)."""
    clause: str
    demand: float
    capacity: float
    kind: Kind
    combo: str = ""
    steps: tuple[TraceStep, ...] = ()
    applicable: bool = True
    ratio_limit: float = 1.0

    @computed_field
    @property
    def ratio(self) -> float:
        if not self.applicable:
            return 0.0
        if self.capacity <= 0.0:
            return float("inf") if self.demand > 0.0 else 0.0
        return abs(self.demand) / self.capacity

    @computed_field
    @property
    def status(self) -> Status:
        if not self.applicable:
            return Status.NOT_APPLICABLE
        return Status.OK if self.ratio <= self.ratio_limit else Status.NG


def governing(results: list[CheckResult]) -> CheckResult | None:
    """Return the applicable check with the highest ratio."""
    applicable = [r for r in results if r.applicable]
    return max(applicable, key=lambda r: r.ratio, default=None)
