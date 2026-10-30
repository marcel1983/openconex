# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
import pytest

from openconex.core.checks import Status
from openconex.core.loads import LoadType
from openconex.i18n import LANGUAGES, catalog, tr
from openconex.units import Kind


def test_catalogs_have_the_same_keys():
    keys = [set(catalog(lang)) for lang in LANGUAGES]
    assert all(k == keys[0] for k in keys)


@pytest.mark.parametrize("lang", LANGUAGES)
def test_enums_are_translated(lang):
    texts = catalog(lang)
    for kind in Kind:
        assert f"kind.{kind.value}" in texts
    for status in Status:
        assert f"status.{status.value}" in texts
    for load in LoadType:
        assert f"load.{load.value}" in texts


def test_tr():
    assert tr("check.anchor.pryout", "es") == "Desprendimiento del concreto por palanca"
    assert tr("check.anchor.pryout", "en") == "Concrete pryout"
    text = tr("report.governing", "es", check="Corte", ratio=0.876, combo="LRFD-2")
    assert text == "Verificación gobernante: Corte (relación 0.88, LRFD-2)"
    assert tr("missing.key", "es") == "missing.key"
    with pytest.raises(ValueError):
        tr("app.name", "fr")
