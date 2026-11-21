# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
import pytest


@pytest.fixture(scope="session", autouse=True)
def _never_prompt_unsaved_changes():
    """Answer «Descartar» to the unsaved-changes prompt for the whole session.

    Session-scoped (and never restored) because the Qt teardown closes the
    remaining windows after every function-scoped patch has been undone;
    a real prompt there would wait forever. Tests that need another answer
    patch ``openconex.gui.session.ask_save_changes`` themselves.
    """
    try:
        from openconex.gui import session
    except ImportError:
        return
    session.ask_save_changes = lambda parent, name: "discard"


@pytest.fixture(autouse=True)
def _isolated_gui_settings(tmp_path):
    """Keep GUI preferences (recent files, units, geometry) in a temporary folder."""
    try:
        from PySide6.QtCore import QSettings
    except ImportError:
        return
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                      str(tmp_path / "settings"))
