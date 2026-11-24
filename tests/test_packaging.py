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


def _load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _installer():
    return _load("openconex_build_installer", "packaging/build_installer.py")


def _release_version():
    return _load("openconex_check_release_version", "tools/check_release_version.py")


def test_release_version_matches_package():
    module = _release_version()
    from openconex import __version__
    assert module.package_version() == __version__
    assert module.check(f"v{__version__}") == __version__
    assert module.check(f"refs/tags/v{__version__}") == __version__


@pytest.mark.parametrize("tag", ["v9.9.9", "0.5.20", "v0.5", "release-1"])
def test_release_version_rejects_mismatch(tag):
    module = _release_version()
    with pytest.raises(ValueError):
        module.check(tag)
    assert module.main([tag]) == 1


def test_release_version_accepts_prereleases(tmp_path):
    module = _release_version()
    init = tmp_path / "__init__.py"
    init.write_text('__version__ = "0.6.0rc1"\n', encoding="utf-8")
    assert module.check("v0.6.0rc1", init) == "0.6.0rc1"
    with pytest.raises(ValueError):
        module.check("v0.6.0", init)


def test_msi_numeric_version():
    module = _installer()
    assert module.numeric_version("0.5.20") == "0.5.20"
    assert module.numeric_version("0.6.0rc1") == "0.6.0"
    with pytest.raises(ValueError):
        module.numeric_version("dev")
    with pytest.raises(ValueError):
        module.numeric_version("256.0.0")


def test_wix_source_is_valid_xml(tmp_path):
    import xml.etree.ElementTree as ET

    module = _installer()
    text = module.wix_source(tmp_path / "staging", tmp_path / "icon.ico", "1.2.3")
    root = ET.fromstring(text)
    ns = {"w": "http://wixtoolset.org/schemas/v4/wxs"}
    package = root.find("w:Package", ns)
    assert package is not None
    assert package.get("Version") == "1.2.3"
    assert package.get("UpgradeCode") == module.UPGRADE_CODE
    assert package.get("Scope") == "perMachine"
    assert package.find("w:MajorUpgrade", ns) is not None
    files = root.find(".//w:Directory[@Id='INSTALLFOLDER']/w:Files", ns)
    assert files is not None and files.get("Include", "").endswith("**")
    shortcut = root.find(".//w:Shortcut", ns)
    assert shortcut is not None
    assert shortcut.get("Target", "").endswith("OpenConex\\OpenConex.exe")
    path = root.find(".//w:Environment", ns)
    assert path is not None and path.get("Permanent") == "no"


def test_desktop_entry_fields():
    module = _installer()
    lines = module.desktop_entry().splitlines()
    assert lines[0] == "[Desktop Entry]"
    fields = dict(line.split("=", 1) for line in lines[1:])
    for key in ("Type", "Name", "Exec", "Icon", "Categories"):
        assert fields[key], key
    assert fields["Icon"] == "openconex"
    assert fields["Categories"].endswith(";")


@pytest.mark.skipif(not Path("/bin/sh").exists(), reason="needs a POSIX shell")
def test_appimage_apprun_dispatch(tmp_path):
    import subprocess

    module = _installer()
    staging = tmp_path / "staging"
    for folder, name in (("OpenConex", "OpenConex"), ("openconex-cli", "openconex")):
        exe = staging / folder / name
        exe.parent.mkdir(parents=True)
        exe.write_text(f'#!/bin/sh\necho "{name} $*"\n', encoding="utf-8")
        exe.chmod(0o755)
    try:
        appdir = module.build_appdir(staging, tmp_path / "OpenConex.AppDir")
    except OSError:
        pytest.skip("symlinks are not available for this user")
    assert (appdir / "openconex.desktop").is_file()
    assert (appdir / ".DirIcon").is_symlink()
    apprun = str(appdir / "AppRun")

    def call(*args, argv0=None):
        env = {"PATH": "/usr/bin:/bin"}
        if argv0:
            env["ARGV0"] = argv0
        return subprocess.run([apprun, *args], capture_output=True, text=True,
                              env=env, check=True).stdout.strip()

    assert call("--version") == "OpenConex --version"
    assert call("--cli", "--version") == "openconex --version"
    assert call("--version", argv0="/usr/local/bin/openconex") == "openconex --version"


def test_write_checksums(tmp_path, monkeypatch):
    import hashlib

    module = _installer()
    monkeypatch.setattr(module, "DIST", tmp_path)
    first = tmp_path / "a.zip"
    first.write_bytes(b"a")
    second = tmp_path / "b.msi"
    second.write_bytes(b"b")
    checksum = module.write_checksums("windows-x64", [first, second])
    assert checksum.name == "SHA256SUMS-windows-x64.txt"
    assert checksum.read_text(encoding="utf-8").splitlines() == [
        f"{hashlib.sha256(b'a').hexdigest()}  a.zip",
        f"{hashlib.sha256(b'b').hexdigest()}  b.msi",
    ]


def test_macho_detection(tmp_path):
    module = _installer()
    binary = tmp_path / "lib.dylib"
    binary.write_bytes(bytes.fromhex("cffaedfe") + b"\0" * 12)
    text = tmp_path / "script.py"
    text.write_text("print('x')\n", encoding="utf-8")
    assert module.is_macho(binary)
    assert not module.is_macho(text)
    assert not module.is_macho(tmp_path)


def test_pypi_readme_has_absolute_links():
    import re
    import tomllib

    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    hook = config["tool"]["hatch"]["metadata"]["hooks"]["fancy-pypi-readme"]
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    for substitution in hook["substitutions"]:
        text = re.sub(substitution["pattern"], substitution["replacement"], text)
    relative_links = re.findall(r"\]\((?!https?://|#)[^)]+\)", text)
    relative_attrs = re.findall(r'(?:src|href)="(?!https?://|#)[^"]+"', text)
    assert not relative_links
    assert not relative_attrs


def test_portable_build_uses_exact_versions():
    """release.yml installs the portable dependencies from the constraints file,
    and every runtime dependency of the package is pinned there."""
    import re
    import tomllib

    release = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert 'pip install -c packaging/constraints-portable.txt -e ".[gui,pdf,3d]"' in release
    pins = {}
    for line in (ROOT / "packaging" / "constraints-portable.txt").read_text(
            encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            name, version = line.split("==")
            pins[re.sub(r"[-_.]+", "-", name).lower()] = version
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    required = [*project["dependencies"], *project["optional-dependencies"]["gui"],
                *project["optional-dependencies"]["3d"], "pyinstaller"]
    names = {re.sub(r"[-_.]+", "-", re.split(r"[<>=!~\[ ;]", dep)[0]).lower()
             for dep in required}
    assert not names - pins.keys(), f"not pinned: {sorted(names - pins.keys())}"
