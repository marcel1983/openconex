# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
from pathlib import Path

import pytest

from openconex.io.project import load_project

EXAMPLE = Path(__file__).parents[2] / "examples" / "base_plate_dg1_4_7_11.ocnx"


@pytest.fixture
def project():
    return load_project(EXAMPLE)


@pytest.fixture(scope="session", autouse=True)
def _qt_teardown():
    """Delete the GUI widgets before the Qt application is destroyed.

    Without this, a few PySide6 versions can abort at interpreter exit after
    several top-level test widgets have been created.
    """
    yield
    try:
        from PySide6.QtCore import QCoreApplication, QEvent, QThreadPool
        from PySide6.QtWidgets import QApplication
    except ImportError:
        return
    QThreadPool.globalInstance().waitForDone(2000)
    app = QCoreApplication.instance()
    if app is None:
        return
    for widget in QApplication.topLevelWidgets():
        widget.close()
        widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
