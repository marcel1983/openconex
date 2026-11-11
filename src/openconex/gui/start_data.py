# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Connection families, subtypes and starter projects for the gallery.

The gallery is a UI layer: it only builds a valid :class:`Project` with sensible
defaults and then opens the existing editor.  The calculation engine is not
touched.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from openconex.io.project import Project

BASE_PLATE_EXPOSED: dict[str, Any] = {
    "info": {"name": "Placa base expuesta", "language": "es", "units": "US"},
    "base_plate": {
        "column": "W14X90", "column_grade": "ASTM A992",
        "plate_grade": "ASTM A572 Gr. 50",
        "N": "24 in", "B": "22 in", "tp": "1.5 in", "fc": "4 ksi",
        "A2_over_A1": 1.0, "grout": "1.5 in", "rod_diameter": "3/4 in",
        "rod_grade": "ASTM F1554 Gr. 36", "rods_per_side": 2,
        "f": "9 in", "rod_spacing": "12 in", "hef": "18 in",
    },
    "cases": [
        {"name": "D", "type": "D", "P": "100 kip", "M": "500 kip*in"},
        {"name": "L", "type": "L", "P": "160 kip", "M": "800 kip*in"},
    ],
    "combinations": {"methods": ["LRFD", "ASD"]},
}

BASE_PLATE_EMBEDDED: dict[str, Any] = {
    "info": {"name": "Base empotrada Tipo I", "language": "es", "units": "US"},
    "base_plate": {
        "connection_type": "embedded", "column": "W14X176",
        "column_grade": "ASTM A992", "plate_grade": "ASTM A572 Gr. 50",
        "pressure_model": "rectangular", "bearing_area_model": "plate",
        "fc": "4 ksi",
        "embedded_base": {
            "embedment": "22 in", "foundation_width": "60 in",
            "face_plate_thickness": "1 in", "beta1": 0.85,
        },
    },
    "cases": [{"name": "S1", "type": "E", "P": "250 kip", "M": "700 kip*ft",
               "V": "96 kip"}],
    "combinations": {
        "include_code": False,
        "custom": [{"name": "S1-LRFD", "method": "LRFD",
                    "factors": {"S1": 1.0}, "source": "DG1 5.3-1"}],
    },
}

BASE_PLATE_WEAK: dict[str, Any] = {
    "info": {"name": "Base débil sísmica", "language": "es", "units": "US"},
    "base_plate": {
        "column": "W12X96", "column_grade": "ASTM A992",
        "N": "20 in", "B": "20 in", "tp": "2.5 in",
        "plate_grade": "ASTM A572 Gr. 50", "pressure_model": "rectangular",
        "bearing_area_model": "plate", "fc": "4 ksi", "A2_over_A1": 4.0,
        "bearing_area": "3.21 in**2", "grout": "1.5 in",
        "rod_diameter": "1 in", "rod_grade": "ASTM F1554 Gr. 55",
        "rods_per_side": 3, "f": "8 in", "rod_spacing": "16 in", "hef": "24 in",
        "seismic": True,
        "weak_base": {"reduced_diameter": "0.75 in", "stretch_length": "8 in",
                      "Rt": 1.2},
    },
    "cases": [{"name": "S1", "type": "E", "P": "376 kip", "M": "3600 kip*in",
               "V": "50 kip"}],
    "combinations": {
        "include_code": False,
        "custom": [{"name": "S1-LRFD", "method": "LRFD",
                    "factors": {"S1": 1.0}, "source": "DG1 6.4-1"}],
    },
}

SHEAR_BASE: dict[str, Any] = {
    "info": {"name": "Conexión de corte", "language": "es", "units": "US"},
    "shear_connection": {
        "type": "single_plate", "beam": "W16X50", "support": "W14X90",
        "support_element": "flange", "grade": "ASTM A572 Gr. 50",
        "electrode": "E70XX", "bolt": {"diameter": "3/4 in"},
        "rows": 4, "spacing": "3 in", "length": "11.5 in",
        "thickness": "1/4 in", "lev": "1.25 in", "leh": "1.5 in",
        "a": "3 in", "weld": "3/16 in",
    },
    "cases": [
        {"name": "D", "type": "D", "V": "8 kip"},
        {"name": "L", "type": "L", "V": "25 kip"},
    ],
    "combinations": {"methods": ["LRFD", "ASD"]},
}

SHEAR_OVERRIDES: dict[str, dict[str, Any]] = {
    "double_angle": {
        "length": "8.5 in", "leh": "1.25 in", "leh_support": "1.25 in",
        "support_element": "web",
    },
    "single_plate": {},
    "extended_single_plate": {
        "rows": 5, "length": "14.5 in", "thickness": "3/4 in",
        "leh": "1.75 in", "a": "9.75 in", "lines": 2, "gage": "3 in",
        "weld": "1/2 in", "beam_leh": "1.75 in", "support_element": "web",
    },
    "end_plate": {
        "length": "11.5 in", "leh": "1.5 in", "weld": "3/16 in",
    },
    "seated": {
        "length": "8 in", "thickness": "5/8 in", "leg": "4 in", "bolts": 4,
        "support_element": "web",
    },
    "stiffened_seat": {
        "width": "7 in", "length": "15 in", "thickness": "5/8 in",
        "weld": "5/16 in", "support_element": "web",
    },
    "skewed_bent_plate": {
        "beam": "W16X77", "support": "W27X94", "support_element": "web",
        "grade": "ASTM A36", "bolt": {"diameter": "7/8 in"}, "rows": 3,
        "length": "8 1/2 in", "thickness": "7/16 in", "lev": "1 1/4 in",
        "leh": "1 1/4 in", "weld": "1/4 in", "weld_return": "2 1/2 in",
        "weld_offset": "3 5/8 in", "row_distance": "6 in",
        "load_offset": "2 1/4 in", "share_b": 0.66,
        "plate_a_width": "7 1/4 in", "plate_b_width": "6 3/4 in",
        "plate_a_leg": "4 7/16 in", "plate_b_leg": "3 9/16 in",
        "bend_radius": "9/16 in", "skew": "6:12",
    },
}


@dataclass(frozen=True)
class Subtype:
    id: str
    label: str
    description: str
    asset: str


@dataclass(frozen=True)
class Family:
    id: str
    label: str
    description: str
    asset: str
    subtypes: tuple[Subtype, ...] = ()
    enabled: bool = True
    badge: str = ""


def _subtypes(definitions: tuple[tuple[str, str, str, str], ...]) -> tuple[Subtype, ...]:
    return tuple(Subtype(*definition) for definition in definitions)


BASE_PLATE_SUBTYPES = _subtypes((
    ("exposed", "Placa base expuesta",
     "Columna sobre una placa de acero apoyada en concreto.",
     "base_plate_exposed"),
    ("embedded", "Base empotrada Tipo I",
     "La columna se empotra en el concreto y el momento se resiste por apoyo "
     "horizontal.",
     "base_plate_embedded"),
    ("weak", "Base débil sísmica",
     "Anclajes dúctiles de sección reducida para formar una rótula.",
     "base_plate_weak"),
))

SHEAR_SUBTYPES = _subtypes((
    ("double_angle", "Doble ángulo apernado",
     "Dos ángulos apernados al alma de la viga y al apoyo.",
     "shear_double_angle"),
    ("single_plate", "Placa simple",
     "Una placa soldada al apoyo y apernada al alma de la viga.",
     "shear_single_plate"),
    ("extended_single_plate", "Placa simple extendida",
     "Placa alta con una o dos líneas de pernos, para mayor excentricidad.",
     "shear_extended_plate"),
    ("end_plate", "Placa de extremo de corte",
     "Placa soldada al extremo del alma de la viga y apernada al apoyo.",
     "shear_end_plate"),
    ("seated", "Asiento no rigidizado",
     "La viga apoya en un ángulo de asiento; el ángulo superior estabiliza.",
     "shear_seated"),
    ("stiffened_seat", "Asiento rigidizado",
     "Placa de asiento sobre un rigidizador soldado al apoyo.",
     "shear_stiffened_seat"),
    ("skewed_bent_plate", "Placa doblada en esviaje",
     "Dos placas dobladas para vigas que llegan con esviaje.",
     "shear_skewed_bent_plate"),
))

SHEAR_BEAM_SUBTYPES = tuple(
    Subtype(subtype.id, subtype.label, subtype.description,
            f"shear_beam_{subtype.id}")
    for subtype in SHEAR_SUBTYPES
)

FAMILIES = (
    Family("base_plate", "Placa base",
           "Columna apoyada en concreto, con anclajes y placa de acero.",
           "family_base_plate", BASE_PLATE_SUBTYPES),
    Family("shear_column", "Corte viga-columna",
           "El extremo de una viga llega a una columna y transmite cortante.",
           "family_shear_column", SHEAR_SUBTYPES),
    Family("shear_beam", "Corte viga-viga",
           "El extremo de una viga llega al alma de una viga de apoyo.",
           "family_shear_beam", SHEAR_BEAM_SUBTYPES),
    Family("moment", "Momento viga-columna",
           "Unión a momento entre viga y columna.", "family_moment",
           enabled=False, badge="Próximamente"),
    Family("splice", "Empalmes",
           "Unión de dos tramos de viga o de columna.", "family_splice",
           enabled=False, badge="Próximamente"),
)


def family_by_id(family_id: str) -> Family:
    for family in FAMILIES:
        if family.id == family_id:
            return family
    raise KeyError(f"unknown connection family: {family_id!r}")


def subtype_by_id(family: Family, subtype_id: str) -> Subtype:
    for subtype in family.subtypes:
        if subtype.id == subtype_id:
            return subtype
    raise KeyError(f"unknown subtype {subtype_id!r} for {family.id!r}")


def build_project(family_id: str, subtype_id: str) -> Project:
    """Build a valid starter project for a gallery selection."""
    family = family_by_id(family_id)
    subtype = subtype_by_id(family, subtype_id)
    if family_id == "base_plate":
        template = {
            "exposed": BASE_PLATE_EXPOSED,
            "embedded": BASE_PLATE_EMBEDDED,
            "weak": BASE_PLATE_WEAK,
        }[subtype_id]
        data = copy.deepcopy(template)
        data["info"]["name"] = f"Placa base — {subtype.label}"
        return Project.model_validate(data)
    if family_id in {"shear_column", "shear_beam"}:
        data = copy.deepcopy(SHEAR_BASE)
        connection = data["shear_connection"]
        connection["type"] = subtype_id
        connection.update(copy.deepcopy(SHEAR_OVERRIDES[subtype_id]))
        if family_id == "shear_beam":
            connection["support"] = ("W27X94" if subtype_id == "skewed_bent_plate"
                                     else "W21X62")
            connection["support_element"] = "web"
        data["info"]["name"] = f"Conexión de corte — {subtype.label}"
        return Project.model_validate(data)
    raise ValueError(f"{family.label} todavía no está disponible")
