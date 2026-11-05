# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Portable packaging helpers."""

from __future__ import annotations

import importlib.util
import stat
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]


def _build_portable():
    spec = importlib.util.spec_from_file_location(
        "openconex_build_portable", ROOT / "packaging" / "build_portable.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_license_bundle_present():
    base = ROOT / "packaging" / "licenses"
    for relative in (
            "PySide6/LGPL-3.0-only.txt",
            "OpenCASCADE/LGPL-2.1.txt",
            "OpenCASCADE/OCCT_LGPL_EXCEPTION.txt",
            "PyInstaller/COPYING.txt",
            "Python/LICENSE.txt"):
        assert (base / relative).is_file(), relative


def test_zip_tree_preserves_symlinks(tmp_path):
    module = _build_portable()
    staging = tmp_path / "OpenConex-0.0.0-test"
    staging.mkdir()
    target = staging / "file.txt"
    target.write_text("ok", encoding="utf-8")
    link = staging / "lib.so"
    try:
        link.symlink_to("file.txt")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are not available for this user")
    archive = tmp_path / "portable.zip"
    module.zip_tree(staging, archive)
    with zipfile.ZipFile(archive) as zipped:
        info = zipped.getinfo("OpenConex-0.0.0-test/lib.so")
        assert stat.S_ISLNK(info.external_attr >> 16)
        assert zipped.read(info) == b"file.txt"
        assert zipped.read("OpenConex-0.0.0-test/file.txt") == b"ok"


def test_deduplicate_copies(tmp_path):
    module = _build_portable()
    staging = tmp_path / "OpenConex-0.0.0-test"
    staging.mkdir()
    first = staging / "a.bin"
    first.write_bytes(b"same")
    duplicate = staging / "sub" / "z.bin"
    duplicate.parent.mkdir()
    duplicate.write_bytes(b"same")
    different = staging / "other.bin"
    different.write_bytes(b"diff")
    try:
        replaced, saved = module.deduplicate_copies(staging, min_size=1)
    except OSError:
        pytest.skip("symlinks are not available for this user")
    assert replaced == 1
    assert saved == 4
    assert duplicate.is_symlink()
    assert duplicate.read_bytes() == b"same"
    assert not different.is_symlink()
