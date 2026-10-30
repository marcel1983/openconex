# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Repository hygiene: license headers and CLI entry point."""

from pathlib import Path

from openconex import __version__
from openconex.cli import main

ROOT = Path(__file__).resolve().parents[1]
SPDX = "SPDX-License-Identifier: GPL-3.0-or-later"


def test_every_python_file_has_spdx_header():
    missing = [
        str(p.relative_to(ROOT))
        for folder in ("src", "tests", "tools")
        for p in (ROOT / folder).rglob("*.py")
        if SPDX not in p.read_text(encoding="utf-8").splitlines()[0]
    ]
    assert not missing, f"missing SPDX header: {missing}"


def test_cli_convert(capsys):
    assert main(["convert", "3/4 in", "thickness", "--to", "mm"]) == 0
    assert capsys.readouterr().out.strip() == "19.05 mm"
    assert main(["convert", "10 tf", "force", "--system", "US"]) == 0
    assert capsys.readouterr().out.strip() == "22.05 kip"
    assert main(["convert", "10 mm", "force", "--to", "kN"]) == 2


def test_version():
    assert __version__.count(".") == 2
