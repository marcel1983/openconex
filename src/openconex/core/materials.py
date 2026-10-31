# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Material library (ASTM grades used with AISC 360-22).

Values are defined in the units of the source standard (ksi) and converted
once to internal units (MPa).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from openconex.units import Kind, to_internal

__all__ = ["BOLTS", "ELECTRODES", "STEELS", "BoltGrade", "SteelGrade", "WeldElectrode"]

E_STEEL = to_internal(29000.0, "ksi", Kind.STRESS)
"""Modulus of elasticity of steel, E = 29 000 ksi (AISC 360-22, Symbols)."""


def _ksi(value: float) -> float:
    return to_internal(value, "ksi", Kind.STRESS)


class SteelGrade(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    Fy: float
    """Specified minimum yield stress [MPa]."""
    Fu: float
    """Specified minimum tensile strength [MPa]."""
    E: float = E_STEEL


class BoltGrade(BaseModel):
    """High-strength bolt or anchor rod nominal stresses, AISC 360-22 Table J3.2."""

    model_config = ConfigDict(frozen=True)

    name: str
    Fnt: float
    """Nominal tensile stress [MPa]."""
    Fnv_N: float
    """Nominal shear stress, threads included in the shear plane [MPa]."""
    Fnv_X: float
    """Nominal shear stress, threads excluded from the shear plane [MPa]."""
    Fu: float
    """Specified minimum tensile strength [MPa]."""
    Fy: float | None = None
    """Specified minimum yield stress [MPa], when the grade defines one."""


class WeldElectrode(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    FEXX: float
    """Filler metal classification strength [MPa]."""


# Typical structural steels of AISC 360-22 Table 2-1 (Manual Part 2). Fy and
# Fu are the specified minimum values in ksi; E is the same for every grade.
STEELS: dict[str, SteelGrade] = {
    g.name: g
    for g in (
        SteelGrade(name="ASTM A36", Fy=_ksi(36), Fu=_ksi(58)),
        SteelGrade(name="ASTM A53 Gr. B", Fy=_ksi(35), Fu=_ksi(60)),
        SteelGrade(name="ASTM A500 Gr. B (rectangular)", Fy=_ksi(46), Fu=_ksi(58)),
        SteelGrade(name="ASTM A500 Gr. B (round)", Fy=_ksi(42), Fu=_ksi(58)),
        SteelGrade(name="ASTM A500 Gr. C (rectangular)", Fy=_ksi(50), Fu=_ksi(62)),
        SteelGrade(name="ASTM A500 Gr. C (round)", Fy=_ksi(46), Fu=_ksi(62)),
        SteelGrade(name="ASTM A501 Gr. A", Fy=_ksi(36), Fu=_ksi(58)),
        SteelGrade(name="ASTM A501 Gr. B", Fy=_ksi(50), Fu=_ksi(70)),
        SteelGrade(name="ASTM A529 Gr. 50", Fy=_ksi(50), Fu=_ksi(65)),
        SteelGrade(name="ASTM A529 Gr. 55", Fy=_ksi(55), Fu=_ksi(70)),
        SteelGrade(name="ASTM A572 Gr. 42", Fy=_ksi(42), Fu=_ksi(60)),
        SteelGrade(name="ASTM A572 Gr. 50", Fy=_ksi(50), Fu=_ksi(65)),
        SteelGrade(name="ASTM A572 Gr. 55", Fy=_ksi(55), Fu=_ksi(70)),
        SteelGrade(name="ASTM A572 Gr. 60", Fy=_ksi(60), Fu=_ksi(75)),
        SteelGrade(name="ASTM A572 Gr. 65", Fy=_ksi(65), Fu=_ksi(80)),
        SteelGrade(name="ASTM A588", Fy=_ksi(50), Fu=_ksi(70)),
        SteelGrade(name="ASTM A709 Gr. 36", Fy=_ksi(36), Fu=_ksi(58)),
        SteelGrade(name="ASTM A709 Gr. 50", Fy=_ksi(50), Fu=_ksi(65)),
        SteelGrade(name="ASTM A709 Gr. 50W", Fy=_ksi(50), Fu=_ksi(70)),
        SteelGrade(name="ASTM A847", Fy=_ksi(50), Fu=_ksi(70)),
        SteelGrade(name="ASTM A913 Gr. 50", Fy=_ksi(50), Fu=_ksi(65)),
        SteelGrade(name="ASTM A913 Gr. 60", Fy=_ksi(60), Fu=_ksi(75)),
        SteelGrade(name="ASTM A913 Gr. 65", Fy=_ksi(65), Fu=_ksi(80)),
        SteelGrade(name="ASTM A913 Gr. 70", Fy=_ksi(70), Fu=_ksi(90)),
        SteelGrade(name="ASTM A992", Fy=_ksi(50), Fu=_ksi(65)),
        SteelGrade(name="ASTM A1043 Gr. 36", Fy=_ksi(36), Fu=_ksi(58)),
        SteelGrade(name="ASTM A1043 Gr. 50", Fy=_ksi(50), Fu=_ksi(65)),
        SteelGrade(name="ASTM A1065 Gr. 50", Fy=_ksi(50), Fu=_ksi(60)),
        SteelGrade(name="ASTM A1065 Gr. 50W", Fy=_ksi(50), Fu=_ksi(70)),
        SteelGrade(name="ASTM A1085", Fy=_ksi(50), Fu=_ksi(65)),
    )
}

BOLTS: dict[str, BoltGrade] = {
    b.name: b
    for b in (
        # AISC 360-22 Table J3.2, Group 120 and Group 150.
        BoltGrade(name="ASTM F3125 Gr. A325", Fnt=_ksi(90), Fnv_N=_ksi(54), Fnv_X=_ksi(68),
                  Fu=_ksi(120)),
        BoltGrade(name="ASTM F3125 Gr. A490", Fnt=_ksi(113), Fnv_N=_ksi(68), Fnv_X=_ksi(84),
                  Fu=_ksi(150)),
        # Threaded parts (anchor rods): Fnt = 0.75 Fu, Fnv = 0.450 Fu (N) / 0.563 Fu (X).
        *(
            BoltGrade(name=f"ASTM F1554 Gr. {gr}", Fnt=_ksi(0.75 * fu), Fnv_N=_ksi(0.450 * fu),
                      Fnv_X=_ksi(0.563 * fu), Fu=_ksi(fu), Fy=_ksi(gr))
            for gr, fu in ((36, 58), (55, 75), (105, 125))
        ),
    )
}

ELECTRODES: dict[str, WeldElectrode] = {
    e.name: e for e in (WeldElectrode(name="E70XX", FEXX=_ksi(70)),
                        WeldElectrode(name="E80XX", FEXX=_ksi(80)))
}
