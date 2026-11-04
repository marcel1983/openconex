# SPDX-License-Identifier: GPL-3.0-or-later
"""Build portable PyInstaller bundles for one platform.

Usage: python packaging/build_portable.py windows-x64
"""

from __future__ import annotations

import hashlib
import os
import shutil
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
    print(f"smoke tests OK for {platform}", flush=True)


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

    archive = DIST / f"OpenConex-{__version__}-{platform}.zip"
    archive.unlink(missing_ok=True)
    if platform.startswith("macos"):
        run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent",
             str(staging), str(archive)])
    else:
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zipped:
            for path in sorted(staging.rglob("*")):
                arcname = Path(staging.name) / path.relative_to(staging)
                zipped.write(path, arcname)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    checksum = DIST / f"SHA256SUMS-{platform}.txt"
    checksum.write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
    print(f"archive: {archive} ({archive.stat().st_size / 1_048_576:.1f} MiB)",
          flush=True)
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
