# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Loader of the help catalog (``i18n/help.<lang>.toml``) and its shared helpers."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from functools import cache
from importlib import resources
from typing import Any

__all__ = ["HELP_LANGUAGE", "HELP_TYPE_LEGEND", "HelpItem", "help_catalog", "help_items",
           "render_page", "table"]

HELP_LANGUAGE = "es"
"""Language of the help; only Spanish has a catalog for now."""


@dataclass(frozen=True)
class HelpItem:
    key: str
    label: str
    group: str
    what: str
    how: str
    effect: str
    default: str = "—"
    types: str = "todas"


@cache
def help_catalog(lang: str = HELP_LANGUAGE) -> dict[str, Any]:
    """The whole help catalog of ``lang`` as read from its TOML file."""
    data = resources.files("openconex.i18n").joinpath(f"help.{lang}.toml")
    return tomllib.loads(data.read_text(encoding="utf-8"))


def help_items(section: str, part: str, lang: str = HELP_LANGUAGE) -> list[HelpItem]:
    """Entries of ``[[section.part]]`` (for example ``shear.fields``), in file order."""
    return [HelpItem(**entry) for entry in help_catalog(lang)[section][part]]


HELP_TYPE_LEGEND: str = help_catalog()["legend"]


def table(items: list[HelpItem], lang: str = HELP_LANGUAGE) -> str:
    header = help_catalog(lang)["table_header"]
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    for item in items:
        lines.append(f"| `{item.key}` | {item.what} | {item.how} | {item.effect} | "
                     f"{item.default} | {item.types} |")
    return "\n".join(lines)


def render_page(page: str, fields: list[HelpItem], menus: list[HelpItem],
                checks: list[HelpItem] | None = None, lang: str = HELP_LANGUAGE) -> str:
    """Reference page ``pages.<page>``: fields by group, menus, checks and how to read one."""
    text = help_catalog(lang)
    p = text["pages"][page]
    parts = [f"# {p['title']}", "", p["intro"], "",
             f"**{text['types_label']}:** {text['legend']}", "",
             f"## {p['fields_heading']}", ""]
    for group in p["groups"]:
        items = [item for item in fields if item.group == group]
        if items:
            parts += [f"### {group}", "", table(items, lang), ""]
    parts += [f"## {text['menus_heading']}", "", table(menus, lang), ""]
    if checks is not None:
        parts += [f"## {p['checks_heading']}", "", table(checks, lang), ""]
    parts += [f"## {text['reading_heading']}", ""]
    parts += [f"{n}. {line}" for n, line in enumerate(p["reading"], start=1)]
    parts.append("")
    if p["closing"]:
        parts += [p["closing"], ""]
    return "\n".join(parts)
