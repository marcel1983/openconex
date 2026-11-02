# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Batch calculation and report tests."""

import os
import shutil
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from openpyxl import load_workbook
from PySide6.QtWidgets import QApplication

from openconex.gui.batch import BatchDialog, calculate_batch, export_summary

from .conftest import EXAMPLE


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    return app


def _copies(folder: Path, count: int) -> list[Path]:
    folder.mkdir(parents=True)
    paths = []
    for index in range(count):
        path = folder / f"project-{index + 1}.ocnx"
        shutil.copy(EXAMPLE, path)
        paths.append(path)
    return paths


def test_batch_calculates_and_continues_after_error(tmp_path):
    paths = _copies(tmp_path / "projects", 3)
    broken = tmp_path / "projects" / "broken.ocnx"
    broken.write_text("{", encoding="utf-8")
    output = tmp_path / "output"
    results = calculate_batch(sorted((*paths, broken)), output, ("html",))
    assert len(results) == 4
    assert sum(result.status != "ERROR" for result in results) == 3
    assert any(result.status == "ERROR" for result in results)
    assert len(list(output.glob("*.html"))) == 3
    assert all(result.outputs for result in results if result.status != "ERROR")


def test_batch_twenty_projects(tmp_path):
    paths = _copies(tmp_path / "many", 20)
    results = calculate_batch(paths, None)
    assert len(results) == 20
    assert all(result.status != "ERROR" for result in results)


def test_batch_can_cancel_after_one_project(tmp_path):
    paths = _copies(tmp_path / "cancel", 3)
    seen = []

    def progress(done, total, result):
        seen.append(done)

    results = calculate_batch(paths, None, progress=progress,
                              should_cancel=lambda: len(seen) >= 1)
    assert len(results) == 1
    assert seen == [1]


def test_export_summary_to_excel(tmp_path):
    results = calculate_batch([EXAMPLE], None)
    path = tmp_path / "summary.xlsx"
    export_summary(results, path)
    sheet = load_workbook(path).active
    assert [cell.value for cell in sheet[1]] == [
        "Proyecto", "Archivo", "Columna", "Estado", "Relación",
        "Verificación", "Combinación", "Error", "Salidas"]
    assert sheet.cell(row=2, column=4).value in ("OK", "NG")
    assert sheet.cell(row=2, column=3).value == "W12X96"


def test_batch_dialog_paths_and_formats(qapp, tmp_path):
    paths = _copies(tmp_path / "dialog", 2)
    dialog = BatchDialog()
    dialog._folder.setText(str(paths[0].parent))
    dialog._output.setText(str(tmp_path / "out"))
    assert dialog.paths() == paths
    assert "html" in dialog.formats()
    assert "dxf" in dialog.formats()
    dialog.close()
