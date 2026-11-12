# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Column web panel zone of a beam-to-column moment connection (AISC 360-22 §J10.6).

The panel zone shear is the flange force of the beam (both beams with
``two_sided``) less the story shear in the column above the joint. A doubler
plate adds its thickness to the web (§J10.6 and Commentary; AISC Design
Guide 13).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from openconex.core.checks import CheckResult
from openconex.core.loads import Method
from openconex.kernel import local

if TYPE_CHECKING:
    from .fr_moment import MomentConnection

__all__ = ["panel_zone_check"]


def panel_zone_check(mc: MomentConnection, flange_force: float, column_shear: float,
                     column_axial: float, method: Method, combo: str = "") -> list[CheckResult]:
    """``moment.column_panel_zone`` for the flange force and the column forces, and the
    weld of a fillet-welded doubler plate for the shear it carries."""
    from .column_stiffening import doubler_checks
    demand = abs((2 * flange_force if mc.two_sided else flange_force) - column_shear)
    kw = {"beam_depth": mc.beam.d, "inelastic": mc.panel_zone_inelastic, "combo": combo}
    check = local.panel_zone_shear(mc.column, column_axial, demand, method,
                                   doubler=mc.doubler_plate, doubler_Fy=mc.plate_Fy or None,
                                   **kw)
    out = [check.model_copy(update={"id": "moment.column_panel_zone",
                                    "text_id": "check.moment.column_panel_zone"})]
    if mc.doubler_plate > 0 and mc.doubler_weld > 0:
        web = local.panel_zone_shear(mc.column, column_axial, demand, method, **kw).capacity
        out += [r for r in doubler_checks(mc, method, combo, demand, web)
                if r.id == "moment.doubler_plate_weld"]
    return out
