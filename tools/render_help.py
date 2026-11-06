# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Regenerate the user reference page from ``openconex.help``."""

from __future__ import annotations

from pathlib import Path

from openconex.help import render_base_help_markdown, render_shear_help_markdown

ROOT = Path(__file__).parents[1]
TARGET = ROOT / "docs" / "usuario" / "10-referencia-conexion-corte.md"
BASE_TARGET = ROOT / "docs" / "usuario" / "11-referencia-placa-base.md"


def main() -> None:
    TARGET.write_text(render_shear_help_markdown(), encoding="utf-8")
    BASE_TARGET.write_text(render_base_help_markdown(), encoding="utf-8")
    print(f"wrote {TARGET}")
    print(f"wrote {BASE_TARGET}")


if __name__ == "__main__":
    main()
