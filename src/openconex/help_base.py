# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Help of the base-plate window and the main application (``base`` in the help catalog)."""

from __future__ import annotations

from openconex.help_core import HelpItem, help_items, render_page

__all__ = ["BASE_ITEMS", "render_base_help_markdown"]

_FIELDS = help_items("base", "fields")
_UI = help_items("base", "ui")

BASE_ITEMS: dict[str, HelpItem] = {
    item.key: item for item in _FIELDS + _UI
}


def render_base_help_markdown() -> str:
    """Generated reference page of the base plate (docs/usuario/11)."""
    return render_page("base", _FIELDS, _UI)
