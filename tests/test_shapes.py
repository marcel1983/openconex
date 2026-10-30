# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Shape catalog: Excel -> SQL converter and SQLite loader.

Uses a small synthetic spreadsheet laid out like the AISC Shapes Database
(U.S. block followed by a metric block with the same column names).
"""

import sys
from pathlib import Path

import pytest

from openconex.core.shapes import ShapeDatabase, ShapeDatabaseError, normalize_label
from openconex.units import Kind, from_internal

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from build_shapes_db import convert

openpyxl = pytest.importorskip("openpyxl")

US_HEADER = ["Type", "EDI_Std_Nomenclature", "AISC_Manual_Label", "T_F", "W", "A", "d",
             "bf", "tw", "tf", "kdes", "Ix", "Zx", "Sx", "Cw", "bf/2tf", "tan(α)", "B", "b"]
ROWS = [
    ["W", "W14X90", "W14X90", "F", 90, 26.5, 14.0, 14.5, 0.44, 0.71, 1.31, 999, 157, 143,
     16000, 10.2, "–", "–", "–"],
    ["HSS", "HSS6X6X3/8", "HSS6X6X3/8", "T", 27.48, 7.58, "–", "–", "–", "–", "–", 39.5,
     23.2, 13.2, "–", "–", "–", 6.0, 4.95],
    ["L", "L4X4X1/2", "L4X4X1/2", "F", 12.8, 3.75, "–", "–", "–", "–", "–", 5.52, 3.94,
     1.96, "–", "–", 1.0, "–", 4.0],
]


@pytest.fixture
def db(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Database v16.0"
    metric = [c for c in US_HEADER if c not in {"Type", "T_F"}]
    ws.append(US_HEADER + metric)
    for row in ROWS:
        ws.append(row + ["999"] * len(metric))  # metric block must be ignored
    xlsx = tmp_path / "shapes.xlsx"
    wb.save(xlsx)
    out = tmp_path / "shapes.sql"
    assert convert(xlsx, out) == 3
    sql = out.read_text(encoding="utf-8")
    assert sql.startswith("-- AISC Shapes Database v16.0")
    return ShapeDatabase(sql)


def test_lookup_and_listing(db):
    assert len(db) == 3
    assert db.types() == ["HSS", "L", "W"]
    assert db.labels("W") == ["W14X90"]
    assert "w14x90" in db
    assert "W 14 X 90" in db
    assert "W99X1" not in db
    with pytest.raises(ShapeDatabaseError):
        db.get("W99X1")


def test_units_are_converted(db):
    w = db.get("W14X90")
    assert w.raw["d"] == 14.0
    assert w["d"] == pytest.approx(355.6)
    assert from_internal(w["A"], Kind.AREA, "in**2") == pytest.approx(26.5)
    assert from_internal(w["Ix"], Kind.MOMENT_OF_INERTIA, "in**4") == pytest.approx(999)
    assert from_internal(w["Zx"], Kind.SECTION_MODULUS, "in**3") == pytest.approx(157)
    assert w["Cw"] == pytest.approx(16000 * 25.4**6)
    assert w["W"] == pytest.approx(90 * 1.48816394, rel=1e-6)  # kg/m
    assert w["bf/2tf"] == pytest.approx(10.2)  # ratios unchanged
    assert w.properties["tan(α)"] is None  # dash -> NULL
    with pytest.raises(KeyError):
        w["tan(α)"]


def test_case_insensitive_header_collision(db):
    """SQLite column names ignore case: "B" and "b" must both survive."""
    hss = db.get("HSS6X6X3/8")
    assert hss.raw["B"] == 6.0
    assert hss.raw["b"] == 4.95
    assert hss["B"] == pytest.approx(152.4)


def test_to_ishape(db):
    shape = db.get("W14X90").to_ishape()
    assert shape.name == "W14X90"
    assert shape.tw == pytest.approx(0.44 * 25.4)
    assert shape.k_des == pytest.approx(1.31 * 25.4)
    with pytest.raises(ShapeDatabaseError):
        db.get("L4X4X1/2").to_ishape()


def test_normalize_label():
    assert normalize_label(" hss6 x6x3/8 ") == "HSS6X6X3/8"


def test_shipped_aisc_catalog():
    from openconex.core.shapes import aisc_shapes

    try:
        db = aisc_shapes()
    except ShapeDatabaseError:
        pytest.skip("aisc_v16.sql not generated")
    assert len(db) > 2000
    assert {"W", "M", "S", "HP", "C", "MC", "L", "WT", "2L", "HSS", "PIPE"} <= set(db.types())
    w = db.get("W44X408")  # values as listed in AISC Shapes Database v16.0
    assert w.raw["A"] == 120
    assert from_internal(w["d"], Kind.LENGTH, "in") == pytest.approx(44.8)
    assert from_internal(w["Ix"], Kind.MOMENT_OF_INERTIA, "in**4") == pytest.approx(38700)
    assert from_internal(w["Zx"], Kind.SECTION_MODULUS, "in**3") == pytest.approx(2000)
    assert w.to_ishape().tf == pytest.approx(2.17 * 25.4)
    hss = db.get(db.labels("HSS")[0])
    assert hss["B"] > 0 and hss["b"] > 0
