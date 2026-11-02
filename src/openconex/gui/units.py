# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Per-quantity unit configuration dialog."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from openconex.units import CHOICES, Kind, UnitSystem

__all__ = ["UnitDialog"]

LABELS = {
    Kind.LENGTH: "Longitud",
    Kind.THICKNESS: "Espesor",
    Kind.FORCE: "Fuerza",
    Kind.MOMENT: "Momento",
    Kind.STRESS: "Tensión",
    Kind.AREA: "Área",
    Kind.FORCE_PER_LENGTH: "Fuerza por longitud",
    Kind.SECTION_MODULUS: "Módulo de sección",
    Kind.MOMENT_OF_INERTIA: "Momento de inercia",
    Kind.DIMENSIONLESS: "Adimensional",
}


class UnitDialog(QDialog):
    """Choose the display unit of every physical quantity."""

    def __init__(self, parent: QWidget | None, system: UnitSystem) -> None:
        super().__init__(parent)
        self._initial = system
        self._combos: dict[Kind, QComboBox] = {}
        self.setWindowTitle("Unidades por magnitud")
        self.resize(420, 420)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()
        for kind in LABELS:
            combo = QComboBox()
            choices = list(CHOICES[kind])
            current = self._initial.unit(kind)
            if current not in choices:
                choices.append(current)
            combo.addItems(choices)
            combo.setCurrentText(current)
            self._combos[kind] = combo
            form.addRow(LABELS[kind], combo)
        layout.addLayout(form)
        note = QLabel("Al aceptar se convierten el formulario, los casos, las secciones "
                      "y los bloques del proyecto. El proyecto guardará un sistema "
                      "personalizado.")
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancelar")
        cancel.clicked.connect(self.reject)
        accept = QPushButton("Aplicar")
        accept.setDefault(True)
        accept.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(accept)
        layout.addLayout(buttons)

    def system(self) -> UnitSystem:
        data = self._initial.model_dump()
        for kind, combo in self._combos.items():
            data[kind.value] = combo.currentText()
        data["name"] = "custom"
        return UnitSystem(**data)
