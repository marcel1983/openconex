# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""PyInstaller entry point for the desktop application."""

from openconex.gui import main

if __name__ == "__main__":
    raise SystemExit(main())
