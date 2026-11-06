# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Batch calculation and report generation for base plate projects."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

from openpyxl import Workbook
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from openconex.gui.exporting import write_3d, write_dxf
from openconex.help import help_text
from openconex.io.project import Project, load_project
from openconex.report.builder import Report, build_report
from openconex.report.docx import write_docx
from openconex.report.html import write_html
from openconex.report.pdf import write_pdf

__all__ = [
    "BatchDialog",
    "BatchResult",
    "BatchSummaryDialog",
    "calculate_batch",
    "export_summary",
]

FORMATS = ("html", "docx", "pdf", "dxf", "step", "stl")


@dataclass
class BatchResult:
    path: Path
    name: str
    status: str
    column: str = ""
    ratio: float | None = None
    check: str = ""
    combo: str = ""
    error: str = ""
    outputs: list[Path] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status == "OK"


def _safe_stem(stem: str, used: set[str]) -> str:
    base = re.sub(r"[^A-Za-z0-9_.-]", "_", stem) or "proyecto"
    candidate = base
    number = 2
    while candidate.casefold() in used:
        candidate = f"{base}-{number}"
        number += 1
    used.add(candidate.casefold())
    return candidate


def _write_format(project: Project, report: Report, kind: str, target: Path) -> None:
    if kind == "html":
        write_html(report, target)
    elif kind == "docx":
        write_docx(report, target)
    elif kind == "pdf":
        write_pdf(report, target)
    elif kind == "dxf":
        write_dxf(project, target)
    elif kind in ("step", "stl"):
        write_3d(project, target, kind)
    else:
        raise ValueError(f"unknown output format: {kind}")


def _summary(report: Report) -> tuple[str, str, float | None]:
    if not report.checks:
        return "", "", None
    governing = max(report.checks, key=lambda check: check.ratio)
    return governing.title, governing.combo, governing.ratio


def calculate_batch(paths: Iterable[str | Path], output_dir: str | Path | None,
                    formats: Iterable[str] = (), progress: Callable[[int, int, BatchResult],
                                                                      None] | None = None,
                    should_cancel: Callable[[], bool] | None = None
                    ) -> list[BatchResult]:
    """Calculate every project and optionally write its reports.

    One broken project does not stop the batch. ``progress(done, total, result)``
    is called after each project and ``should_cancel`` is checked before the next
    one, so a cancelled batch finishes the current project cleanly.
    """
    formats = tuple(formats)
    unknown = [kind for kind in formats if kind not in FORMATS]
    if unknown:
        raise ValueError(f"unknown output formats: {unknown}")
    files = [Path(path) for path in paths]
    out = None if output_dir is None else Path(output_dir)
    if out is not None:
        out.mkdir(parents=True, exist_ok=True)
    used: set[str] = set()
    results: list[BatchResult] = []
    total = len(files)
    for index, path in enumerate(files, start=1):
        if should_cancel is not None and should_cancel():
            break
        result = _calculate_one(path, out, formats, used)
        results.append(result)
        if progress is not None:
            progress(index, total, result)
    return results


def _calculate_one(path: Path, out: Path | None, formats: tuple[str, ...],
                   used: set[str]) -> BatchResult:
    try:
        project = load_project(path)
        report = build_report(project)
    except Exception as exc:
        return BatchResult(path=path, name=path.stem, status="ERROR", error=str(exc))
    check, combo, ratio = _summary(report)
    if project.shear_connection is not None:
        beam = project.shear_connection.beam
        column_text = beam if isinstance(beam, str) else beam.label()
    else:
        column = project.base_plate.column
        column_text = column if isinstance(column, str) else column.label()
    result = BatchResult(path=path, name=project.info.name or path.stem,
                         status="OK" if report.ok else "NG", column=column_text,
                         ratio=ratio, check=check, combo=combo)
    if out is None:
        return result
    stem = _safe_stem(path.stem, used)
    for kind in formats:
        target = out / f"{stem}.{kind}"
        try:
            _write_format(project, report, kind, target)
        except Exception as exc:
            result.status = "ERROR"
            result.error = f"Error al escribir {kind}: {exc}"
            return result
        result.outputs.append(target)
    return result


def export_summary(results: Iterable[BatchResult], path: str | Path) -> Path:
    """Write the batch summary as an Excel workbook."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Resumen"
    headers = ["Proyecto", "Archivo", "Columna", "Estado", "Relación",
               "Verificación", "Combinación", "Error", "Salidas"]
    sheet.append(headers)
    for result in results:
        sheet.append([
            result.name,
            str(result.path),
            result.column,
            result.status,
            result.ratio,
            result.check,
            result.combo,
            result.error,
            ", ".join(str(output) for output in result.outputs),
        ])
    for row in range(2, sheet.max_row + 1):
        cell = sheet.cell(row=row, column=5)
        if isinstance(cell.value, (int, float)):
            cell.number_format = "0.000"
    sheet.freeze_panes = "A2"
    widths = (32, 44, 18, 10, 10, 32, 24, 44, 44)
    for index, width in enumerate(widths, start=1):
        sheet.column_dimensions[sheet.cell(row=1, column=index).column_letter].width = width
    target = Path(path)
    workbook.save(target)
    return target


class BatchDialog(QDialog):
    """Choose the folder, output formats and destination of a batch run."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Calcular lote de proyectos")
        self.resize(560, 360)
        layout = QVBoxLayout(self)
        form = QFormLayout()

        def tip(widget: QWidget, key: str) -> None:
            widget.setToolTip(help_text(key))
            widget.setStatusTip(help_text(key))

        folder_row = QWidget()
        folder_layout = QHBoxLayout(folder_row)
        folder_layout.setContentsMargins(0, 0, 0, 0)
        self._folder = QLineEdit()
        self._folder.setPlaceholderText("Carpeta con archivos .ocnx")
        tip(self._folder, "dialog.batch.folder")
        folder_layout.addWidget(self._folder, 1)
        browse = QPushButton("Carpeta…")
        browse.clicked.connect(self._browse_folder)
        tip(browse, "dialog.batch.folder")
        folder_layout.addWidget(browse)
        form.addRow("Proyectos", folder_row)

        output_row = QWidget()
        output_layout = QHBoxLayout(output_row)
        output_layout.setContentsMargins(0, 0, 0, 0)
        self._output = QLineEdit()
        self._output.setPlaceholderText("Si se deja vacío, se usa la carpeta de entrada")
        tip(self._output, "dialog.batch.output")
        output_layout.addWidget(self._output, 1)
        output_browse = QPushButton("Carpeta…")
        output_browse.clicked.connect(self._browse_output)
        tip(output_browse, "dialog.batch.output")
        output_layout.addWidget(output_browse)
        form.addRow("Salida", output_row)

        self._recursive = QCheckBox("Incluir subcarpetas")
        form.addRow("", self._recursive)
        tip(self._recursive, "dialog.batch.recursive")
        layout.addLayout(form)

        format_group = QWidget()
        format_layout = QVBoxLayout(format_group)
        format_layout.setContentsMargins(0, 0, 0, 0)
        format_layout.addWidget(QLabel("Salidas (además del resumen en pantalla)"))
        checks = QHBoxLayout()
        self._formats: dict[str, QCheckBox] = {}
        for key, label, checked in (
                ("html", "HTML", True), ("docx", "Word", False),
                ("pdf", "PDF", False), ("dxf", "DXF", True),
                ("step", "STEP", False), ("stl", "STL", False)):
            box = QCheckBox(label)
            box.setChecked(checked)
            self._formats[key] = box
            tip(box, "dialog.batch.formats")
            checks.addWidget(box)
        checks.addStretch(1)
        format_layout.addLayout(checks)
        note = QLabel("Cada proyecto conserva sus propios datos; el formulario abierto no "
                      "se modifica. Si se cancela, el proyecto en curso termina y no se "
                      "empieza el siguiente.")
        note.setWordWrap(True)
        format_layout.addWidget(note)
        layout.addWidget(format_group)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancelar")
        cancel.clicked.connect(self.reject)
        accept = QPushButton("Calcular")
        accept.setDefault(True)
        accept.clicked.connect(self.accept)
        tip(cancel, "dialog.batch.accept")
        tip(accept, "dialog.batch.accept")
        buttons.addWidget(cancel)
        buttons.addWidget(accept)
        layout.addLayout(buttons)

    def _browse_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Carpeta de proyectos")
        if path:
            self._folder.setText(path)

    def _browse_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Carpeta de salida")
        if path:
            self._output.setText(path)

    def accept(self) -> None:
        if not Path(self._folder.text().strip()).is_dir():
            QMessageBox.warning(self, "Carpeta no válida",
                                "Seleccione la carpeta con los proyectos .ocnx.")
            return
        if not self.paths():
            QMessageBox.warning(self, "Sin proyectos",
                                "La carpeta seleccionada no contiene archivos .ocnx.")
            return
        super().accept()

    def paths(self) -> list[Path]:
        folder = Path(self._folder.text().strip())
        if not folder.is_dir():
            return []
        pattern = "**/*.ocnx" if self._recursive.isChecked() else "*.ocnx"
        return sorted(folder.glob(pattern))

    @property
    def output(self) -> str:
        text = self._output.text().strip()
        return text or self._folder.text().strip()

    def formats(self) -> tuple[str, ...]:
        return tuple(key for key, box in self._formats.items() if box.isChecked())


class BatchSummaryDialog(QDialog):
    """Show the per-project result of a batch run."""

    def __init__(self, parent: QWidget | None, results: list[BatchResult]) -> None:
        super().__init__(parent)
        self._results = results
        self.setWindowTitle("Resultado del lote")
        self.resize(900, 420)
        layout = QVBoxLayout(self)
        ok = sum(result.ok for result in results)
        ng = sum(result.status == "NG" for result in results)
        errors = sum(result.status == "ERROR" for result in results)
        summary = QLabel(f"{len(results)} proyectos: {ok} OK, {ng} NG, {errors} con error.")
        layout.addWidget(summary)

        table = QTableWidget(0, 6)
        table.setHorizontalHeaderLabels(
            ["Proyecto", "Estado", "Relación", "Verificación", "Combinación", "Error"])
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)
        for result in results:
            row = table.rowCount()
            table.insertRow(row)
            values = (result.name, result.status,
                      "" if result.ratio is None else f"{result.ratio:.3f}",
                      result.check, result.combo, result.error)
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if result.status == "ERROR":
                    item.setForeground(QColor("#b00020"))
                elif result.status == "NG":
                    item.setForeground(QColor("#9a6700"))
                table.setItem(row, col, item)
        table.resizeColumnsToContents()
        layout.addWidget(table, 1)

        buttons = QHBoxLayout()
        export = QPushButton("Exportar Excel…")
        export.clicked.connect(self._export)
        buttons.addWidget(export)
        buttons.addStretch(1)
        close = QPushButton("Cerrar")
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        layout.addLayout(buttons)

    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Guardar resumen del lote",
                                               "resumen-lote.xlsx", "Excel (*.xlsx)")
        if not path:
            return
        target = Path(path)
        if target.suffix.lower() != ".xlsx":
            target = target.with_suffix(".xlsx")
        try:
            export_summary(self._results, target)
        except Exception as exc:
            QMessageBox.critical(self, "Error al exportar", str(exc))
            return
        QMessageBox.information(self, "Resumen exportado", f"Guardado en:\n{target}")
