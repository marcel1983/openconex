# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Single source of truth for the user help (GUI tooltips, Help dialog and the
generated user reference, ``tools/render_help.py``).

The entries live in ``i18n/help.es.toml``. Each one answers three questions:
what the item is, how it is used, and how it affects the calculation. This
module exposes the shear-connection entries plus the base-plate ones
(:mod:`openconex.help_base`) under one key index.

The registry is deliberately UI-independent so it can be tested and rendered
without PySide6.
"""

from __future__ import annotations

from openconex.help_base import BASE_ITEMS, render_base_help_markdown
from openconex.help_core import HELP_TYPE_LEGEND, HelpItem, help_catalog, help_items, render_page

__all__ = [
    "HELP_ITEMS",
    "HelpItem",
    "help_item",
    "help_text",
    "render_base_help_markdown",
    "render_shear_help_markdown",
    "shear_fields",
    "shear_menus",
]

TYPE_LEGEND = HELP_TYPE_LEGEND

_FIELDS = help_items("shear", "fields")
_MENUS = help_items("shear", "menus")
_CHECKS = help_items("shear", "checks")

HELP_ITEMS: dict[str, HelpItem] = {
    item.key: item for item in _FIELDS + _MENUS + _CHECKS
}

HELP_ITEMS.update(BASE_ITEMS)


def help_item(key: str) -> HelpItem:
    """Help entry for a field, menu or UI key; raises if it is missing."""
    return HELP_ITEMS[key]


def help_text(key: str) -> str:
    """Plain-text tooltip for a field or action."""
    item = help_item(key)
    return str(help_catalog()["tooltip"]).format(what=item.what, how=item.how,
                                                 effect=item.effect)


def shear_fields() -> list[HelpItem]:
    return [item for item in _FIELDS if item.key in HELP_ITEMS]


def shear_menus() -> list[HelpItem]:
    return [item for item in _MENUS if item.key in HELP_ITEMS]


def render_shear_help_markdown() -> str:
    """Generated reference page of the shear connection (docs/usuario/10)."""
    return render_page("shear", _FIELDS, _MENUS, _CHECKS)
