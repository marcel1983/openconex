# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
import json

import pytest

from openconex.core.loads import Method
from openconex.core.model import HSSKind, HSSShape, IShape
from openconex.io.project import (
    FORMAT_VERSION,
    CustomCombinationInput,
    Project,
    load_project,
    save_project,
)
from openconex.units import Kind

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
    column = {"type": "HSS", "shape": shape, "d": "12 in", "t": "0.5 in"}
    if bf is not None:
        column["bf"] = bf
    section = _project_with_column(column).column_model()
    assert isinstance(section, HSSShape)
    assert section.kind is kind
    assert section.d == pytest.approx(304.8)
    assert section.t == pytest.approx(12.7)
    assert section.bf == pytest.approx(304.8 if bf is None else 203.2)
    assert section.grade == grade


def test_generic_hss_requires_width():
    with pytest.raises(ValueError, match="needs its width"):
        _project_with_column({"type": "HSS", "shape": "rectangular", "d": "12 in",
                              "t": "0.5 in"})
    with pytest.raises(ValueError, match="bf is not allowed"):
        _project_with_column({"type": "HSS", "shape": "round", "d": "12 in",
                              "bf": "12 in", "t": "0.5 in"})


def test_generic_section_dimensions_are_validated():
    with pytest.raises(ValueError, match="flanges thicker"):
        _project_with_column({"type": "W", "d": "20 in", "bf": "12 in", "tf": "11 in",
                              "tw": "0.5 in"}).column_model()
    with pytest.raises(ValueError, match="wall thickness"):
        _project_with_column({"type": "HSS", "shape": "round", "d": "12 in",
                              "t": "7 in"}).column_model()


@pytest.mark.parametrize(("filename", "kind"), [
    ("base_plate_generic_w.ocnx", IShape),
    ("base_plate_hss_square.ocnx", HSSShape),
    ("base_plate_hss_round.ocnx", HSSShape),
])
def test_generic_column_examples(filename, kind):
    project = load_project(EXAMPLE.with_name(filename))
    assert isinstance(project.column_model(), kind)
