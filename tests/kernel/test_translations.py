# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Every check produced by the kernel has a title in every language."""

import pytest

from openconex.core.bolting import min_pretension
from openconex.core.loads import Method
from openconex.core.model import BoltSpec, FilletWeld, IShape
from openconex.i18n import LANGUAGES, catalog
from openconex.kernel import bolt_group, bolts, elements, local, prying, weld_group, welds

M = Method.LRFD
B = BoltSpec(diameter=19.05)
W = IShape(name="W", d=356, bf=368, tf=18, tw=11.2, k_des=33)


def all_checks():
    out = [
        bolts.bolt_tension(B, 0, M), bolts.bolt_shear(B, 0, M),
        bolts.bolt_tension_shear(B, 0, 0, M), bolts.bolt_slip(B, 0, M, min_pretension(0.75)),
        bolts.bolt_bearing(B, 10, 400, 0, M), bolts.bolt_tearout(B, 10, 400, 20, 0, M),
        *bolts.bolt_spacing_checks(B, 76, 32, 10),
        welds.fillet_weld(FilletWeld(size=6, length=100), 0, M),
        welds.pjp_weld(6, 100, 482, 0, M, True), *welds.fillet_size_checks(6, 100, 10, 10),
        elements.tension_yielding(1, 1, 0, M), elements.tension_rupture(1, 1, 0, M),
        elements.shear_yielding(1, 1, 0, M), elements.shear_rupture(1, 1, 0, M),
        elements.block_shear(1, 1, 1, 1, 1, 0, M), elements.compression(1, 250, 30, 0, M),
        elements.flexural_yielding(1, 1, 0, M), elements.flexural_rupture(1, 1, 0, M),
        prying.prying_tension(1e5, 15, 40, 40, 76, 19, 21, 450, 0, M),
        prying.prying_min_thickness(1e5, 40, 76, 19, 450, 15, M),
        bolt_group.bolt_group_eccentric([(0, 0), (0, 76)], (50, 0), 1e5, 0, M),
        weld_group.weld_group_eccentric([weld_group.WeldLine(0, 0, 0, 200)], 6, 482, (50, 100),
                                        0, M),
        local.flange_local_bending(W, 0, M), local.web_local_yielding(W, 100, 0, M),
        local.web_local_crippling(W, 100, 0, M), local.web_compression_buckling(W, 0, M),
        local.panel_zone_shear(W, 0, 0, M),
    ]
    return out


@pytest.mark.parametrize("lang", LANGUAGES)
def test_every_check_is_translated(lang):
    texts = catalog(lang)
    missing = sorted({r.text_id for r in all_checks()} - set(texts))
    assert not missing, f"{lang}: missing translations {missing}"
