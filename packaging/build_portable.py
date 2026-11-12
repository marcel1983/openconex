# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Build portable PyInstaller bundles for one platform.

Usage: python packaging/build_portable.py windows-x64
"""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
BUILD = ROOT / "build"
PLATFORMS = ("windows-x64", "macos-arm64", "linux-x86_64")
GUI_NAME = "OpenConex"
CLI_BUILD_NAME = "openconex-cli"
CLI_RELEASE_NAME = "openconex"
BRANDING = ROOT / "src" / "openconex" / "data" / "branding"
LICENSES = ROOT / "packaging" / "licenses"

HIDDEN = (
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebChannel",
    "PySide6.QtPrintSupport",
    "PySide6.QtSvg",
)


def run(args: list[str], *, env: dict[str, str] | None = None,
        timeout: int = 1800) -> None:
    print("+", " ".join(str(arg) for arg in args), flush=True)
    subprocess.run([str(arg) for arg in args], cwd=ROOT, env=env, check=True,
                   timeout=timeout)


def pyinstaller(name: str, entry: str, windowed: bool,
                icon: Path | None = None) -> None:
    work = BUILD / f"pyinstaller-{name}"
    specs = BUILD / f"spec-{name}"
    work.mkdir(parents=True, exist_ok=True)
    specs.mkdir(parents=True, exist_ok=True)
    args = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir",
        "--name", name,
        "--distpath", str(DIST),
        "--workpath", str(work),
        "--specpath", str(specs),
        "--paths", str(ROOT / "src"),
        "--collect-all", "openconex",
        "--collect-all", "OCP",
        "--collect-data", "latex2mathml",
    ]
    args += [f"--hidden-import={module}" for module in HIDDEN]
    if icon is not None:
        args += ["--icon", str(icon)]
    args += ["--windowed" if windowed else "--console", entry]
    run(args)


def executable(folder: Path, name: str) -> Path:
    suffix = ".exe" if sys.platform == "win32" else ""
    return folder / f"{name}{suffix}"


def deduplicate_copies(staging: Path,
                       min_size: int = 1_048_576) -> tuple[int, int]:
    """Replace identical large files with relative symlinks before zipping.

    PyInstaller copies the same shared library into several runtime search
    paths, and the GUI and CLI bundles each get their own copy. A ZIP file
    cannot store hardlinks, so keeping every path as a regular file duplicates
    more than two gigabytes. The first path stays as the real file; later
    copies become relative symlinks to it. Files below ``min_size`` are left
    alone because symlinking them saves little and adds noise.
    """
    by_size: dict[int, list[Path]] = {}
    for path in sorted(staging.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        size = path.stat().st_size
        if size >= min_size:
            by_size.setdefault(size, []).append(path)

    seen: dict[str, Path] = {}
    replaced = 0
    saved = 0
    for size, paths in by_size.items():
        if len(paths) < 2:
            continue
        for path in paths:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            first = seen.get(digest)
            if first is None:
                seen[digest] = path
                continue
            target = os.path.relpath(first, start=path.parent)
            path.unlink()
            path.symlink_to(target)
            replaced += 1
            saved += size
    return replaced, saved


def zip_tree(staging: Path, archive: Path) -> None:
    """Zip a PyInstaller onedir, storing Unix symlinks instead of following them."""
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zipped:
        for path in sorted(staging.rglob("*")):
            arcname = (Path(staging.name) / path.relative_to(staging)).as_posix()
            if path.is_symlink():
                info = zipfile.ZipInfo(arcname)
                info.create_system = 3  # Unix
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
                info.compress_type = zipfile.ZIP_STORED
                zipped.writestr(info, os.readlink(path))
            else:
                zipped.write(path, arcname)


def smoke(platform: str) -> None:
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    mac_app = DIST / "OpenConex.app"
    gui = (mac_app / "Contents" / "MacOS" / GUI_NAME if mac_app.exists()
           else executable(DIST / GUI_NAME, GUI_NAME))
    cli = executable(DIST / CLI_BUILD_NAME, CLI_BUILD_NAME)
    if not gui.exists() or not cli.exists():
        raise RuntimeError(f"missing executable: GUI={gui} CLI={cli}")
    if hashlib.sha256(gui.read_bytes()).digest() == hashlib.sha256(
            cli.read_bytes()).digest():
        raise RuntimeError(
            "GUI and CLI executables are identical; use distinct PyInstaller names")
    run([gui, "--version"], env=env, timeout=120)
    run([gui, "--check-assets"], env=env, timeout=120)
    run([cli, "--version"], env=env, timeout=120)
    run([cli, "convert", "3/4 in", "thickness", "--to", "mm"],
        env=env, timeout=120)
    out = BUILD / "smoke" / platform
    shutil.rmtree(out, ignore_errors=True)
    run([cli, "baseplate", "examples/base_plate_dg1_4_7_11.ocnx",
         "--html", "-o", str(out / "base")], env=env, timeout=600)
    run([cli, "shear", "examples/shear_single_plate.ocnx",
         "--html", "-o", str(out / "shear")], env=env, timeout=600)
    run([cli, "moment", "examples/moment_bolted_flange_plate.ocnx",
         "--html", "-o", str(out / "moment")], env=env, timeout=600)
    print(f"smoke tests OK for {platform}", flush=True)


def verify_archive(platform: str, archive: Path) -> None:
    """Extract the published zip and run the GUI and CLI from the result.

    This catches broken symlinks, missing Qt/OCP libraries and permission
    problems that do not appear when testing the PyInstaller ``dist`` folders.
    """
    target = BUILD / "verify" / platform
    shutil.rmtree(target, ignore_errors=True)
    target.mkdir(parents=True)
    if sys.platform == "darwin":
        run(["ditto", "-x", "-k", str(archive), str(target)])
    elif sys.platform.startswith("linux"):
        run(["unzip", "-q", str(archive), "-d", str(target)])
    else:
        with zipfile.ZipFile(archive) as zipped:
            zipped.extractall(target)

    root = target / archive.stem
    for relative in ("LICENSE", "licenses/PySide6/LGPL-3.0-only.txt",
                     "licenses/OpenCASCADE/LGPL-2.1.txt"):
        if not (root / relative).is_file():
            raise RuntimeError(f"missing {relative} in {archive.name}")
    mac_app = root / "OpenConex.app"
    gui = (mac_app / "Contents" / "MacOS" / GUI_NAME if mac_app.exists()
           else executable(root / GUI_NAME, GUI_NAME))
    cli = executable(root / CLI_BUILD_NAME, CLI_RELEASE_NAME)
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    run([gui, "--version"], env=env, timeout=120)
    run([gui, "--check-assets"], env=env, timeout=120)
    run([cli, "--version"], env=env, timeout=120)
    out = target / "smoke"
    run([cli, "shear", "examples/shear_single_plate.ocnx", "--pdf", "--step",
         "-o", str(out / "shear")], env=env, timeout=900)
    print(f"extracted archive OK for {platform}", flush=True)


def package(platform: str) -> Path:
    from openconex import __version__

    staging = BUILD / "portable" / f"OpenConex-{__version__}-{platform}"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    mac_app = DIST / f"{GUI_NAME}.app"
    if mac_app.exists():
        # ditto preserves the framework symlinks inside the .app bundle.
        run(["ditto", str(mac_app), str(staging / "OpenConex.app")])
        run(["ditto", str(DIST / CLI_BUILD_NAME), str(staging / "openconex-cli")])
    else:
        shutil.copytree(DIST / GUI_NAME, staging / "OpenConex")
        shutil.copytree(DIST / CLI_BUILD_NAME, staging / "openconex-cli")
    cli_binary = executable(staging / "openconex-cli", CLI_BUILD_NAME)
    cli_binary.replace(executable(staging / "openconex-cli", CLI_RELEASE_NAME))
    for source, target in (
            (ROOT / "LICENSE", staging / "LICENSE"),
            (ROOT / "packaging" / "README-portable.txt", staging / "LEEME.txt"),
            (ROOT / "src" / "openconex" / "data" / "shapes" / "NOTICE.md",
             staging / "NOTICE-AISC.md")):
        if source.exists():
            shutil.copy2(source, target)
    if not LICENSES.is_dir():
        raise RuntimeError(f"missing third-party licenses: {LICENSES}")
    shutil.copytree(LICENSES, staging / "licenses")
    if sys.platform.startswith("linux"):
        replaced, saved = deduplicate_copies(staging)
        print(f"identical files replaced by symlinks: {replaced} "
              f"({saved / 1048576:.1f} MiB saved)", flush=True)

    archive = DIST / f"OpenConex-{__version__}-{platform}.zip"
    archive.unlink(missing_ok=True)
    if platform.startswith("macos"):
        run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent",
             str(staging), str(archive)])
    else:
        zip_tree(staging, archive)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    checksum = DIST / f"SHA256SUMS-{platform}.txt"
    checksum.write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
    print(f"archive: {archive} ({archive.stat().st_size / 1_048_576:.1f} MiB)",
          flush=True)
    verify_archive(platform, archive)
    return archive


def platform_icon() -> Path | None:
    if sys.platform == "win32":
        path = BRANDING / "icon.ico"
        if not path.exists():
            raise RuntimeError(f"missing Windows icon: {path}")
        return path
    if sys.platform == "darwin":
        iconset = BUILD / "openconex.iconset"
        shutil.rmtree(iconset, ignore_errors=True)
        iconset.mkdir(parents=True)
        mapping = {
            "icon_16x16.png": 16,
            "icon_16x16@2x.png": 32,
            "icon_32x32.png": 32,
            "icon_32x32@2x.png": 64,
            "icon_128x128.png": 128,
            "icon_128x128@2x.png": 256,
            "icon_256x256.png": 256,
            "icon_256x256@2x.png": 512,
            "icon_512x512.png": 512,
            "icon_512x512@2x.png": 1024,
        }
        for name, size in mapping.items():
            shutil.copy2(BRANDING / f"icon-{size}.png", iconset / name)
        output = BUILD / "openconex.icns"
        output.unlink(missing_ok=True)
        run(["iconutil", "-c", "icns", str(iconset), "-o", str(output)])
        return output
    return None


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in PLATFORMS:
        print(f"usage: {sys.argv[0]} {'|'.join(PLATFORMS)}", file=sys.stderr)
        return 2
    platform = sys.argv[1]
    DIST.mkdir(exist_ok=True)
    icon = platform_icon()
    pyinstaller(GUI_NAME, "packaging/gui_entry.py", windowed=True, icon=icon)
    pyinstaller(CLI_BUILD_NAME, "packaging/cli_entry.py", windowed=False,
                icon=icon if sys.platform == "win32" else None)
    smoke(platform)
    package(platform)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
