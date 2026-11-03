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


def pyinstaller(name: str, entry: str, windowed: bool) -> None:
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
    args += ["--windowed" if windowed else "--console", entry]
    run(args)


def executable(folder: Path, name: str) -> Path:
    suffix = ".exe" if sys.platform == "win32" else ""
    return folder / f"{name}{suffix}"


def smoke(platform: str) -> None:
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    mac_app = DIST / "OpenConex.app"
    gui = (mac_app / "Contents" / "MacOS" / "OpenConex" if mac_app.exists()
           else executable(DIST / "OpenConex", "OpenConex"))
    cli = executable(DIST / "openconex", "openconex")
    if not gui.exists() or not cli.exists():
        raise RuntimeError(f"missing executable: GUI={gui} CLI={cli}")
    run([gui, "--version"], env=env, timeout=120)
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
    mac_app = DIST / "OpenConex.app"
    if mac_app.exists():
        # ditto preserves the framework symlinks inside the .app bundle.
        run(["ditto", str(mac_app), str(staging / "OpenConex.app")])
        run(["ditto", str(DIST / "openconex"), str(staging / "openconex-cli")])
    else:
        shutil.copytree(DIST / "OpenConex", staging / "OpenConex")
        shutil.copytree(DIST / "openconex", staging / "openconex-cli")
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


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in PLATFORMS:
        print(f"usage: {sys.argv[0]} {'|'.join(PLATFORMS)}", file=sys.stderr)
        return 2
    platform = sys.argv[1]
    DIST.mkdir(exist_ok=True)
    pyinstaller("OpenConex", "packaging/gui_entry.py", windowed=True)
    pyinstaller("openconex", "packaging/cli_entry.py", windowed=False)
    smoke(platform)
    package(platform)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
