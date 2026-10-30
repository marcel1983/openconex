# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Fail if an installed runtime dependency has a license incompatible with GPL-3.0.

Run in an environment where only ``pip install .`` was done (no dev extras):

    python tools/check_licenses.py
"""

from __future__ import annotations

import json
import subprocess
import sys

# Substrings of license names compatible with distribution under GPL-3.0.
ALLOWED = (
    "MIT", "BSD", "Apache", "ISC", "PSF", "Python Software Foundation",
    "LGPL", "GNU Lesser General Public License",
    "GPL-3", "GPLv3", "GNU General Public License v3", "MPL-2.0", "Mozilla Public License 2.0",
    "Unlicense", "Zlib", "CC0",
)
# Tooling present in any virtualenv, not shipped with OpenConex.
IGNORED = {"pip", "setuptools", "wheel", "pip-licenses", "prettytable", "wcwidth", "openconex"}


def main() -> int:
    out = subprocess.run(
        [sys.executable, "-m", "piplicenses", "--format=json", "--from=mixed"],
        check=True, capture_output=True, text=True,
    ).stdout
    bad = [
        f"{pkg['Name']} {pkg['Version']}: {pkg['License']}"
        for pkg in json.loads(out)
        if pkg["Name"].lower() not in IGNORED
        and not any(token.lower() in pkg["License"].lower() for token in ALLOWED)
    ]
    if bad:
        print("Dependencies with a license not on the GPL-3.0 allow-list:")
        print("\n".join(f"  - {line}" for line in bad))
        return 1
    print("All runtime dependency licenses are GPL-3.0 compatible.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
