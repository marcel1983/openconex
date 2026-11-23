# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Check that a release tag matches ``openconex.__version__``.

Usage: python tools/check_release_version.py v0.5.21

The release workflow runs this before building anything, so a tag pushed
without bumping ``src/openconex/__init__.py`` (or the other way round) fails
early instead of publishing wheels and installers with the wrong version.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INIT = ROOT / "src" / "openconex" / "__init__.py"
VERSION_RE = re.compile(r'^__version__\s*=\s*["\']([^"\']+)["\']', re.MULTILINE)
# Final releases and pre-releases accepted by PyPI (PEP 440 subset we use).
TAG_RE = re.compile(r"^v(\d+\.\d+\.\d+(?:(?:a|b|rc)\d+)?(?:\.post\d+)?)$")


def package_version(init: Path = INIT) -> str:
    match = VERSION_RE.search(init.read_text(encoding="utf-8"))
    if match is None:
        raise ValueError(f"__version__ not found in {init}")
    return match.group(1)


def tag_version(tag: str) -> str:
    tag = tag.removeprefix("refs/tags/")
    match = TAG_RE.match(tag)
    if match is None:
        raise ValueError(
            f"tag {tag!r} does not look like v<major>.<minor>.<patch>[aN|bN|rcN]")
    return match.group(1)


def check(tag: str, init: Path = INIT) -> str:
    """Return the version, or raise ``ValueError`` when tag and code differ."""
    expected = tag_version(tag)
    actual = package_version(init)
    if expected != actual:
        raise ValueError(
            f"tag {tag!r} is version {expected} but __version__ is {actual} "
            f"in {init.relative_to(ROOT) if init.is_relative_to(ROOT) else init}")
    return actual


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("usage: check_release_version.py <tag>", file=sys.stderr)
        return 2
    try:
        version = check(args[0])
    except ValueError as error:
        print(f"::error::{error}", file=sys.stderr)
        return 1
    print(f"release version OK: {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
