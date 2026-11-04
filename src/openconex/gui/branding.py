# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Application icon and splash screen loaded from packaged branding assets."""

from __future__ import annotations

import os
from functools import lru_cache
from importlib import resources

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QSplashScreen

from openconex import __version__

BRANDING_PACKAGE = "openconex.data"


def _branding_path(name: str):
    return resources.files(BRANDING_PACKAGE).joinpath("branding", name)


@lru_cache(maxsize=1)
def app_icon() -> QIcon:
    """Return the multi-size application icon, or an empty QIcon if unavailable."""
    icon = QIcon()
    for size in (16, 32, 64, 128, 256, 512):
        try:
            with resources.as_file(_branding_path(f"icon-{size}.png")) as path:
                icon.addFile(str(path))
        except (FileNotFoundError, OSError):
            continue
    return icon


def splash_pixmap() -> QPixmap:
    """Load the splash art and draw the live version number on it."""
    with resources.as_file(_branding_path("splash.png")) as path:
        pixmap = QPixmap(str(path))
    if pixmap.isNull():
        return pixmap

    painter = QPainter(pixmap)
    try:
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setPen(QColor("#8FB4C9"))
        font = QFont("Consolas")
        font.setPixelSize(12)
        painter.setFont(font)
        painter.drawText(
            QRect(320, 592, 134, 22),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            f"v{__version__}",
        )
    finally:
        painter.end()
    return pixmap


def show_splash(app: QApplication) -> QSplashScreen | None:
    """Show the splash screen unless running headless or explicitly disabled."""
    if os.environ.get("OPENCONEX_NO_SPLASH"):
        return None
    if os.environ.get("QT_QPA_PLATFORM", "").lower() in {"offscreen", "minimal"}:
        return None

    pixmap = splash_pixmap()
    if pixmap.isNull():
        return None

    screen = app.primaryScreen()
    if screen is not None:
        available = screen.availableGeometry()
        max_width = max(1, int(available.width() * 0.86))
        max_height = max(1, int(available.height() * 0.86))
        if pixmap.width() > max_width or pixmap.height() > max_height:
            pixmap = pixmap.scaled(
                max_width,
                max_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

    splash = QSplashScreen(pixmap, Qt.WindowType.WindowStaysOnTopHint)
    splash.show()
    app.processEvents()
    return splash
