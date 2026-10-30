# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Load cases, connection forces and ASCE 7-22 load combinations.

Sign convention of :class:`Forces` (local axes of the connection):
``P`` axial (+ compression), ``V2``/``V3`` shears, ``T`` torsion,
``M2``/``M3`` moments. Forces in N, moments in N·mm.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from enum import StrEnum
from itertools import product

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "Forces",
    "LoadCase",
    "LoadCombination",
    "LoadType",
    "Method",
    "SeismicParameters",
    "asce7_combinations",
    "combine",
]


class LoadType(StrEnum):
    DEAD = "D"
    LIVE = "L"
    ROOF_LIVE = "Lr"
    SNOW = "S"
    RAIN = "R"
    WIND = "W"
    SEISMIC = "E"
    """Horizontal seismic effect Q_E of one direction (before ρ or Ω0)."""


class Method(StrEnum):
    LRFD = "LRFD"
    ASD = "ASD"


class Forces(BaseModel):
    model_config = ConfigDict(frozen=True)

    P: float = 0.0
    V2: float = 0.0
    V3: float = 0.0
    T: float = 0.0
    M2: float = 0.0
    M3: float = 0.0

    def __add__(self, other: Forces) -> Forces:
        return Forces(**{k: v + getattr(other, k) for k, v in self})

    def __mul__(self, factor: float) -> Forces:
        return Forces(**{k: v * factor for k, v in self})

    __rmul__ = __mul__


class LoadCase(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    type: LoadType


class LoadCombination(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    method: Method
    factors: dict[str, float]
    """Factor applied to each load case, by case name."""
    seismic: bool = False
    overstrength: bool = False
    """True when the seismic effect is amplified by Ω0 (ASCE 7-22 §12.4.3)."""
    source: str = ""
    """Origin, e.g. ``ASCE 7-22 §2.3.1 (2)`` or ``imported``."""


class SeismicParameters(BaseModel):
    model_config = ConfigDict(frozen=True)

    SDS: float = Field(ge=0)
    rho: float = Field(default=1.0, ge=1.0)
    omega0: float | None = Field(default=None, ge=1.0)
    """Overstrength factor Ω0; when given, the Ω0 combinations are generated too."""


def combine(combo: LoadCombination, forces: Mapping[str, Forces]) -> Forces:
    """Factored forces of ``combo`` from the forces of each load case."""
    missing = set(combo.factors) - set(forces)
    if missing:
        raise KeyError(f"combination {combo.name} uses undefined cases: {sorted(missing)}")
    total = Forces()
    for case, factor in combo.factors.items():
        total = total + forces[case] * factor
    return total


# ---------------------------------------------------------------------------
# ASCE 7-22 combinations
# ---------------------------------------------------------------------------

# Each combination: (clause, required variable load, terms). A term is
# (case type, factor); "roof" is one of Lr, S or R at a time ("Lr or S or R"),
# "wind" one wind case with either sign, and "L*" the live load whose factor
# ASCE 7 allows to reduce to 0.5. A combination whose required variable load
# does not exist is skipped.
_LRFD = [
    ("2.3.1 (1)", None, [("D", 1.4)]),
    ("2.3.1 (2)", None, [("D", 1.2), ("L", 1.6), ("roof", 0.5)]),
    ("2.3.1 (3)", "roof", [("D", 1.2), ("roof", 1.6), ("L*", 1.0)]),
    ("2.3.1 (3)", "roof", [("D", 1.2), ("roof", 1.6), ("wind", 0.5)]),
    ("2.3.1 (4)", "wind", [("D", 1.2), ("wind", 1.0), ("L*", 1.0), ("roof", 0.5)]),
    ("2.3.1 (5)", "wind", [("D", 0.9), ("wind", 1.0)]),
]
_ASD = [
    ("2.4.1 (1)", None, [("D", 1.0)]),
    ("2.4.1 (2)", None, [("D", 1.0), ("L", 1.0)]),
    ("2.4.1 (3)", "roof", [("D", 1.0), ("roof", 1.0)]),
    ("2.4.1 (4)", None, [("D", 1.0), ("L", 0.75), ("roof", 0.75)]),
    ("2.4.1 (5)", "wind", [("D", 1.0), ("wind", 0.6)]),
    ("2.4.1 (6)", "wind", [("D", 1.0), ("L", 0.75), ("wind", 0.45), ("roof", 0.75)]),
    ("2.4.1 (7)", "wind", [("D", 0.6), ("wind", 0.6)]),
]
# Seismic: (clause, D factor, coefficient of SDS on D (Ev), Eh factor, other terms).
_LRFD_SEISMIC = [
    ("2.3.6 (6)", 1.2, 0.2, 1.0, [("L*", 1.0), ("S", 0.15)]),
    ("2.3.6 (7)", 0.9, -0.2, 1.0, []),
]
_ASD_SEISMIC = [
    ("2.4.5 (8)", 1.0, 0.14, 0.7, []),
    ("2.4.5 (9)", 1.0, 0.105, 0.525, [("L", 0.75), ("S", 0.75)]),
    ("2.4.5 (10)", 0.6, -0.14, 0.7, []),
]


def asce7_combinations(
    cases: Iterable[LoadCase],
    method: Method = Method.LRFD,
    seismic: SeismicParameters | None = None,
    live_factor: float = 1.0,
) -> list[LoadCombination]:
    """Generate the basic ASCE 7-22 combinations (§2.3 LRFD or §2.4 ASD).

    Each wind and seismic case is taken with both signs, and one roof load
    (Lr, S or R) at a time. All D cases share the D factor and all L cases the
    L factor. ``live_factor`` is the factor on L in LRFD combinations 3, 4
    and 6 (1.0, or 0.5 where ASCE 7-22 §2.3.1 permits).
    Duplicate combinations are removed.
    """
    cases = list(cases)
    by_type: dict[str, list[str]] = {t.value: [] for t in LoadType}
    for case in cases:
        by_type[case.type.value].append(case.name)
    roofs = by_type["Lr"] + by_type["S"] + by_type["R"]
    winds = [(name, sign) for name in by_type["W"] for sign in (1.0, -1.0)]
    quakes = [(name, sign) for name in by_type["E"] for sign in (1.0, -1.0)]

    combos: list[LoadCombination] = []
    seen: set[tuple] = set()

    def add(clause: str, factors: dict[str, float], tags: list[str], **kw) -> None:
        factors = {k: round(v, 10) for k, v in factors.items() if v != 0.0}
        key = (*sorted(factors.items()), kw.get("overstrength", False))
        if not factors or key in seen:
            return
        seen.add(key)
        label = f"{method.value}-{len(combos) + 1}"
        name = f"{label} {' '.join(tags)}".strip()
        combos.append(LoadCombination(name=name, method=method, factors=factors,
                                      source=f"ASCE 7-22 §{clause}", **kw))

    def put(factors: dict[str, float], names: list[str], value: float) -> None:
        for n in names:
            factors[n] = factors.get(n, 0.0) + value

    for clause, required, terms in _LRFD if method is Method.LRFD else _ASD:
        types = {t for t, _ in terms}
        if (required == "roof" and not roofs) or (required == "wind" and not winds):
            continue
        roof_options = roofs if "roof" in types and roofs else [None]
        wind_options = winds if "wind" in types else [None]
        for roof, wind in product(roof_options, wind_options):
            factors: dict[str, float] = {}
            tags: list[str] = []
            for kind, factor in terms:
                if kind == "roof":
                    if roof:
                        put(factors, [roof], factor)
                        tags.append(roof)
                elif kind == "wind":
                    name, sign = wind
                    put(factors, [name], sign * factor)
                    tags.append(("+" if sign > 0 else "-") + name)
                elif kind == "L*":
                    put(factors, by_type["L"], factor * live_factor)
                else:
                    put(factors, by_type[kind], factor)
            add(clause, factors, tags)

    if seismic is not None and quakes:
        table = _LRFD_SEISMIC if method is Method.LRFD else _ASD_SEISMIC
        amplifications = [(seismic.rho, False)]
        if seismic.omega0 is not None:
            amplifications.append((seismic.omega0, True))
        for (clause, d, ev, eh, others), (amp, over), (quake, sign) in product(
            table, amplifications, quakes
        ):
            factors = {}
            put(factors, by_type["D"], d + ev * seismic.SDS)
            put(factors, [quake], sign * eh * amp)
            for kind, factor in others:
                f = factor * live_factor if kind == "L*" else factor
                put(factors, by_type["L" if kind == "L*" else kind], f)
            tags = [("+" if sign > 0 else "-") + quake] + (["Ω0"] if over else [])
            add(clause, factors, tags, seismic=True, overstrength=over)

    return combos
