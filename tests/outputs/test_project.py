# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
import json

import pytest

from openconex.connections.base_plate.check import BearingAreaModel, PressureModel
from openconex.core.loads import Method
from openconex.core.model import HSSKind, HSSShape, IShape
from openconex.io.project import (
    FORMAT_VERSION,
    CustomCombinationInput,
    MaterialInput,
    Project,
    load_project,
    save_project,
)
from openconex.units import Kind, to_internal

from .conftest import EXAMPLE


def test_example_converts_to_model(project):
    bp = project.base_plate_model()
    assert bp.N == pytest.approx(609.6)
    assert bp.tp == pytest.approx(50.8)
    assert bp.column.name == "W12X96"
    assert bp.rod.grade == "ASTM F1554 Gr. 36"
    forces = project.case_forces()
    assert forces["L"].M3 == pytest.approx(1500 * 4448.2216152605 * 25.4)
    names = [c.name for c in project.load_combinations()]
    assert names[:2] == ["LRFD-1", "LRFD-2"] and "ASD-2" in names


def test_bare_numbers_use_project_units(project):
    project.base_plate.tp = 2  # project units are "US": inches
    assert project.base_plate_model().tp == pytest.approx(50.8)
    project.info.units = "SI_N_mm"
    assert project.quantity(25, Kind.THICKNESS) == pytest.approx(25.0)


def test_round_trip(tmp_path, project):
    path = tmp_path / "copy.ocnx"
    save_project(project, path)
    again = load_project(path)
    assert again == project
    assert json.loads(path.read_text())["format_version"] == FORMAT_VERSION


def test_custom_combinations_example():
    path = EXAMPLE.with_name("base_plate_custom_combinations.ocnx")
    project = load_project(path)
    combos = project.load_combinations()
    assert [c.name for c in combos] == ["C-1", "C-2", "C-3", "C-4"]
    assert all(c.source for c in combos)


def test_older_format_still_loads(tmp_path):
    data = json.loads(EXAMPLE.read_text())
    data["format_version"] = 1
    path = tmp_path / "old.ocnx"
    path.write_text(json.dumps(data))
    project = load_project(path)
    assert project.format_version == 1
    save_project(project, path)
    assert json.loads(path.read_text())["format_version"] == FORMAT_VERSION


def test_newer_format_is_rejected(tmp_path):
    data = json.loads(EXAMPLE.read_text())
    data["format_version"] = 99
    path = tmp_path / "future.ocnx"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="newer"):
        load_project(path)


def test_unknown_fields_are_rejected():
    data = json.loads(EXAMPLE.read_text())
    data["base_plate"]["typo"] = 1
    with pytest.raises(ValueError):
        Project.model_validate(data)


def test_custom_combinations_replace_code(project):
    project.combinations.include_code = False
    project.combinations.custom = [
        CustomCombinationInput(
            name="C-1", method=Method.LRFD, factors={"D": 1.2, "L": 1.6},
            source="Criterio del proyecto"),
    ]
    combos = project.load_combinations()
    assert [c.name for c in combos] == ["C-1"]
    assert combos[0].factors == {"D": 1.2, "L": 1.6}
    assert combos[0].method is Method.LRFD
    assert combos[0].source == "Criterio del proyecto"


def test_custom_combinations_are_added_to_code(project):
    project.combinations.custom = [
        CustomCombinationInput(name="C-1", factors={"D": 1.0, "L": 1.0}),
    ]
    names = [c.name for c in project.load_combinations()]
    assert names[:2] == ["LRFD-1", "LRFD-2"]
    assert names[-1] == "C-1"


def test_custom_combination_flags(project):
    project.combinations.include_code = False
    project.combinations.custom = [
        CustomCombinationInput(
            name="S-1", method=Method.ASD, factors={"D": 1.0, "L": 0.7},
            seismic=True, overstrength=True, allowable_increase=1.2),
    ]
    combo = project.load_combinations()[0]
    assert combo.seismic and combo.overstrength
    assert combo.allowable_increase == pytest.approx(1.2)
    assert combo.source == "custom"


def test_custom_combination_with_unknown_case_is_rejected(project):
    project.combinations.custom = [CustomCombinationInput(name="C-1", factors={"Q": 1.0})]
    with pytest.raises(ValueError, match="undefined load cases"):
        project.load_combinations()


def test_custom_combinations_are_validated_on_load():
    data = json.loads(EXAMPLE.read_text())
    data["combinations"] = {"include_code": False, "custom": [
        {"name": "C-1", "factors": {"Q": 1.0}},
    ]}
    with pytest.raises(ValueError, match="undefined load cases"):
        Project.model_validate(data)


def test_custom_only_project_needs_combinations():
    data = json.loads(EXAMPLE.read_text())
    data["combinations"] = {"include_code": False, "custom": []}
    with pytest.raises(ValueError, match="no load combinations"):
        Project.model_validate(data)


def test_duplicate_custom_combination_names_are_rejected(project):
    project.combinations.include_code = False
    project.combinations.custom = [
        CustomCombinationInput(name="C-1", factors={"D": 1.0}),
        CustomCombinationInput(name="C-1", factors={"D": 1.0, "L": 1.0}),
    ]
    with pytest.raises(ValueError, match="duplicate load combination names"):
        project.load_combinations()


def _project_with_column(column) -> Project:
    data = json.loads(EXAMPLE.read_text())
    data["base_plate"]["column"] = column
    return Project.model_validate(data)


def test_generic_w_column():
    project = _project_with_column({
        "type": "W", "d": "20 in", "bf": "12 in", "tf": "1 in", "tw": "0.5 in",
        "grade": "ASTM A572 Gr. 50"})
    column = project.column_model()
    assert isinstance(column, IShape)
    assert column.name == "W 20 in×12 in×1 in×0.5 in"
    assert column.d == pytest.approx(508)
    assert column.bf == pytest.approx(304.8)
    assert column.tf == pytest.approx(25.4)
    assert column.tw == pytest.approx(12.7)
    assert column.grade == "ASTM A572 Gr. 50"


@pytest.mark.parametrize(("shape", "bf", "kind", "grade"), [
    ("rectangular", "8 in", HSSKind.RECTANGULAR, "ASTM A500 Gr. C (rectangular)"),
    ("square", None, HSSKind.SQUARE, "ASTM A500 Gr. C (rectangular)"),
    ("round", None, HSSKind.ROUND, "ASTM A500 Gr. C (round)"),
])
def test_generic_hss_columns(shape, bf, kind, grade):
    column = {"type": "HSS", "shape": shape, "d": "12 in", "t": "0.5 in",
              "grade": grade}
    if bf is not None:
        column["bf"] = bf
    section = _project_with_column(column).column_model()
    assert isinstance(section, HSSShape)
    assert section.kind is kind
    assert section.d == pytest.approx(304.8)
    assert section.t == pytest.approx(12.7)
    assert section.bf == pytest.approx(304.8 if bf is None else 203.2)
    assert section.grade == grade


def test_generic_section_material_is_required():
    with pytest.raises(ValueError):
        _project_with_column({"type": "W", "d": "20 in", "bf": "12 in", "tf": "1 in",
                              "tw": "0.5 in"})
    with pytest.raises(ValueError):
        _project_with_column({"type": "HSS", "shape": "square", "d": "12 in",
                              "t": "0.5 in"})


def test_generic_hss_requires_width():
    with pytest.raises(ValueError, match="needs its width"):
        _project_with_column({"type": "HSS", "shape": "rectangular", "d": "12 in",
                              "t": "0.5 in", "grade": "ASTM A500 Gr. C (rectangular)"})
    with pytest.raises(ValueError, match="bf is not allowed"):
        _project_with_column({"type": "HSS", "shape": "round", "d": "12 in",
                              "bf": "12 in", "t": "0.5 in",
                              "grade": "ASTM A500 Gr. C (round)"})


def test_generic_section_dimensions_are_validated():
    with pytest.raises(ValueError, match="flanges thicker"):
        _project_with_column({"type": "W", "d": "20 in", "bf": "12 in", "tf": "11 in",
                              "tw": "0.5 in", "grade": "ASTM A992"}).column_model()
    with pytest.raises(ValueError, match="wall thickness"):
        _project_with_column({"type": "HSS", "shape": "round", "d": "12 in",
                              "t": "7 in", "grade": "ASTM A500 Gr. C (round)"}).column_model()


@pytest.mark.parametrize(("filename", "kind"), [
    ("base_plate_generic_w.ocnx", IShape),
    ("base_plate_hss_square.ocnx", HSSShape),
    ("base_plate_hss_round.ocnx", HSSShape),
])
def test_generic_column_examples(filename, kind):
    project = load_project(EXAMPLE.with_name(filename))
    assert isinstance(project.column_model(), kind)


def test_custom_material_is_used_by_sections_and_plate():
    data = json.loads(EXAMPLE.read_text())
    data["materials"] = [
        {"name": "Acero del proyecto", "Fy": "50 ksi", "Fu": "65 ksi"},
    ]
    data["base_plate"]["plate_grade"] = "Acero del proyecto"
    data["base_plate"]["column"] = {
        "type": "W", "name": "COL", "d": "20 in", "bf": "12 in", "tf": "1 in",
        "tw": "0.5 in", "grade": "Acero del proyecto",
    }
    project = Project.model_validate(data)
    library = project.material_library()
    material = library["Acero del proyecto"]
    assert material.Fy == pytest.approx(project.quantity("50 ksi", Kind.STRESS))
    assert material.Fu == pytest.approx(project.quantity("65 ksi", Kind.STRESS))
    model = project.base_plate_model()
    assert model.column.material.name == material.name
    assert model.column.material.Fy == pytest.approx(material.Fy)
    assert model.materials[model.plate_grade].name == material.name
    assert model.Fy == pytest.approx(material.Fy)


def test_custom_material_for_hss_column():
    data = json.loads(EXAMPLE.read_text())
    data["materials"] = [{"name": "Acero del proyecto", "Fy": "50 ksi", "Fu": "65 ksi"}]
    data["base_plate"]["column"] = {
        "type": "HSS", "shape": "square", "d": "12 in", "t": "0.5 in",
        "grade": "Acero del proyecto",
    }
    column = Project.model_validate(data).column_model()
    assert isinstance(column, HSSShape)
    assert column.material.name == "Acero del proyecto"


def test_custom_material_for_catalog_column():
    data = json.loads(EXAMPLE.read_text())
    data["materials"] = [{"name": "Acero del proyecto", "Fy": "50 ksi", "Fu": "65 ksi"}]
    data["base_plate"]["column_grade"] = "Acero del proyecto"
    column = Project.model_validate(data).column_model()
    assert column.grade == "Acero del proyecto"
    assert column.material.name == "Acero del proyecto"


def test_pressure_model_options_are_parsed():
    data = json.loads(EXAMPLE.read_text())
    data["base_plate"]["pressure_model"] = "triangular"
    project = Project.model_validate(data)
    assert project.base_plate_model().pressure_model is PressureModel.TRIANGULAR
    data = json.loads(EXAMPLE.read_text())
    data["base_plate"]["bearing_area_model"] = "effective"
    project = Project.model_validate(data)
    assert project.base_plate_model().bearing_area_model is BearingAreaModel.EFFECTIVE
    data["base_plate"]["pressure_model"] = "triangular"
    with pytest.raises(ValueError, match="rectangular pressure model"):
        Project.model_validate(data)


def test_rod_bending_lever_is_parsed():
    data = json.loads(EXAMPLE.read_text())
    data["base_plate"]["rod_bending_lever"] = "1.825 in"
    project = Project.model_validate(data)
    assert project.base_plate_model().rod_bending_lever == pytest.approx(46.355)


def test_reinforcement_input_is_parsed():
    data = json.loads(EXAMPLE.read_text())
    data["base_plate"]["reinforcement"] = {
        "bars": "4 #6", "area": "1.76 in**2", "fy": "60 ksi", "db": "0.75 in",
        "clear_cover": "2 in", "anchor_to_bar": "2.83 in", "le": "15.2 in",
    }
    project = Project.model_validate(data)
    reinforcement = project.base_plate_model().reinforcement
    assert reinforcement is not None
    assert reinforcement.bars == "4 #6"
    assert reinforcement.area == pytest.approx(1.76 * 25.4**2)
    assert reinforcement.le == pytest.approx(to_internal(15.2, "in", Kind.LENGTH))


def test_effective_area_requires_an_i_shape():
    data = json.loads(EXAMPLE.read_text())
    data["base_plate"]["column"] = {
        "type": "HSS", "shape": "square", "d": "12 in", "t": "0.5 in",
        "grade": "ASTM A500 Gr. C (rectangular)",
    }
    data["base_plate"]["bearing_area_model"] = "effective"
    with pytest.raises(ValueError, match="I-shapes"):
        Project.model_validate(data)


def test_triangular_model_rejects_weak_axis_moment():
    data = json.loads(EXAMPLE.read_text())
    data["base_plate"]["pressure_model"] = "triangular"
    data["cases"][0]["M_weak"] = "10 kip*in"
    with pytest.raises(ValueError, match="weak-axis"):
        Project.model_validate(data)


def test_custom_material_names_must_be_unique():
    data = json.loads(EXAMPLE.read_text())
    data["materials"] = [{"name": "ASTM A36", "Fy": "36 ksi", "Fu": "58 ksi"}]
    with pytest.raises(ValueError, match="already exists"):
        Project.model_validate(data)
    data["materials"] = [
        {"name": "Acero X", "Fy": "50 ksi", "Fu": "65 ksi"},
        {"name": "Acero X", "Fy": "50 ksi", "Fu": "65 ksi"},
    ]
    with pytest.raises(ValueError, match="already exists"):
        Project.model_validate(data)


def test_custom_material_values_are_validated():
    data = json.loads(EXAMPLE.read_text())
    data["materials"] = [{"name": "Acero X", "Fy": "50 ksi", "Fu": "40 ksi"}]
    with pytest.raises(ValueError, match="Fu must be at least Fy"):
        Project.model_validate(data)
    data["materials"] = [{"name": "Acero X", "Fy": "-1 ksi", "Fu": "40 ksi"}]
    with pytest.raises(ValueError, match="positive"):
        Project.model_validate(data)
    with pytest.raises(ValueError):
        MaterialInput(name="   ", Fy="50 ksi", Fu="65 ksi")


def test_unknown_material_is_rejected():
    data = json.loads(EXAMPLE.read_text())
    data["base_plate"]["plate_grade"] = "Acero inexistente"
    with pytest.raises(ValueError, match="unknown plate material"):
        Project.model_validate(data)
    data = json.loads(EXAMPLE.read_text())
    data["base_plate"]["column_grade"] = "Acero inexistente"
    with pytest.raises(ValueError, match="unknown column material"):
        Project.model_validate(data)


def test_custom_materials_round_trip(tmp_path, project):
    project.materials = [
        MaterialInput(name="Acero del proyecto", Fy="50 ksi", Fu="65 ksi", E="29000 ksi"),
    ]
    path = tmp_path / "custom_material.ocnx"
    save_project(project, path)
    again = load_project(path)
    assert again.materials == project.materials
    assert again.material_library()["Acero del proyecto"].Fy == pytest.approx(
        project.quantity("50 ksi", Kind.STRESS))
