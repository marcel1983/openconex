# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
import ezdxf
import pytest

from openconex.drawing.base_plate import LAYERS, BasePlateDrawing, anchor_hole, write_base_plate_dxf
from openconex.io.project import HSSSectionInput
from openconex.units import PRESETS, Kind, from_internal, to_internal


def _write(tmp_path, project, units, lang):
    bp = project.base_plate_model()
    return write_base_plate_dxf(bp, tmp_path / f"bp_{lang}.dxf", PRESETS[units], lang,
                                BasePlateDrawing(pedestal_N=to_internal(36, "in", Kind.LENGTH),
                                                 pedestal_B=to_internal(36, "in", Kind.LENGTH),
                                                 title="Test", number="T-1"))


def test_dxf_is_valid_and_layered(tmp_path, project):
    doc = ezdxf.readfile(_write(tmp_path, project, "US", "es"))
    assert doc.dxfversion == "AC1027"  # R2013
    assert not doc.audit().has_errors
    assert set(LAYERS) <= {layer.dxf.name for layer in doc.layers}
    assert doc.header["$INSUNITS"] == 1  # inches
    msp = doc.modelspace()
    for layer in LAYERS:
        assert len(msp.query(f'*[layer=="{layer}"]')) > 0, layer


def test_dimensions_match_the_plate(tmp_path, project):
    doc = ezdxf.readfile(_write(tmp_path, project, "US", "en"))
    values = sorted(round(d.get_measurement(), 3) for d in doc.modelspace().query("DIMENSION"))
    for expected in (24.0, 22.0, 18.5, 12.0, 2.0, 1.5, 18.0):  # N, B, 2f, s, tp, grout, hef
        assert expected in values


def test_metric_drawing(tmp_path, project):
    doc = ezdxf.readfile(_write(tmp_path, project, "SI_N_mm", "en"))
    assert doc.header["$INSUNITS"] == 4  # millimetres
    values = [d.get_measurement() for d in doc.modelspace().query("DIMENSION")]
    assert any(v == pytest.approx(609.6) for v in values)


@pytest.mark.parametrize(("lang", "words"), [("es", ["PLANTA", "ELEVACIÓN", "LISTA DE MATERIALES"]),
                                             ("en", ["PLAN", "ELEVATION", "BILL OF MATERIALS"])])
def test_texts_are_translated(tmp_path, project, lang, words):
    doc = ezdxf.readfile(_write(tmp_path, project, "US", lang))
    texts = " ".join(t.dxf.text for t in doc.modelspace().query("TEXT"))
    for word in words:
        assert word in texts


def test_hss_column_outline(tmp_path, project):
    project.base_plate.column = HSSSectionInput(
        type="HSS", shape="round", d="12 in", t="0.5 in",
        grade="ASTM A500 Gr. C (round)")
    doc = ezdxf.readfile(_write(tmp_path, project, "US", "en"))
    assert len(doc.modelspace().query('CIRCLE[layer=="BP-COLUMNA"]')) == 2

    project.base_plate.column = HSSSectionInput(
        type="HSS", shape="rectangular", d="12 in", bf="8 in", t="0.5 in",
        grade="ASTM A500 Gr. C (rectangular)")
    doc = ezdxf.readfile(_write(tmp_path, project, "US", "es"))
    # Two concentric outlines in plan plus the two tube walls in elevation.
    assert len(doc.modelspace().query('LWPOLYLINE[layer=="BP-COLUMNA"]')) == 4


def test_anchor_hole_table_14_2():
    assert from_internal(anchor_hole(to_internal(1.0, "in", Kind.LENGTH)), Kind.LENGTH, "in") == \
        pytest.approx(1.875)
