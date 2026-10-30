# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Translation catalogs for reports and messages (Spanish and English).

Catalogs are TOML files named after the language code. Keys are dotted
(``check.bolt.shear``); code references such as clause numbers are never
translated.
"""

from __future__ import annotations

import tomllib
from functools import cache
from importlib import resources

__all__ = ["DEFAULT_LANGUAGE", "LANGUAGES", "catalog", "tr"]

LANGUAGES = ("es", "en")
DEFAULT_LANGUAGE = "es"


def _flatten(table: dict, prefix: str = "") -> dict[str, str]:
    flat: dict[str, str] = {}
    for key, value in table.items():
        name = f"{prefix}{key}"
        if isinstance(value, dict):
            flat.update(_flatten(value, f"{name}."))
        else:
            flat[name] = str(value)
    return flat


@cache
def catalog(lang: str) -> dict[str, str]:
    """All messages of ``lang`` as a flat ``{key: text}`` mapping."""
    if lang not in LANGUAGES:
        raise ValueError(f"unsupported language: {lang!r} (available: {', '.join(LANGUAGES)})")
    data = resources.files(__package__).joinpath(f"{lang}.toml").read_text(encoding="utf-8")
    return _flatten(tomllib.loads(data))


def tr(key: str, lang: str = DEFAULT_LANGUAGE, **values: object) -> str:
    """Translate ``key`` into ``lang``, filling ``{placeholders}`` from ``values``.

    Falls back to English, then to the key itself, so a missing translation
    never breaks a report.
    """
    text = catalog(lang).get(key) or catalog("en").get(key) or key
    return text.format(**values) if values else text
