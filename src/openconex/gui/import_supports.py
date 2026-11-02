# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Dialog to import supports from a SAP2000 / ETABS Excel export."""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
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

__all__ = ["ImportSupportsDialog"]


class ImportSupportsDialog(QDialog):
    """Choose the CSI export, the output folder and the batch options."""

    def __init__(self, parent: QWidget | None, template_name: str) -> None:
        super().__init__(parent)
        self.setWindowTitle("Importar SAP2000 / ETABS")
        self._build_ui(template_name)

    def _build_ui(self, template_name: str) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        file_row = QWidget()
        file_layout = QHBoxLayout(file_row)
        file_layout.setContentsMargins(0, 0, 0, 0)
        self._file = QLineEdit()
        self._file.setPlaceholderText("Exportación de tablas a Excel (.xlsx)")
        file_layout.addWidget(self._file, 1)
        browse = QPushButton("Examinar…")
        browse.clicked.connect(self._browse_file)
        file_layout.addWidget(browse)
        form.addRow("Archivo CSI", file_row)

        output_row = QWidget()
        output_layout = QHBoxLayout(output_row)
        output_layout.setContentsMargins(0, 0, 0, 0)
        self._output = QLineEdit()
        self._output.setPlaceholderText("Carpeta donde escribir los proyectos .ocnx")
        output_layout.addWidget(self._output, 1)
        folder = QPushButton("Carpeta…")
        folder.clicked.connect(self._browse_output)
        output_layout.addWidget(folder)
        form.addRow("Salida", output_row)

        template = QLabel(template_name or "(proyecto abierto)")
        template.setWordWrap(True)
        form.addRow("Plantilla", template)

        self._group = QComboBox()
        self._group.addItem("Un proyecto por apoyo", "joint")
        self._group.addItem("Un proyecto por sección de columna", "column")
        form.addRow("Agrupación", self._group)

        self._loads = QComboBox()
        self._loads.addItem("Casos de carga (OpenConex genera combinaciones)", "cases")
        self._loads.addItem("Combinaciones del programa (ya factorizadas)",
                            "combinations")
        form.addRow("Cargas", self._loads)

        self._include = QLineEdit()
        self._include.setPlaceholderText("opcional: expresión regular, por ejemplo ^CU")
        form.addRow("Incluir", self._include)

        self._envelopes = QCheckBox("Incluir envolventes Max/Min")
        self._envelopes.setEnabled(False)
        form.addRow("", self._envelopes)

        self._method = QComboBox()
        self._method.addItem("Según la plantilla", "")
        self._method.addItem("LRFD", "LRFD")
        self._method.addItem("ASD", "ASD")
        form.addRow("Método", self._method)

        note = QLabel("La plantilla es el proyecto abierto: aporta la placa, el concreto, "
                      "los anclajes y las opciones. Cada apoyo recibe su columna y sus "
                      "reacciones.")
        note.setWordWrap(True)
        form.addRow(note)
        layout.addLayout(form)

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

        self._loads.currentIndexChanged.connect(self._update_envelopes)
        self._update_envelopes()

    def _update_envelopes(self) -> None:
        self._envelopes.setEnabled(self._loads.currentData() == "combinations")
        if not self._envelopes.isEnabled():
            self._envelopes.setChecked(False)

    def _browse_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Exportación de SAP2000 / ETABS",
                                               "", "Excel (*.xlsx);;Todos (*)")
        if path:
            self._file.setText(path)

    def _browse_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Carpeta de salida")
        if path:
            self._output.setText(path)

    def accept(self) -> None:
        if not Path(self._file.text().strip()).is_file():
            QMessageBox.warning(self, "Archivo no válido",
                                "Seleccione una exportación .xlsx existente.")
            return
        if not self._output.text().strip():
            QMessageBox.warning(self, "Salida incompleta",
                                "Seleccione la carpeta donde escribir los proyectos.")
            return
        include = self._include.text().strip()
        if include:
            try:
                re.compile(include)
            except re.error as exc:
                QMessageBox.warning(self, "Expresión no válida", str(exc))
                return
        super().accept()

    @property
    def file(self) -> str:
        return self._file.text().strip()

    @property
    def output(self) -> str:
        return self._output.text().strip()

    @property
    def group(self) -> str:
        return self._group.currentData()

    @property
    def loads(self) -> str:
        return self._loads.currentData()

    @property
    def include(self) -> str:
        return self._include.text().strip()

    @property
    def envelopes(self) -> bool:
        return self._envelopes.isChecked()

    @property
    def method(self) -> str:
        return self._method.currentData()
