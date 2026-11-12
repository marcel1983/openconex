# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Compressive strength of a single plate pushed by the beam (AISC 360-22 §J4.4).

When the axial force at the beam end is compression, the plate of a single-plate
connection is a cantilever from the weld: AISC Design Example II.A-19B
(Comments) takes K = 1.2 (Specification Commentary Table C-A-7.1, case (d)),
L = a, the distance from the weld to the (first) bolt line, and r = t/√12.
With L_c/r ≤ 25, P_n = F_y A_g (Eq. J4-6); otherwise Chapter E applies.
"""

from __future__ import annotations

import math

from openconex.core.checks import CheckResult
from openconex.core.loads import Method
from openconex.kernel import elements
from openconex.kernel.design import Calc
from openconex.units import Kind

__all__ = ["K_CANTILEVER", "plate_compression"]

K_CANTILEVER = 1.2
CLAUSE = "AISC 360-22 §J4.4; Commentary Table C-A-7.1(d); Design Example II.A-19B"


def plate_compression(prefix: str, length: float, thickness: float, a: float, Fy: float,
                      N: float, method: Method, combo: str = "") -> CheckResult:
    """Compression of the plate ``length × thickness`` with unbraced length ``a``."""
    c = Calc(method, combo)
    r = c.step("r", r"t/\sqrt{12}", thickness / math.sqrt(12), Kind.LENGTH, CLAUSE)
    slenderness = c.step(r"\frac{L_c}{r}", r"\frac{K a}{r}", K_CANTILEVER * a / r,
                         clause=CLAUSE, K=(K_CANTILEVER, Kind.DIMENSIONLESS),
                         a=(a, Kind.LENGTH))
    check = elements.compression(length * thickness, Fy, slenderness, N, method, combo)
    return check.model_copy(update={
        "id": f"{prefix}.compression", "text_id": f"check.{prefix}.compression",
        "clause": CLAUSE, "steps": tuple(c.steps) + check.steps})
