# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
import pytest

from openconex.core.loads import (
    Forces,
    LoadCase,
    LoadCombination,
    LoadType,
    Method,
    SeismicParameters,
    asce7_combinations,
    combine,
)

CASES = [
    LoadCase(name="D", type=LoadType.DEAD),
    LoadCase(name="SD", type=LoadType.DEAD),
    LoadCase(name="L", type=LoadType.LIVE),
    LoadCase(name="Lr", type=LoadType.ROOF_LIVE),
    LoadCase(name="S", type=LoadType.SNOW),
    LoadCase(name="WX", type=LoadType.WIND),
    LoadCase(name="EX", type=LoadType.SEISMIC),
]


def _factors(combos):
    return [c.factors for c in combos]


def test_forces_arithmetic():
    f = Forces(P=10, V2=2) + Forces(P=5, M3=7) * 2
    assert f == Forces(P=20, V2=2, M3=14)
    assert 0.5 * Forces(P=4) == Forces(P=2)


def test_combine():
    combo = LoadCombination(name="c", method=Method.LRFD, factors={"D": 1.2, "L": 1.6})
    forces = {"D": Forces(P=100), "L": Forces(P=50, V2=10)}
    assert combine(combo, forces) == Forces(P=200, V2=16)
    with pytest.raises(KeyError):
        combine(combo, {"D": Forces()})


def test_lrfd_gravity_only():
    combos = asce7_combinations(CASES[:3])
    assert _factors(combos) == [
        {"D": 1.4, "SD": 1.4},
        {"D": 1.2, "SD": 1.2, "L": 1.6},
    ]
    assert combos[1].source == "ASCE 7-22 §2.3.1 (2)"


def test_lrfd_full_set():
    seismic = SeismicParameters(SDS=1.0, rho=1.3, omega0=3.0)
    combos = asce7_combinations(CASES, seismic=seismic)
    factors = _factors(combos)
    assert {"D": 1.2, "SD": 1.2, "L": 1.6, "Lr": 0.5} in factors
    # ASCE 7-22 snow is strength level: 0.3S / 1.0S instead of 0.5S / 1.6S
    assert {"D": 1.2, "SD": 1.2, "L": 1.6, "S": 0.3} in factors
    assert {"D": 1.2, "SD": 1.2, "S": 1.0, "WX": -0.5} in factors
    assert {"D": 1.2, "SD": 1.2, "Lr": 1.6, "WX": -0.5} in factors
    assert {"D": 1.2, "SD": 1.2, "WX": 1.0, "L": 1.0, "S": 0.3} in factors
    assert not any(f.get("S") in (0.5, 1.6) for f in factors)
    assert {"D": 0.9, "SD": 0.9, "WX": -1.0} in factors
    # 2.3.6 (6): (1.2 + 0.2 SDS) D + rho QE + L + 0.15 S
    assert {"D": 1.4, "SD": 1.4, "EX": 1.3, "L": 1.0, "S": 0.15} in factors
    # 2.3.6 (7) with overstrength: (0.9 - 0.2 SDS) D + Omega0 QE
    over = [c for c in combos if c.overstrength]
    assert {"D": 0.7, "SD": 0.7, "EX": -3.0} in _factors(over)
    assert all(c.seismic for c in over)
    assert len({tuple(sorted(f.items())) for f in factors}) == len(factors)


def test_live_factor_reduction():
    combos = asce7_combinations(CASES[:6], live_factor=0.5)
    assert {"D": 1.2, "SD": 1.2, "Lr": 1.6, "L": 0.5} in _factors(combos)
    assert {"D": 1.2, "SD": 1.2, "L": 1.6} not in _factors(combos)  # 1.6 L is never reduced
    assert {"D": 1.2, "SD": 1.2, "L": 1.6, "Lr": 0.5} in _factors(combos)


def test_asd_set():
    seismic = SeismicParameters(SDS=0.5)
    factors = _factors(asce7_combinations(CASES, Method.ASD, seismic))
    assert {"D": 1.0, "SD": 1.0, "L": 1.0} in factors
    assert {"D": 1.0, "SD": 1.0, "L": 0.75, "WX": 0.45, "Lr": 0.75} in factors
    assert {"D": 1.0, "SD": 1.0, "S": 0.7} in factors
    assert {"D": 1.0, "SD": 1.0, "L": 0.75, "S": 0.525} in factors
    assert {"D": 0.6, "SD": 0.6, "WX": -0.6} in factors
    assert {"D": 1.07, "SD": 1.07, "EX": 0.7} in factors
    assert {"D": 1.0525, "SD": 1.0525, "EX": -0.525, "L": 0.75, "S": 0.1} in factors
    assert {"D": 0.53, "SD": 0.53, "EX": 0.7} in factors


def test_no_seismic_without_parameters():
    assert not any(c.seismic for c in asce7_combinations(CASES))
