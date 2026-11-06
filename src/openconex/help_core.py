# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Shared types and table helpers for the OpenConex help registry."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["HELP_TYPE_LEGEND", "HelpItem", "field_item", "table", "ui_item"]

HELP_TYPE_LEGEND = (
    "DA: doble ángulo; PS: placa simple; PSE: placa simple extendida; "
    "PE: placa de extremo; AS: asiento; AR: asiento rigidizado; "
    "PD: placa doblada; PB: placa base; todas: cualquier tipo."
)


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


def field_item(key: str, label: str, group: str, what: str, how: str, effect: str,
               default: str = "—", types: str = "todas") -> HelpItem:
    return HelpItem(key, label, group, what, how, effect, default, types)


def ui_item(key: str, label: str, group: str, what: str, how: str, effect: str,
            default: str = "—", types: str = "todas") -> HelpItem:
    return HelpItem(key, label, group, what, how, effect, default, types)


def table(items: list[HelpItem]) -> str:
    lines = ["| Campo / acción | Qué es | Cómo se usa | Efecto en el cálculo | Defecto | Tipos |",
             "|---|---|---|---|---|---|"]
    for item in items:
        lines.append(f"| `{item.key}` | {item.what} | {item.how} | {item.effect} | "
                     f"{item.default} | {item.types} |")
    return "\n".join(lines)
