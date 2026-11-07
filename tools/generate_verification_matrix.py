# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Generate the traceability matrix for the verification manual.

The catalog in ``docs/tecnico/04-verificaciones.md`` is the source of the
check identifiers and clauses.  This tool adds the evidence columns that the
catalog does not carry: the published reference, the automated test, the
independent calculation, the external comparison, the status and the risk.

Run from the repository root::

    python tools/generate_verification_matrix.py

The output is ``docs/verificacion/matriz-verificacion.csv``.  It is checked by
``tests/test_docs.py`` so every ``check.*`` message in the translation
catalogs has a row.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

from openconex.i18n import catalog

ROOT = Path(__file__).parents[1]
CATALOG = ROOT / "docs" / "tecnico" / "04-verificaciones.md"
OUTPUT = ROOT / "docs" / "verificacion" / "matriz-verificacion.csv"

COLUMNS = ("check_id", "familia", "clausula", "formula", "referencia_publicada",
           "test", "calculo_independiente", "software_externo", "estado", "riesgo",
           "notas")

FAMILY = {
    "Placa base": "placa_base",
    "Doble ángulo apernado": "doble_angulo",
    "Doble ángulo con carga axial": "doble_angulo_axial",
    "Conexión sesgada de doble placa doblada": "placa_doblada",
    "Placa simple convencional": "placa_simple",
    "Placa simple con carga axial": "placa_simple_axial",
    "Viga con destaje": "viga_destajada",
    "Refuerzo del destaje": "refuerzo_destaje",
    "Placa simple extendida": "placa_extendida",
    "Placa simple extendida con carga axial": "placa_extendida_axial",
    "Placa de extremo de corte": "placa_extremo",
    "Asiento no rigidizado apernado": "asiento",
    "Asiento rigidizado soldado": "asiento_rigidizado",
    "Conexión de corte: resultados comunes": "conexion_corte",
    "Anclajes": "anclajes",
    "Pernos": "pernos",
    "Soldaduras": "soldaduras",
    "Elementos de conexión": "elementos",
    "Fuerzas concentradas": "fuerzas_concentradas",
}

REFERENCE = {
    "placa_base": "DG1 3.ª ed. (2024), ejemplos 4.7-1 a 4.7-15, B.2/B.3 y 5.3-1",
    "doble_angulo": "AISC DE v16.1, II.A-1A/1B, II.A-2A y II.A-3",
    "doble_angulo_axial": "AISC DE v16.1, II.A-1B",
    "placa_doblada": "AISC DE v16.1, II.A-10",
    "placa_simple": "AISC DE v16.1, II.A-17A",
    "placa_simple_axial": "AISC DE v16.1, II.A-17B",
    "viga_destajada": "AISC DE v16.1, II.A-4, II.A-6 A/B y II.A-7",
    "refuerzo_destaje": "AISC DE v16.1, II.A-6 C/D",
    "placa_extendida": "AISC DE v16.1, II.A-19A",
    "placa_extendida_axial": "AISC DE v16.1, II.A-19B",
    "placa_extremo": "AISC DE v16.1, II.A-11A/B",
    "asiento": "AISC DE v16.1, II.A-12A, II.A-13 y II.A-16",
    "asiento_rigidizado": "AISC DE v16.1, II.A-14 y II.A-15",
    "conexion_corte": "—",
    "anclajes": "ACI 318-19 Cap. 17; DG1 4.7-3 a 4.7-6 y 4.7-15",
    "pernos": "AISC 360-22 §J3; Manual Tablas 7-6 a 7-14 y 14-2",
    "soldaduras": "AISC 360-22 §J2; Manual Tablas 8-3 a 8-11",
    "elementos": "AISC 360-22 §J4",
    "fuerzas_concentradas": "AISC 360-22 §J10",
}

TEST = {
    "placa_base": "tests/base_plate/test_dg1_acceptance.py",
    "doble_angulo": "tests/connections/test_double_angle.py",
    "doble_angulo_axial": "tests/connections/test_double_angle_axial.py",
    "placa_doblada": "tests/connections/test_bent_plate.py",
    "placa_simple": "tests/connections/test_single_plate.py",
    "placa_simple_axial": "tests/connections/test_single_plate_axial.py",
    "viga_destajada": "tests/connections/test_coped_beam.py",
    "refuerzo_destaje": "tests/connections/test_cope_reinforcement.py",
    "placa_extendida": "tests/connections/test_extended_single_plate.py",
    "placa_extendida_axial": "tests/connections/test_extended_single_plate_axial.py",
    "placa_extremo": "tests/connections/test_end_plate.py",
    "asiento": "tests/connections/test_seated.py; tests/connections/test_shear_project.py",
    "asiento_rigidizado": "tests/connections/test_stiffened_seat.py",
    "conexion_corte": "tests/connections/test_shear_project.py",
    "anclajes": "tests/kernel/test_anchors.py",
    "pernos": "tests/kernel/test_bolts.py",
    "soldaduras": "tests/kernel/test_welds.py",
    "elementos": "tests/kernel/test_elements.py",
    "fuerzas_concentradas": "tests/kernel/test_local.py",
}

# Specific overrides for tests that live in another file.
TEST_OVERRIDE = {
    "base_plate.biaxial": "tests/base_plate/test_biaxial.py",
    "base_plate.embedded_moment": "tests/base_plate/test_embedded_base.py",
    "base_plate.face_plate_bearing": "tests/base_plate/test_embedded_base.py",
    "base_plate.face_plate_thickness": "tests/base_plate/test_embedded_base.py",
    "base_plate.face_plate_seismic": "tests/base_plate/test_embedded_base.py",
    "base_plate.lug_shear_yielding": "tests/base_plate/test_shear_lug.py",
    "base_plate.lug_shear_rupture": "tests/base_plate/test_shear_lug.py",
    "base_plate.lug_flexural_yielding": "tests/base_plate/test_shear_lug.py",
    "base_plate.lug_flexural_rupture": "tests/base_plate/test_shear_lug.py",
    "base_plate.lug_weld": "tests/base_plate/test_shear_lug.py",
    "base_plate.lug_plate_bending": "tests/base_plate/test_shear_lug.py",
    "base_plate.lug_anchor_embedment": "tests/base_plate/test_shear_lug.py",
    "base_plate.anchor_rebar_clearance": "tests/base_plate/test_anchor_reinforcement.py",
    "bolt_group.eccentric": "tests/kernel/test_bolt_group_manual.py",
    "weld_group.eccentric": "tests/kernel/test_weld_group.py",
    "prying.tension": "tests/kernel/test_prying.py",
    "prying.min_thickness": "tests/kernel/test_prying.py",
}

# Checks with a documented difference or a partial reference.
DIFFERENCE = {
    "single_plate.bolts": ("C = 3,556/4,06 frente a 3,54/4,07 interpolado (II.A-17A/17B); "
                           "el cálculo independiente de II.A-17A da C = 3,556 y 58,7/39,1 kip"),
    "double_angle.block_shear_axial": "forma U en vez de L (II.A-1B), algo conservador",
    "extended_plate.flexural_rupture": "Z_net = 12,75 in³ frente a 12,8 in³ (II.A-19A)",
}

PARTIAL = {
    "coped_beam.flexure": "λ > 2λ_p (Ec. 9-12/9-13) y doble destaje de II.A-18 pendientes",
    "coped_beam.block_shear": "doble destaje y conexiones desplazadas de II.A-18 pendientes",
}

NO_APLICA = {"shear_connection.axial_compression", "shear_connection.axial_unsupported"}

INDEPENDENT = {
    "seated.bearing_length": "docs/verificacion/calculos/asientos.py",
    "seated.shear_yielding": "docs/verificacion/calculos/asientos.py",
    "seated.flexural_yielding": "docs/verificacion/calculos/asientos.py",
    "seated.bolts": "docs/verificacion/calculos/asientos.py",
    "seated.weld": "docs/verificacion/calculos/asientos.py",
    "stiffened_seat.weld": "docs/verificacion/calculos/asientos.py",
    "double_angle.bolts_beam": "docs/verificacion/calculos/doble_angulo_placa_simple.py",
    "double_angle.bolts_support": "docs/verificacion/calculos/doble_angulo_placa_simple.py",
    "double_angle.angle_shear_yielding": "docs/verificacion/calculos/doble_angulo_placa_simple.py",
    "double_angle.angle_shear_rupture": "docs/verificacion/calculos/doble_angulo_placa_simple.py",
    "double_angle.block_shear_beam": "docs/verificacion/calculos/doble_angulo_placa_simple.py",
    "double_angle.block_shear_support": "docs/verificacion/calculos/doble_angulo_placa_simple.py",
    "single_plate.bolts": "docs/verificacion/calculos/doble_angulo_placa_simple.py",
    "single_plate.shear_yielding": "docs/verificacion/calculos/doble_angulo_placa_simple.py",
    "single_plate.shear_rupture": "docs/verificacion/calculos/doble_angulo_placa_simple.py",
    "single_plate.block_shear": "docs/verificacion/calculos/doble_angulo_placa_simple.py",
    "base_plate.bearing": "docs/verificacion/calculos/placa_base.py",
    "base_plate.thickness_compression": "docs/verificacion/calculos/placa_base.py",
    "base_plate.thickness_tension": "docs/verificacion/calculos/placa_base.py",
    "base_plate.biaxial": "docs/verificacion/calculos/placa_base.py",
}

NOTES = {
    "shear_connection.axial_compression": "No implementado; capacidad 0 y estado no cumple.",
    "shear_connection.axial_unsupported": "Tipo sin procedimiento axial; capacidad 0.",
    "base_plate.face_plate_seismic": "AISC 341-22; no forma parte de los 20 ejemplos DG1.",
    "prying.tension": "Biblioteca; usado por el doble ángulo con carga axial.",
    "prying.min_thickness": "Biblioteca; usado por el doble ángulo con carga axial.",
    "seated.top_angle_leg": "Detalle de estabilidad; no toma carga.",
    "seated.top_angle_thickness": "Detalle de estabilidad; no toma carga.",
    "seated.top_angle_length": "Detalle de estabilidad; no toma carga.",
    "seated.top_angle_bolts": "Detalle de estabilidad; no toma carga.",
    "seated.top_angle_weld": "Detalle de estabilidad; no toma carga.",
    "stiffened_seat.seat_plate_width": "Detalle estándar de II.A-14.",
    "stiffened_seat.seat_plate_thickness": "Detalle estándar de II.A-14.",
    "stiffened_seat.seat_plate_weld": "Detalle estándar de II.A-14.",
    "stiffened_seat.seat_plate_weld_length": "Detalle estándar de II.A-14.",
}

DETAIL = (
    "top_angle", "weld_size", "weld_max_size", "max_thickness", "leh", "lev",
    "min_spacing", "max_spacing", "min_edge", "max_edge", "clearance",
    "support_thickness", "beam_web_thickness", "plate_thickness", "compact",
    "seat_plate_width", "seat_plate_thickness", "seat_plate_weld_length",
    "stiffener_thickness", "anchor_plate_edge", "anchor_column_clearance",
    "anchor_lug_clearance", "anchor_rebar_clearance", "a2_over_a1",
)

HIGH_FAMILIES = set(FAMILY.values()) - {"conexion_corte"}

# The catalog uses a wildcard for the five stability-angle checks.
WILDCARD = {
    "seated.top_angle_*": [
        ("seated.top_angle_leg", "Ala del ángulo superior ≥ 4 in",
         "Manual Parte 10, detalle estándar"),
        ("seated.top_angle_thickness", "Espesor ≥ 1/4 in",
         "Manual Parte 10, detalle estándar"),
        ("seated.top_angle_length", "Largo ≥ 4 in",
         "Manual Parte 10, detalle estándar"),
        ("seated.top_angle_bolts", "Pernos por ala ≥ 2 (asiento apernado)",
         "Manual Parte 10, detalle estándar"),
        ("seated.top_angle_weld", "Soldadura ≥ 3/16 in (asiento soldado)",
         "Manual Parte 10, detalle estándar"),
    ],
}


def parse_catalog() -> dict[str, tuple[str, str, str]]:
    """Return check_id -> (family, description, clause)."""
    text = CATALOG.read_text(encoding="utf-8")
    section = ""
    info: dict[str, tuple[str, str, str]] = {}
    for line in text.splitlines():
        heading = re.match(r"^#{2,3}\s+(.*)$", line)
        if heading:
            section = heading.group(1).strip()
            continue
        row = re.match(r"^\|\s*`([^`]+)`\s*\|", line)
        if not row:
            continue
        check_id = row.group(1)
        if check_id == "id":
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        description = cells[1] if len(cells) > 1 else ""
        clause = cells[2] if len(cells) > 2 else "—"
        if check_id in WILDCARD:
            for expanded, text_id, text_clause in WILDCARD[check_id]:
                info[expanded] = (section, text_id, text_clause)
            continue
        info[check_id] = (section, description, clause)
    return info


def family_of(section: str) -> str:
    for prefix, family in FAMILY.items():
        if section.startswith(prefix):
            return family
    return "otros"


def status_of(check_id: str, family: str) -> str:
    if check_id in NO_APLICA:
        return "no aplica"
    if check_id in DIFFERENCE:
        return "diferencia aceptada"
    if check_id in PARTIAL:
        return "parcial"
    if family in {"pernos", "soldaduras", "elementos", "fuerzas_concentradas"}:
        return "validado" if "local." not in check_id else "parcial"
    if family == "anclajes":
        return "validado"
    if family == "conexion_corte":
        return "no aplica"
    return "validado"


def risk_of(check_id: str, family: str, status: str) -> str:
    if status == "no aplica":
        return "bajo"
    if any(token in check_id for token in DETAIL):
        return "bajo"
    if family == "fuerzas_concentradas":
        return "bajo"
    if family in {"pernos", "soldaduras", "elementos"}:
        return "medio" if status == "validado" else "alto"
    if status in {"parcial", "pendiente"}:
        return "alto"
    if status == "diferencia aceptada":
        return "medio"
    return "medio"


def main() -> int:
    info = parse_catalog()
    ids = [key.removeprefix("check.") for key in catalog("es")
           if key.startswith("check.")]
    rows = []
    for check_id in ids:
        section, description, clause = info.get(
            check_id, ("Otros", "Ver catálogo técnico", "—"))
        family = family_of(section)
        status = status_of(check_id, family)
        note = DIFFERENCE.get(check_id) or PARTIAL.get(check_id)
        if note:
            description = f"{description} ({note})"
        notes = NOTES.get(check_id, "")
        if check_id.startswith("local."):
            notes = "Solo biblioteca; no integrado en las rutas de diseño actuales."
        rows.append({
            "check_id": check_id,
            "familia": family,
            "clausula": clause,
            "formula": description,
            "referencia_publicada": REFERENCE.get(family, "—"),
            "test": TEST_OVERRIDE.get(check_id, TEST.get(family, "—")),
            "calculo_independiente": INDEPENDENT.get(check_id, "pendiente"),
            "software_externo": "pendiente",
            "estado": status,
            "riesgo": risk_of(check_id, family, status),
            "notas": notes,
        })
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["estado"]] = counts.get(row["estado"], 0) + 1
    print(f"{OUTPUT.relative_to(ROOT)}: {len(rows)} checks")
    print(", ".join(f"{key}={value}" for key, value in sorted(counts.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
