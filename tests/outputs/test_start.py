# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Connection gallery: family/subtype data and the starter projects."""

import os
from importlib import resources

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication

from openconex.geometry3d.mesh import MeshPart
from openconex.gui.start import ConnectionStartDialog, connection_pixmap
from openconex.gui.start_data import FAMILIES, build_project
from openconex.gui.viewer3d import _swap_yz_meshes


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def dialog(app):
    window = ConnectionStartDialog()
    yield window
    window.close()
    window.deleteLater()
    app.processEvents()


def test_families_and_subtypes():
    by_id = {family.id: family for family in FAMILIES}
    assert {"base_plate", "shear_column", "shear_beam", "moment", "splice"} <= set(by_id)
    assert by_id["base_plate"].enabled
    assert by_id["shear_column"].enabled
    assert by_id["shear_beam"].enabled
    assert not by_id["moment"].enabled
    assert not by_id["splice"].enabled
    assert len(by_id["base_plate"].subtypes) == 3
    assert len(by_id["shear_column"].subtypes) == 7


@pytest.mark.parametrize("family", [f for f in FAMILIES if f.enabled],
                         ids=lambda f: f.id)
def test_every_subtype_builds_a_valid_project(family):
    for subtype in family.subtypes:
        project = build_project(family.id, subtype.id)
        if family.id == "base_plate":
            assert project.base_plate is not None
            assert project.shear_connection is None
        else:
            assert project.shear_connection is not None
            assert project.base_plate is None
            assert project.shear_connection.type.value == subtype.id


def test_beam_to_beam_sets_the_support_web():
    project = build_project("shear_beam", "single_plate")
    connection = project.shear_connection
    assert connection.support_element == "web"
    assert connection.support == "W21X62"


def test_starter_shear_projects_have_valid_bolt_groups():
    from openconex.connections.shear.check import validate_shear_connection

    for family in FAMILIES:
        if family.id not in {"shear_column", "shear_beam"}:
            continue
        for subtype in family.subtypes:
            validate_shear_connection(
                build_project(family.id, subtype.id).shear_model())


def test_beam_family_has_its_own_thumbnails():
    column = next(family for family in FAMILIES if family.id == "shear_column")
    beam = next(family for family in FAMILIES if family.id == "shear_beam")
    column_assets = {subtype.asset for subtype in column.subtypes}
    beam_assets = {subtype.asset for subtype in beam.subtypes}
    assert not column_assets & beam_assets
    assert "shear_beam_single_plate" in beam_assets
    assert "shear_beam_skewed_bent_plate" in beam_assets


def test_shear_viewer_swaps_y_and_z():
    mesh = MeshPart("beam", (((0.0, 1.0, 2.0), (0.0, 0.0, 0.0),
                              (1.0, 0.0, 0.0)),))
    swapped = _swap_yz_meshes([mesh])[0]
    assert swapped.triangles[0][0] == (0.0, 2.0, 1.0)


def test_3d_thumbnails_are_packaged():
    for asset in ("base_plate_exposed", "base_plate_embedded", "base_plate_weak",
                  "family_base_plate", "family_shear_column", "family_shear_beam",
                  "shear_double_angle", "shear_single_plate",
                  "shear_extended_plate", "shear_end_plate", "shear_seated",
                  "shear_stiffened_seat", "shear_beam_double_angle",
                  "shear_beam_single_plate", "shear_beam_extended_single_plate",
                  "shear_beam_end_plate", "shear_beam_seated",
                  "shear_beam_stiffened_seat"):
        path = resources.files("openconex.data").joinpath(
            "connections", "thumbs", f"{asset}.png")
        assert path.is_file(), asset


@pytest.mark.parametrize("family", [f for f in FAMILIES],
                         ids=lambda f: f.id)
def test_every_card_asset_is_packaged(family):
    pack = resources.files("openconex.data").joinpath("connections")
    for subtype in family.subtypes:
        png = pack.joinpath("thumbs", f"{subtype.asset}.png")
        svg = pack.joinpath(f"{subtype.asset}.svg")
        assert png.is_file() or svg.is_file(), subtype.asset


@pytest.mark.parametrize("family", [f for f in FAMILIES],
                         ids=lambda f: f.id)
def test_every_card_has_an_isometric_asset(family, app):
    pixmap = connection_pixmap(family.asset, QSize(220, 130))
    assert not pixmap.isNull()
    for subtype in family.subtypes:
        assert not connection_pixmap(subtype.asset, QSize(220, 130)).isNull()


def test_dialog_returns_a_base_plate_selection(dialog):
    base = next(family for family in FAMILIES if family.id == "base_plate")
    dialog._show_family(base)
    assert dialog._stack.currentIndex() == 1
    dialog._select_subtype(base.subtypes[0])
    assert dialog.selection is not None
    assert dialog.selection.kind == "base_plate"
    assert dialog.selection.project is not None


def test_dialog_returns_a_shear_selection(dialog):
    shear = next(family for family in FAMILIES if family.id == "shear_column")
    dialog._show_family(shear)
    dialog._select_subtype(shear.subtypes[0])
    assert dialog.selection is not None
    assert dialog.selection.kind == "shear"
