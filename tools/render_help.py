# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Regenerate the user reference page from ``openconex.help``."""

from __future__ import annotations

from pathlib import Path

from openconex.help import render_shear_help_markdown

ROOT = Path(__file__).parents[1]
TARGET = ROOT / "docs" / "usuario" / "10-referencia-conexion-corte.md"


def main() -> None:
    TARGET.write_text(render_shear_help_markdown(), encoding="utf-8")
    print(f"wrote {TARGET}")


if __name__ == "__main__":
    main()
