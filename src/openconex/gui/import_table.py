# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Dialog to import a generic Excel/CSV base plate table."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from openconex.units import PRESETS

__all__ = ["TableImportDialog"]

LABELS = {
    "SI_kN_m": "SI (kN, m)",
    "SI_N_mm": "SI (N, mm)",
    "MKS": "MKS (tf, m)",
    "US": "US (kip, in)",
}


class TableImportDialog(QDialog):
    """Choose a CSV/XLSX table, the output folder and the default units."""

    def __init__(self, parent: QWidget | None, default_units: str = "US") -> None:
        super().__init__(parent)
        self.setWindowTitle("Importar Excel / CSV")
        self.resize(560, 360)
        self._build(default_units if default_units in PRESETS else "US")

    def _build(self, default_units: str) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        file_row = QWidget()
        file_layout = QHBoxLayout(file_row)
        file_layout.setContentsMargins(0, 0, 0, 0)
        self._file = QLineEdit()
        self._file.setPlaceholderText("Tabla .xlsx o .csv")
        file_layout.addWidget(self._file, 1)
        browse = QPushButton("Examinar…")
        browse.clicked.connect(self._browse_file)
        file_layout.addWidget(browse)
        form.addRow("Archivo", file_row)

        output_row = QWidget()
        output_layout = QHBoxLayout(output_row)
        output_layout.setContentsMargins(0, 0, 0, 0)
        self._output = QLineEdit()
        self._output.setPlaceholderText("Carpeta de los proyectos .ocnx")
        output_layout.addWidget(self._output, 1)
        folder = QPushButton("Carpeta…")
        folder.clicked.connect(self._browse_output)
        output_layout.addWidget(folder)
        form.addRow("Salida", output_row)

        self._units = QComboBox()
        for key, label in LABELS.items():
            self._units.addItem(label, key)
        self._units.setCurrentIndex(self._units.findData(default_units))
        form.addRow("Unidades de números", self._units)
        layout.addLayout(form)

        note = QLabel(
            "Primera fila = cabecera. Columnas: support, case, type, column, P, V, M, "
            "V_weak, M_weak. support y case son obligatorios. Los números sin unidad "
            "usan el sistema elegido; las celdas pueden incluir su unidad (\"25 kN\").")
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch(1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancelar")
        cancel.clicked.connect(self.reject)
        accept = QPushButton("Importar")
        accept.setDefault(True)
        accept.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(accept)
        layout.addLayout(buttons)

    def _browse_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Tabla de importación", "",
            "Excel/CSV (*.xlsx *.csv);;Excel (*.xlsx);;CSV (*.csv);;Todos (*)")
        if path:
            self._file.setText(path)

    def _browse_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Carpeta de salida")
        if path:
            self._output.setText(path)

    def accept(self) -> None:
        if not Path(self._file.text().strip()).is_file():
            QMessageBox.warning(self, "Archivo no válido",
                                "Seleccione un archivo .xlsx o .csv existente.")
            return
        if not self._output.text().strip():
            QMessageBox.warning(self, "Salida incompleta",
                                "Seleccione la carpeta donde escribir los proyectos.")
            return
        super().accept()

    @property
    def file(self) -> str:
        return self._file.text().strip()

    @property
    def output(self) -> str:
        return self._output.text().strip()

    @property
    def units(self) -> str:
        return self._units.currentData()
