# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""AISC Design Guide 1 reference cases (tests/reference/dg1/*.toml).

Until the base plate module exists (phase F2) these tests only validate the
case files. Each case becomes an acceptance test when its ``status`` is set
to ``"implemented"``.
"""

import tomllib
from pathlib import Path

import pint
import pytest

from openconex.units import ureg

CASES_DIR = Path(__file__).parent / "reference" / "dg1"
CASES = sorted(CASES_DIR.glob("ex_*.toml"))
REQUIRED = {"id", "title", "source", "feature", "status", "given", "expected"}


def _load(path: Path) -> dict:
    with path.open("rb") as fh:
        return tomllib.load(fh)


def _expected_keys(case: dict) -> set[str]:
    keys = set()
    for key, value in case["expected"].items():
        if isinstance(value, dict):
            keys.update(value)
        else:
            keys.add(key)
    return keys


def _values(table: dict):
    for key, value in table.items():
        if isinstance(value, dict):
            yield from _values(value)
        else:
            yield key, value


def test_cases_exist():
    assert len(CASES) >= 11


@pytest.mark.parametrize("path", CASES, ids=lambda p: p.stem)
def test_case_format(path):
    case = _load(path)
    assert REQUIRED <= set(case), f"missing fields: {REQUIRED - set(case)}"
    assert path.stem == f"ex_{case['id']}"
    assert case["status"] in {"pending", "implemented"}
    assert case["source"].startswith("AISC DG1 3rd ed. (2024), Example " + case["id"])
    assert case["given"] and case["expected"]
    assert set(case["expected"]) - {"lrfd", "asd"} or case["expected"].get("lrfd")
    assert set(case.get("tolerances", {})) <= _expected_keys(case)


@pytest.mark.parametrize("path", CASES, ids=lambda p: p.stem)
def test_quantities_parse(path):
    """Every text value with a number must be a valid quantity with units."""
    case = _load(path)
    for section in ("given", "expected"):
        for key, value in _values(case[section]):
            if isinstance(value, str) and value.lstrip("-")[:1].isdigit():
                try:
                    ureg.Quantity(value)
                except (pint.UndefinedUnitError, pint.DimensionalityError, ValueError) as exc:
                    pytest.fail(f"{path.name}: {section}.{key} = {value!r}: {exc}")


@pytest.mark.parametrize("path", CASES, ids=lambda p: p.stem)
def test_load_sign_convention(path):
    """Axial loads: compression positive, uplift negative; LRFD >= ASD in magnitude."""
    given = _load(path)["given"]
    if "Pu" in given and "Pa" in given:
        pu, pa = ureg.Quantity(given["Pu"]), ureg.Quantity(given["Pa"])
        assert abs(pu) >= abs(pa)
        assert (pu.magnitude >= 0) == (pa.magnitude >= 0)
