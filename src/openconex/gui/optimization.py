# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Dialog with the search trace of the base plate optimization."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from openconex.connections.base_plate.optimize import OptimizationResult, steel_weight
from openconex.gui.quantity import format_quantity, unit_label
from openconex.units import Kind, UnitSystem

__all__ = ["OptimizationDialog", "trace_rows"]

HEADERS = ("Disposición", "N", "B", "tp", "Anclaje", "Peso [kg]", "Ratio", "Gobierna")


def trace_rows(result: OptimizationResult, units: UnitSystem) -> list[list[str]]:
    """Table rows of the search trace, in the order they were explored."""
    rows = []
    for row in result.trace:
        rows.append([
            row.label,
            format_quantity(row.N, Kind.LENGTH, units),
            format_quantity(row.B, Kind.LENGTH, units),
            format_quantity(row.tp, Kind.THICKNESS, units),
            f"{2 * row.rods_per_side} × {format_quantity(row.rod_diameter, Kind.LENGTH, units)}",
            f"{row.weight:.1f}",
            f"{row.ratio:.3f}" if row.ok else "NG",
            row.governing,
        ])
    return rows


class OptimizationDialog(QDialog):
    """Shows the explored layouts and asks whether to apply the best one."""

    def __init__(self, result: OptimizationResult, units: UnitSystem,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Optimización global de la placa base")
        layout = QVBoxLayout(self)
        best = result.best
        summary = QLabel(
            f"Mejor solución: N = {format_quantity(best.N, Kind.LENGTH, units)}, "
            f"B = {format_quantity(best.B, Kind.LENGTH, units)}, "
            f"tp = {format_quantity(best.tp, Kind.THICKNESS, units)} "
            f"{unit_label(units, Kind.THICKNESS)}, {best.rods} anclajes de "
            f"{format_quantity(best.rod.diameter, Kind.LENGTH, units)} "
            f"{unit_label(units, Kind.LENGTH)}; peso {steel_weight(best):.1f} kg "
            f"(inicial {steel_weight(result.initial):.1f} kg). Todas las combinaciones "
            "cumplen. ¿Aplicar al proyecto?")
        summary.setWordWrap(True)
        layout.addWidget(summary)
        rows = trace_rows(result, units)
        table = QTableWidget(len(rows), len(HEADERS))
        table.setHorizontalHeaderLabels(list(HEADERS))
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        for r, values in enumerate(rows):
            for c, value in enumerate(values):
                table.setItem(r, c, QTableWidgetItem(value))
        table.resizeColumnsToContents()
        layout.addWidget(table, 1)
        self.table = table
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Apply
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.resize(820, 460)
