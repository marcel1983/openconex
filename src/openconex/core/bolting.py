# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Bolt detailing data from AISC 360-22 §J3 (U.S. customary bolt sizes).

Tables are stored in inches as in the specification and converted to internal
units (mm, N) by the accessor functions.
"""

from __future__ import annotations

import math
from enum import StrEnum
from fractions import Fraction as Fr

from openconex.units import Kind, to_internal

__all__ = [
    "BOLT_DIAMETERS_IN",
    "HoleType",
    "bolt_area",
    "hole_size",
    "min_edge_distance",
    "min_pretension",
    "min_spacing",
]


class HoleType(StrEnum):
    STANDARD = "STD"
    OVERSIZED = "OVS"
    SHORT_SLOT = "SSL"
    LONG_SLOT = "LSL"


BOLT_DIAMETERS_IN: tuple[Fr, ...] = (
    Fr(1, 2), Fr(5, 8), Fr(3, 4), Fr(7, 8), Fr(1), Fr(9, 8), Fr(5, 4), Fr(11, 8), Fr(3, 2),
)

# Table J3.3 — nominal hole dimensions [in]: (width, length); slots list both.
_HOLES: dict[Fr, dict[HoleType, tuple[Fr, Fr]]] = {
    Fr(1, 2): {HoleType.STANDARD: (Fr(9, 16),) * 2, HoleType.OVERSIZED: (Fr(5, 8),) * 2,
               HoleType.SHORT_SLOT: (Fr(9, 16), Fr(11, 16)),
               HoleType.LONG_SLOT: (Fr(9, 16), Fr(5, 4))},
    Fr(5, 8): {HoleType.STANDARD: (Fr(11, 16),) * 2, HoleType.OVERSIZED: (Fr(13, 16),) * 2,
               HoleType.SHORT_SLOT: (Fr(11, 16), Fr(7, 8)),
               HoleType.LONG_SLOT: (Fr(11, 16), Fr(25, 16))},
    Fr(3, 4): {HoleType.STANDARD: (Fr(13, 16),) * 2, HoleType.OVERSIZED: (Fr(15, 16),) * 2,
               HoleType.SHORT_SLOT: (Fr(13, 16), Fr(1)),
               HoleType.LONG_SLOT: (Fr(13, 16), Fr(15, 8))},
    Fr(7, 8): {HoleType.STANDARD: (Fr(15, 16),) * 2, HoleType.OVERSIZED: (Fr(17, 16),) * 2,
               HoleType.SHORT_SLOT: (Fr(15, 16), Fr(9, 8)),
               HoleType.LONG_SLOT: (Fr(15, 16), Fr(35, 16))},
    Fr(1): {HoleType.STANDARD: (Fr(9, 8),) * 2, HoleType.OVERSIZED: (Fr(5, 4),) * 2,
            HoleType.SHORT_SLOT: (Fr(9, 8), Fr(21, 16)),
            HoleType.LONG_SLOT: (Fr(9, 8), Fr(5, 2))},
}

# Table J3.4 — minimum edge distance from center of standard hole to edge [in].
_EDGE: dict[Fr, Fr] = {
    Fr(1, 2): Fr(3, 4), Fr(5, 8): Fr(7, 8), Fr(3, 4): Fr(1), Fr(7, 8): Fr(9, 8),
    Fr(1): Fr(5, 4), Fr(9, 8): Fr(3, 2), Fr(5, 4): Fr(13, 8),
}

# Table J3.1 — minimum bolt pretension [kips]: (Group 120 / A325, Group 150 / A490).
_PRETENSION: dict[Fr, tuple[int, int]] = {
    Fr(1, 2): (12, 15), Fr(5, 8): (19, 24), Fr(3, 4): (28, 35), Fr(7, 8): (39, 49),
    Fr(1): (51, 64), Fr(9, 8): (64, 80), Fr(5, 4): (81, 102), Fr(11, 8): (97, 121),
    Fr(3, 2): (118, 148),
}


def _inch(d_in: Fr) -> float:
    return to_internal(float(d_in), "in", Kind.LENGTH)


def _as_fraction(d_in: float | Fr) -> Fr:
    frac = Fr(d_in).limit_denominator(64)
    if frac <= 0:
        raise ValueError(f"bolt diameter must be positive: {d_in}")
    return frac


def bolt_area(d: float) -> float:
    """Nominal unthreaded body area A_b = π d²/4 [mm²] for diameter ``d`` [mm]."""
    return math.pi * d * d / 4.0


def hole_size(d_in: float | Fr, hole: HoleType = HoleType.STANDARD) -> tuple[float, float]:
    """Nominal hole (width, length) [mm] for a bolt of diameter ``d_in`` [in], Table J3.3."""
    d = _as_fraction(d_in)
    if d in _HOLES:
        width, length = _HOLES[d][hole]
    elif d >= Fr(9, 8):
        width, length = {
            HoleType.STANDARD: (d + Fr(1, 8), d + Fr(1, 8)),
            HoleType.OVERSIZED: (d + Fr(5, 16), d + Fr(5, 16)),
            HoleType.SHORT_SLOT: (d + Fr(1, 8), d + Fr(3, 8)),
            HoleType.LONG_SLOT: (d + Fr(1, 8), Fr(5, 2) * d),
        }[hole]
    else:
        raise ValueError(f"no Table J3.3 entry for a {d} in bolt")
    return _inch(width), _inch(length)


def min_edge_distance(d_in: float | Fr) -> float:
    """Minimum edge distance [mm] for a standard hole, Table J3.4."""
    d = _as_fraction(d_in)
    if d in _EDGE:
        return _inch(_EDGE[d])
    if d > Fr(5, 4):
        return _inch(Fr(5, 4) * d)
    raise ValueError(f"no Table J3.4 entry for a {d} in bolt")


def min_spacing(d: float) -> float:
    """Minimum center-to-center spacing 2⅔ d [mm] (AISC 360-22 §J3.3); 3d is preferred."""
    return 8.0 * d / 3.0


def min_pretension(d_in: float | Fr, group: int = 120) -> float:
    """Minimum bolt pretension T_b [N], Table J3.1 (group 120 = A325, 150 = A490)."""
    d = _as_fraction(d_in)
    if d not in _PRETENSION:
        raise ValueError(f"no Table J3.1 entry for a {d} in bolt")
    kips = _PRETENSION[d][{120: 0, 150: 1}[group]]
    return to_internal(kips, "kip", Kind.FORCE)


# AISC Manual 16th ed., Table 14-2: recommended anchor rod hole and plate washer
# sizes in base plates [in.]: diameter -> (hole, washer size, min. washer thickness).
_BASE_PLATE_HOLES: dict[Fr, tuple[Fr, Fr, Fr]] = {
    Fr(3, 4): (Fr(21, 16), Fr(2), Fr(1, 4)),
    Fr(7, 8): (Fr(25, 16), Fr(5, 2), Fr(5, 16)),
    Fr(1): (Fr(15, 8), Fr(3), Fr(3, 8)),
    Fr(5, 4): (Fr(17, 8), Fr(7, 2), Fr(1, 2)),
    Fr(3, 2): (Fr(19, 8), Fr(4), Fr(1, 2)),
    Fr(7, 4): (Fr(23, 8), Fr(9, 2), Fr(5, 8)),
    Fr(2): (Fr(13, 4), Fr(5), Fr(3, 4)),
    Fr(5, 2): (Fr(15, 4), Fr(11, 2), Fr(7, 8)),
}


def base_plate_hole(d_in: float | Fr) -> tuple[float, float, float]:
    """Recommended (hole diameter, washer size, minimum washer thickness) [mm] for an
    anchor rod of diameter ``d_in`` [in.] in a base plate (AISC Manual Table 14-2).

    Circular or square washers of the given size are acceptable.
    """
    d = _as_fraction(d_in)
    if d not in _BASE_PLATE_HOLES:
        raise ValueError(f"no AISC Manual Table 14-2 entry for a {d} in. anchor rod")
    return tuple(_inch(v) for v in _BASE_PLATE_HOLES[d])
