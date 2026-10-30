# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""LRFD/ASD available strength and the calculation trace builder.

Every check in :mod:`openconex.kernel` records its intermediate values in a
:class:`Calc` and returns a :class:`~openconex.core.checks.CheckResult`, so
reports can show each equation with its substitution and code reference.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from openconex.core.checks import CheckResult, TraceStep
from openconex.core.loads import Method
from openconex.units import Kind

__all__ = ["Calc", "Method", "Resistance", "available"]

SPEC = "AISC 360-22"


@dataclass(frozen=True)
class Resistance:
    """Resistance factor φ (LRFD) and safety factor Ω (ASD) of a limit state."""

    phi: float
    omega: float


# Factors used by more than one module.
TENSION_YIELD = Resistance(0.90, 1.67)
TENSION_RUPTURE = Resistance(0.75, 2.00)
SHEAR_YIELD = Resistance(1.00, 1.50)
SHEAR_RUPTURE = Resistance(0.75, 2.00)
BOLT = Resistance(0.75, 2.00)
WELD = Resistance(0.75, 2.00)
FLEXURE = Resistance(0.90, 1.67)


def available(nominal: float, resistance: Resistance, method: Method) -> float:
    """φRn (LRFD) or Rn/Ω (ASD)."""
    if method is Method.LRFD:
        return resistance.phi * nominal
    return nominal / resistance.omega


@dataclass
class Calc:
    """Accumulates the trace of one check."""

    method: Method
    combo: str = ""
    steps: list[TraceStep] = field(default_factory=list)

    def step(
        self,
        symbol: str,
        expression: str,
        value: float,
        kind: Kind = Kind.DIMENSIONLESS,
        clause: str = "",
        **inputs: tuple[float, Kind],
    ) -> float:
        """Record ``symbol = expression = value`` and return ``value``."""
        self.steps.append(
            TraceStep(symbol=symbol, expression=expression, value=value, kind=kind,
                      clause=clause, inputs=inputs)
        )
        return value

    def available(self, nominal: float, resistance: Resistance, kind: Kind,
                  clause: str = "", symbol: str = "R_n") -> float:
        """Record and return φRn or Rn/Ω for the current method."""
        if self.method is Method.LRFD:
            return self.step(rf"\phi {symbol}", rf"{resistance.phi:g}\,{symbol}",
                             available(nominal, resistance, self.method), kind, clause)
        return self.step(rf"{symbol}/\Omega", rf"{symbol}/{resistance.omega:g}",
                         available(nominal, resistance, self.method), kind, clause)

    def result(
        self,
        check_id: str,
        clause: str,
        demand: float,
        capacity: float,
        kind: Kind,
        applicable: bool = True,
    ) -> CheckResult:
        return CheckResult(
            id=check_id, text_id=f"check.{check_id}", clause=clause, demand=demand,
            capacity=capacity, kind=kind, combo=self.combo, steps=tuple(self.steps),
            applicable=applicable,
        )
