# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Steel shape catalog (AISC Shapes Database) stored as SQL and loaded into SQLite.

The SQL file keeps the values as published by AISC (U.S. customary units);
:class:`Section` exposes them in internal units (mm, mm², mm³, mm⁴, mm⁶, kg/m).
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from importlib import resources
from pathlib import Path

from openconex.core.materials import SteelGrade
from openconex.core.model import IShape
from openconex.units import ureg

__all__ = ["DEFAULT_SQL", "Section", "ShapeDatabase", "ShapeDatabaseError", "aisc_shapes"]

DEFAULT_SQL = "aisc_v16.sql"

_LENGTH = (
    "d ddet Ht h OD bf bfdet B b ID tw twdet tf tfdet t tnom tdes kdes kdet k1 x y eo xp yp "
    "rx ry rz ro rts ho T WGi WGo PA PA2 PB PC PD zA zB zC wA wB wC"
).split()
_AREA = ["A", "Wno"]
_MODULUS = "Zx Sx Zy Sy Sz C Qf Qw SwA SwB SwC SzA SzB SzC".split()
_INERTIA = ["Ix", "Iy", "Iz", "J", "Iw", "Sw1"]

# Source unit -> internal unit, per column. Other numeric columns are ratios.
_CONVERSION: dict[str, tuple[str, str]] = {
    **{c: ("in", "mm") for c in _LENGTH},
    **{c: ("in**2", "mm**2") for c in _AREA},
    **{c: ("in**3", "mm**3") for c in _MODULUS},
    **{c: ("in**4", "mm**4") for c in _INERTIA},
    "Cw": ("in**6", "mm**6"),
    "Sw2": ("in**4", "mm**4"),
    "Sw3": ("in**4", "mm**4"),
    "W": ("lb/ft", "kg/m"),
}
_TEXT = {"Type", "EDI_Std_Nomenclature", "AISC_Manual_Label", "T_F"}
_I_SHAPES = {"W", "M", "S", "HP"}


@cache
def _factor(source: str, target: str) -> float:
    return float(ureg.Quantity(1.0, source).to(target).magnitude)


class ShapeDatabaseError(LookupError):
    """Missing catalog file or unknown shape."""


def normalize_label(label: str) -> str:
    """``'w14x90'``, ``'W 14 X 90'`` -> ``'W14X90'``."""
    return re.sub(r"\s+", "", label).upper()


@dataclass(frozen=True)
class Section:
    label: str
    type: str
    properties: dict[str, float | None]
    """Numeric properties in internal units, keyed by spreadsheet header (``"bf/2tf"``)."""
    raw: dict[str, object]
    """Row as published by AISC (U.S. customary units), keyed by spreadsheet header."""

    def __getitem__(self, key: str) -> float:
        value = self.properties.get(key)
        if value is None:
            raise KeyError(f"{self.label} has no property {key!r}")
        return value

    def to_ishape(self, grade: str = "ASTM A992",
                  materials: Mapping[str, SteelGrade] | None = None) -> IShape:
        if self.type not in _I_SHAPES:
            raise ShapeDatabaseError(f"{self.label} ({self.type}) is not an I-shape")
        p = self.properties
        return IShape(name=self.label, d=self["d"], bf=self["bf"], tf=self["tf"],
                      tw=self["tw"], k_des=p.get("kdes") or 0.0, grade=grade,
                      materials=materials or {})


class ShapeDatabase:
    """In-memory SQLite catalog of steel shapes."""

    def __init__(self, sql: str) -> None:
        self._db = sqlite3.connect(":memory:", check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.executescript(sql)
        self._db.execute(
            "CREATE INDEX IF NOT EXISTS shapes_norm ON shapes "
            "(upper(replace(AISC_Manual_Label, ' ', '')))"
        )
        has_map = self._db.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'columns'"
        ).fetchone()
        # SQL column name -> spreadsheet header (e.g. "bf_2tf" -> "bf/2tf", "b_2" -> "b").
        self._headers: dict[str, str] = (
            dict(self._db.execute("SELECT name, header FROM columns")) if has_map else {}
        )

    @classmethod
    def from_file(cls, path: str | Path) -> ShapeDatabase:
        return cls(Path(path).read_text(encoding="utf-8"))

    def types(self) -> list[str]:
        rows = self._db.execute("SELECT DISTINCT Type FROM shapes ORDER BY Type")
        return [r[0] for r in rows]

    def labels(self, shape_type: str | None = None) -> list[str]:
        if shape_type is None:
            rows = self._db.execute("SELECT AISC_Manual_Label FROM shapes ORDER BY rowid")
        else:
            rows = self._db.execute(
                "SELECT AISC_Manual_Label FROM shapes WHERE Type = ? ORDER BY rowid",
                (shape_type,),
            )
        return [r[0] for r in rows]

    def __contains__(self, label: str) -> bool:
        return self._row(label) is not None

    def __len__(self) -> int:
        return self._db.execute("SELECT count(*) FROM shapes").fetchone()[0]

    def _row(self, label: str) -> sqlite3.Row | None:
        return self._db.execute(
            "SELECT * FROM shapes WHERE upper(replace(AISC_Manual_Label, ' ', '')) = ?",
            (normalize_label(label),),
        ).fetchone()

    def get(self, label: str) -> Section:
        row = self._row(label)
        if row is None:
            raise ShapeDatabaseError(f"shape not found: {label}")
        raw = {self._headers.get(k, k): v for k, v in dict(row).items()}
        props: dict[str, float | None] = {}
        for key, value in raw.items():
            if key in _TEXT:
                continue
            if value is None or isinstance(value, str):
                props[key] = None
                continue
            conversion = _CONVERSION.get(key)
            props[key] = float(value) * _factor(*conversion) if conversion else float(value)
        return Section(label=raw["AISC_Manual_Label"], type=raw["Type"], properties=props,
                       raw=raw)


@cache
def aisc_shapes() -> ShapeDatabase:
    """The AISC catalog shipped with OpenConex."""
    path = resources.files("openconex.data").joinpath("shapes", DEFAULT_SQL)
    if not path.is_file():
        raise ShapeDatabaseError(
            f"shape catalog {DEFAULT_SQL} is not installed; build it with "
            "tools/build_shapes_db.py from the AISC Shapes Database spreadsheet"
        )
    return ShapeDatabase(path.read_text(encoding="utf-8"))
