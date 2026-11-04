# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Branding assets used by the desktop application."""

import os
from importlib import resources

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from openconex.gui.branding import app_icon, splash_pixmap


def test_branding_assets_are_packaged():
    branding = resources.files("openconex.data").joinpath("branding")
    for name in ("splash.png", "icon.ico", "icon-16.png", "icon-32.png",
                 "icon-64.png", "icon-128.png", "icon-256.png", "icon-512.png",
                 "icon-1024.png"):
        assert branding.joinpath(name).is_file(), name


def test_icon_and_splash_load():
    app = QApplication.instance() or QApplication([])
    assert app is not None
    icon = app_icon()
    assert not icon.isNull()
    assert icon.availableSizes()
    splash = splash_pixmap()
    assert not splash.isNull()
    assert (splash.width(), splash.height()) == (1000, 700)
