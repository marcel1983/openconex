# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Build the native installer for one platform from the portable bundle.

Usage: python packaging/build_installer.py windows-x64|macos-arm64|linux-x86_64

Run it after ``packaging/build_portable.py`` on the same machine: it reuses the
staging folder ``build/portable/OpenConex-<version>-<platform>`` and writes to
``dist/``:

- Windows: ``OpenConex-<version>-windows-x64.msi`` (WiX Toolset 5).
- macOS: ``OpenConex-<version>-macos-arm64.dmg`` (``hdiutil``).
- Linux: ``OpenConex-<version>-linux-x86_64.AppImage`` (``appimagetool``).

Signing is optional and driven by environment variables, so forks and pull
requests build unsigned installers. When the variables are present the bundle is
signed before the installer is built, the portable ZIP is rebuilt from the
signed files and the installer itself is signed (and notarized on macOS):

- Windows: ``WINDOWS_CERTIFICATE`` (base64 PFX), ``WINDOWS_CERTIFICATE_PASSWORD``
  and optionally ``WINDOWS_TIMESTAMP_URL``.
- macOS: ``MACOS_SIGN_IDENTITY`` (a "Developer ID Application" identity already
  in the keychain); notarization also needs ``APPLE_ID``, ``APPLE_TEAM_ID`` and
  ``APPLE_APP_PASSWORD``.
- Linux: ``LINUX_GPG_KEY`` (ASCII-armored private key) and optionally
  ``LINUX_GPG_PASSPHRASE``; writes a detached ``.AppImage.asc`` signature.

Each installer is installed (or mounted), run and removed again, so a release
never ships an installer that has not been exercised on the build machine.
"""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
BUILD = ROOT / "build"
WORK = BUILD / "installer"
PACKAGING = ROOT / "packaging"
BRANDING = ROOT / "src" / "openconex" / "data" / "branding"
PLATFORMS = ("windows-x64", "macos-arm64", "linux-x86_64")
GUI_NAME = "OpenConex"
CLI_FOLDER = "openconex-cli"
CLI_NAME = "openconex"
EXTENSIONS = {"windows-x64": ".msi", "macos-arm64": ".dmg",
              "linux-x86_64": ".AppImage"}
# Never change: Windows uses it to recognise older OpenConex installs and
# replace them (MajorUpgrade) instead of installing side by side.
UPGRADE_CODE = "648CB04F-F0E0-445D-AE1E-9121C43F4FCD"
SHORTCUT_GUID = "CCDD2C5C-CED1-4EC6-9A21-F0B80B8E78BC"
PATH_GUID = "6583AC48-1544-44A1-AFF3-F0CA45A974E0"
MANUFACTURER = "The OpenConex contributors"
HOMEPAGE = "https://github.com/marcel1983/openconex"
DEFAULT_TIMESTAMP_URL = "http://timestamp.digicert.com"
MACHO_MAGICS = {bytes.fromhex(magic) for magic in (
    "feedface", "feedfacf", "cefaedfe", "cffaedfe", "cafebabe", "bebafeca")}


def run(args: list[object], *, env: dict[str, str] | None = None,
        timeout: int = 1800, secret: bool = False) -> None:
    shown = [str(arg) for arg in args[:2]] + ["…"] if secret else [str(a) for a in args]
    print("+", " ".join(shown), flush=True)
    subprocess.run([str(arg) for arg in args], cwd=ROOT, env=env, check=True,
                   timeout=timeout)


def version() -> str:
    from openconex import __version__
    return __version__


def staging_dir(platform: str) -> Path:
    path = BUILD / "portable" / f"OpenConex-{version()}-{platform}"
    if not path.is_dir():
        raise RuntimeError(
            f"missing {path}; run packaging/build_portable.py {platform} first")
    return path


def installer_path(platform: str) -> Path:
    return DIST / f"OpenConex-{version()}-{platform}{EXTENSIONS[platform]}"


def numeric_version(text: str) -> str:
    """MSI ProductVersion: three numeric fields, pre-release suffix dropped."""
    match = re.match(r"(\d+)\.(\d+)\.(\d+)", text)
    if match is None:
        raise ValueError(f"cannot derive a numeric version from {text!r}")
    major, minor, patch = (int(part) for part in match.groups())
    if major > 255 or minor > 255 or patch > 65535:
        raise ValueError(f"version {text!r} is outside the MSI range")
    return f"{major}.{minor}.{patch}"


def write_checksums(platform: str, files: list[Path]) -> Path:
    lines = [f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n"
             for path in files]
    checksum = DIST / f"SHA256SUMS-{platform}.txt"
    checksum.write_text("".join(lines), encoding="utf-8")
    return checksum


def _portable_module():
    spec = importlib.util.spec_from_file_location(
        "openconex_build_portable", PACKAGING / "build_portable.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rebuild_portable_zip(platform: str, staging: Path) -> Path:
    """Re-zip the staging folder after signing so the ZIP carries signed files."""
    archive = DIST / f"{staging.name}.zip"
    archive.unlink(missing_ok=True)
    if platform.startswith("macos"):
        run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent",
             staging, archive])
    else:
        _portable_module().zip_tree(staging, archive)
    return archive


# --------------------------------------------------------------------------- Windows

def wix_source(staging: Path, icon: Path, product_version: str) -> str:
    """WiX 5 source: everything under Program Files, Start menu entry, CLI on PATH."""
    return f"""<?xml version="1.0" encoding="utf-8"?>
<Wix xmlns="http://wixtoolset.org/schemas/v4/wxs">
  <Package Name="OpenConex" Manufacturer="{MANUFACTURER}"
           Version="{product_version}" UpgradeCode="{UPGRADE_CODE}"
           Scope="perMachine" Compressed="yes">
    <MajorUpgrade DowngradeErrorMessage="A newer version of OpenConex is already installed." />
    <MediaTemplate EmbedCab="yes" />
    <Icon Id="OpenConexIcon" SourceFile="{icon}" />
    <Property Id="ARPPRODUCTICON" Value="OpenConexIcon" />
    <Property Id="ARPURLINFOABOUT" Value="{HOMEPAGE}" />
    <Property Id="ARPHELPLINK" Value="{HOMEPAGE}/issues" />
    <StandardDirectory Id="ProgramFiles64Folder">
      <Directory Id="INSTALLFOLDER" Name="OpenConex">
        <Files Include="{staging}\\**" />
        <Component Id="CliOnPath" Guid="{PATH_GUID}">
          <Environment Id="OpenConexPath" Name="PATH" Value="[INSTALLFOLDER]{CLI_FOLDER}"
                       Action="set" Part="last" System="yes" Permanent="no" />
          <RegistryValue Root="HKLM" Key="Software\\OpenConex" Name="CliOnPath"
                         Type="integer" Value="1" KeyPath="yes" />
        </Component>
      </Directory>
    </StandardDirectory>
    <StandardDirectory Id="ProgramMenuFolder">
      <Component Id="StartMenuShortcut" Guid="{SHORTCUT_GUID}">
        <Shortcut Id="OpenConexShortcut" Name="OpenConex"
                  Description="Steel connection design to AISC 360"
                  Target="[INSTALLFOLDER]{GUI_NAME}\\{GUI_NAME}.exe"
                  WorkingDirectory="INSTALLFOLDER" Icon="OpenConexIcon" />
        <RegistryValue Root="HKCU" Key="Software\\OpenConex" Name="StartMenuShortcut"
                       Type="integer" Value="1" KeyPath="yes" />
      </Component>
    </StandardDirectory>
  </Package>
</Wix>
"""


def find_signtool() -> Path:
    found = shutil.which("signtool")
    if found:
        return Path(found)
    kits = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
    candidates = sorted((kits / "Windows Kits" / "10" / "bin").glob("*/x64/signtool.exe"))
    if not candidates:
        raise RuntimeError("signtool.exe not found (install the Windows SDK)")
    return candidates[-1]


def windows_sign(files: list[Path]) -> bool:
    certificate = os.environ.get("WINDOWS_CERTIFICATE", "")
    if not certificate or not files:
        return False
    password = os.environ.get("WINDOWS_CERTIFICATE_PASSWORD", "")
    timestamp = os.environ.get("WINDOWS_TIMESTAMP_URL", DEFAULT_TIMESTAMP_URL)
    signtool = find_signtool()
    with tempfile.TemporaryDirectory() as folder:
        pfx = Path(folder) / "certificate.pfx"
        pfx.write_bytes(base64.b64decode(certificate))
        run([signtool, "sign", "/f", pfx, "/p", password, "/fd", "SHA256",
             "/tr", timestamp, "/td", "SHA256", "/d", "OpenConex", "/du", HOMEPAGE,
             *files], secret=True)
    run([signtool, "verify", "/pa", *files])
    return True


def build_windows(platform: str, staging: Path) -> list[Path]:
    signed = windows_sign(sorted(staging.rglob("*.exe")))
    outputs: list[Path] = []
    if signed:
        outputs.append(rebuild_portable_zip(platform, staging))
    else:
        outputs.append(DIST / f"{staging.name}.zip")
    WORK.mkdir(parents=True, exist_ok=True)
    source = WORK / "openconex.wxs"
    source.write_text(wix_source(staging, BRANDING / "icon.ico",
                                 numeric_version(version())), encoding="utf-8")
    msi = installer_path(platform)
    msi.unlink(missing_ok=True)
    run(["wix", "build", "-arch", "x64", "-o", msi, source])
    windows_sign([msi])
    verify_windows(msi)
    return [*outputs, msi]


def verify_windows(msi: Path) -> None:
    """Install silently, run the installed CLI, uninstall and check nothing is left."""
    program_files = Path(os.environ.get("ProgramW6432", r"C:\Program Files"))
    target = program_files / "OpenConex"
    log = WORK / "install.log"
    run(["msiexec", "/i", msi, "/qn", "/norestart", "/l*v", log], timeout=1800)
    try:
        cli = target / CLI_FOLDER / f"{CLI_NAME}.exe"
        gui = target / GUI_NAME / f"{GUI_NAME}.exe"
        if not cli.is_file() or not gui.is_file():
            raise RuntimeError(f"installer did not create {cli} and {gui}")
        env = os.environ.copy()
        env["QT_QPA_PLATFORM"] = "offscreen"
        run([cli, "--version"], env=env, timeout=120)
        run([gui, "--check-assets"], env=env, timeout=120)
    finally:
        run(["msiexec", "/x", msi, "/qn", "/norestart", "/l*v", WORK / "uninstall.log"],
            timeout=1800)
    if target.exists():
        left = [str(path) for path in target.rglob("*")][:20]
        raise RuntimeError(f"uninstall left files behind in {target}: {left}")
    print("MSI install/uninstall OK", flush=True)


# --------------------------------------------------------------------------- macOS

def is_macho(path: Path) -> bool:
    if path.is_symlink() or not path.is_file():
        return False
    with path.open("rb") as handle:
        return handle.read(4) in MACHO_MAGICS


def macos_sign(staging: Path) -> bool:
    identity = os.environ.get("MACOS_SIGN_IDENTITY", "")
    if not identity:
        return False
    entitlements = PACKAGING / "macos" / "entitlements.plist"
    base = ["codesign", "--force", "--timestamp", "--options", "runtime",
            "--entitlements", entitlements, "--sign", identity]
    # Inside-out: loose Mach-O files first, then framework and app bundles,
    # deepest first, so each outer signature seals already-signed contents.
    binaries = sorted((path for path in staging.rglob("*") if is_macho(path)),
                      key=lambda path: len(path.parts), reverse=True)
    for path in binaries:
        run([*base, path])
    bundles = sorted((path for path in staging.rglob("*")
                      if path.is_dir() and not path.is_symlink()
                      and path.suffix in {".framework", ".app"}),
                     key=lambda path: len(path.parts), reverse=True)
    for path in bundles:
        run([*base, path])
    run(["codesign", "--verify", "--deep", "--strict", "--verbose=2",
         staging / f"{GUI_NAME}.app"])
    return True


def macos_notarize(dmg: Path) -> bool:
    apple_id = os.environ.get("APPLE_ID", "")
    team = os.environ.get("APPLE_TEAM_ID", "")
    password = os.environ.get("APPLE_APP_PASSWORD", "")
    if not (apple_id and team and password):
        return False
    run(["xcrun", "notarytool", "submit", dmg, "--apple-id", apple_id,
         "--team-id", team, "--password", password, "--wait"],
        timeout=3600, secret=True)
    run(["xcrun", "stapler", "staple", dmg])
    run(["xcrun", "stapler", "validate", dmg])
    return True


def build_macos(platform: str, staging: Path) -> list[Path]:
    signed = macos_sign(staging)
    portable = (rebuild_portable_zip(platform, staging) if signed
                else DIST / f"{staging.name}.zip")
    layout = WORK / "dmg"
    shutil.rmtree(layout, ignore_errors=True)
    layout.mkdir(parents=True)
    for name in (f"{GUI_NAME}.app", CLI_FOLDER, "licenses"):
        run(["ditto", staging / name, layout / name])
    for name in ("LICENSE", "LEEME.txt", "NOTICE-AISC.md"):
        if (staging / name).exists():
            shutil.copy2(staging / name, layout / name)
    (layout / "Applications").symlink_to("/Applications")
    dmg = installer_path(platform)
    dmg.unlink(missing_ok=True)
    run(["hdiutil", "create", "-volname", f"OpenConex {version()}",
         "-srcfolder", layout, "-fs", "HFS+", "-format", "UDZO", "-ov", dmg])
    if signed:
        run(["codesign", "--force", "--timestamp", "--sign",
             os.environ["MACOS_SIGN_IDENTITY"], dmg])
        if macos_notarize(dmg):
            run(["spctl", "--assess", "--type", "open",
                 "--context", "context:primary-signature", "--verbose=2", dmg])
    verify_macos(dmg)
    return [portable, dmg]


def verify_macos(dmg: Path) -> None:
    mount = WORK / "mount"
    shutil.rmtree(mount, ignore_errors=True)
    mount.mkdir(parents=True)
    run(["hdiutil", "attach", dmg, "-nobrowse", "-readonly", "-mountpoint", mount])
    try:
        gui = mount / f"{GUI_NAME}.app" / "Contents" / "MacOS" / GUI_NAME
        cli = mount / CLI_FOLDER / CLI_NAME
        if not (mount / "Applications").is_symlink():
            raise RuntimeError("the disk image has no Applications link")
        env = os.environ.copy()
        env["QT_QPA_PLATFORM"] = "offscreen"
        run([gui, "--version"], env=env, timeout=120)
        run([gui, "--check-assets"], env=env, timeout=120)
        run([cli, "--version"], env=env, timeout=120)
    finally:
        run(["hdiutil", "detach", mount])
    print("DMG mount/run OK", flush=True)


# --------------------------------------------------------------------------- Linux

APPRUN = f"""#!/bin/sh
# OpenConex AppImage entry point: GUI by default, CLI with --cli or when the
# AppImage is called through a link named "openconex".
HERE="$(dirname "$(readlink -f "$0")")"
APP="$HERE/usr/lib/openconex"
if [ "$1" = "--cli" ]; then
  shift
  exec "$APP/{CLI_FOLDER}/{CLI_NAME}" "$@"
fi
case "$(basename "${{ARGV0:-$0}}")" in
  {CLI_NAME}|{CLI_NAME}-cli) exec "$APP/{CLI_FOLDER}/{CLI_NAME}" "$@" ;;
esac
exec "$APP/{GUI_NAME}/{GUI_NAME}" "$@"
"""


def desktop_entry() -> str:
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=OpenConex\n"
        "GenericName=Steel connection design\n"
        "GenericName[es]=Diseño de conexiones de acero\n"
        "Comment=Steel connection design to AISC 360\n"
        "Comment[es]=Diseño de conexiones de acero según AISC 360\n"
        f"Exec={GUI_NAME} %f\n"
        "Icon=openconex\n"
        "Terminal=false\n"
        "Categories=Science;Engineering;\n"
        "Keywords=steel;AISC;connection;base plate;acero;conexión;\n"
    )


def build_appdir(staging: Path, appdir: Path) -> Path:
    shutil.rmtree(appdir, ignore_errors=True)
    target = appdir / "usr" / "lib" / "openconex"
    target.parent.mkdir(parents=True)
    # symlinks=True keeps the relative links build_portable uses to share the
    # Qt/OCP libraries between the GUI and CLI folders; squashfs stores them.
    shutil.copytree(staging, target, symlinks=True)
    apprun = appdir / "AppRun"
    apprun.write_text(APPRUN, encoding="utf-8")
    apprun.chmod(0o755)
    (appdir / "openconex.desktop").write_text(desktop_entry(), encoding="utf-8")
    shutil.copy2(BRANDING / "icon-256.png", appdir / "openconex.png")
    icons = appdir / "usr" / "share" / "icons" / "hicolor" / "256x256" / "apps"
    icons.mkdir(parents=True)
    shutil.copy2(BRANDING / "icon-256.png", icons / "openconex.png")
    (appdir / ".DirIcon").symlink_to("openconex.png")
    return appdir


def linux_sign(path: Path) -> Path | None:
    key = os.environ.get("LINUX_GPG_KEY", "")
    if not key:
        return None
    passphrase = os.environ.get("LINUX_GPG_PASSPHRASE", "")
    signature = path.with_name(path.name + ".asc")
    signature.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory() as home:
        env = os.environ.copy()
        env["GNUPGHOME"] = home
        subprocess.run(["gpg", "--batch", "--import"], input=key.encode(),
                       env=env, check=True)
        command = ["gpg", "--batch", "--yes", "--pinentry-mode", "loopback",
                   "--passphrase-fd", "0", "--armor", "--detach-sign",
                   "--output", str(signature), str(path)]
        print("+ gpg --detach-sign", path.name, flush=True)
        subprocess.run(command, input=passphrase.encode(), env=env, check=True)
        subprocess.run(["gpg", "--batch", "--verify", str(signature), str(path)],
                       env=env, check=True)
    return signature


def build_linux(platform: str, staging: Path) -> list[Path]:
    appdir = build_appdir(staging, WORK / "OpenConex.AppDir")
    appimage = installer_path(platform)
    appimage.unlink(missing_ok=True)
    tool = os.environ.get("APPIMAGETOOL", "appimagetool")
    env = os.environ.copy()
    env["ARCH"] = "x86_64"
    env["APPIMAGE_EXTRACT_AND_RUN"] = "1"  # CI runners have no FUSE
    run([tool, "--no-appstream", appdir, appimage], env=env)
    appimage.chmod(0o755)
    verify_linux(appimage)
    outputs = [DIST / f"{staging.name}.zip", appimage]
    signature = linux_sign(appimage)
    if signature is not None:
        outputs.append(signature)
    return outputs


def verify_linux(appimage: Path) -> None:
    env = os.environ.copy()
    env["APPIMAGE_EXTRACT_AND_RUN"] = "1"
    env["QT_QPA_PLATFORM"] = "offscreen"
    run([appimage, "--version"], env=env, timeout=300)
    run([appimage, "--check-assets"], env=env, timeout=300)
    run([appimage, "--cli", "--version"], env=env, timeout=300)
    out = WORK / "smoke"
    shutil.rmtree(out, ignore_errors=True)
    run([appimage, "--cli", "baseplate", "examples/base_plate_dg1_4_7_11.ocnx",
         "--pdf", "--step", "-o", out / "base"], env=env, timeout=900)
    print("AppImage run OK", flush=True)


# --------------------------------------------------------------------------- main

BUILDERS = {"windows-x64": build_windows, "macos-arm64": build_macos,
            "linux-x86_64": build_linux}


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in PLATFORMS:
        print(f"usage: {sys.argv[0]} {'|'.join(PLATFORMS)}", file=sys.stderr)
        return 2
    platform = sys.argv[1]
    staging = staging_dir(platform)
    outputs = BUILDERS[platform](platform, staging)
    checksum = write_checksums(platform, outputs)
    for path in outputs:
        print(f"output: {path} ({path.stat().st_size / 1_048_576:.1f} MiB)", flush=True)
    print(f"checksums: {checksum}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
