# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
import json

import pytest

from openconex.io.project import Project, load_project, save_project
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
    assert json.loads(path.read_text())["format_version"] == 1


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
