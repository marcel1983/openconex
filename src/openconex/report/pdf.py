# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""PDF report printed from the HTML report with Qt WebEngine (optional extra ``pdf``).

The same Chromium engine renders the on-screen preview, so the PDF matches it
on every platform. Works without a display (offscreen platform).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from openconex.report.builder import Report
from openconex.report.html import render_html

__all__ = ["pdf_available", "write_pdf"]


def pdf_available() -> bool:
    try:
        from PySide6 import QtWebEngineCore  # noqa: F401
    except ImportError:
        return False
    return True


def _prepare_environment() -> None:
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY") \
            and not os.environ.get("WAYLAND_DISPLAY"):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    if hasattr(os, "geteuid") and os.geteuid() == 0:  # Chromium refuses its sandbox as root
        flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
        if "--no-sandbox" not in flags:
            os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (flags + " --no-sandbox").strip()


def write_pdf(report: Report, path: str | Path, timeout_ms: int = 60000) -> Path:
    """Render the report to an A4 PDF. Raises RuntimeError if Qt WebEngine is missing."""
    if not pdf_available():
        raise RuntimeError("PDF output needs Qt WebEngine: pip install 'openconex[pdf]'")
    _prepare_environment()
    from PySide6.QtCore import QCoreApplication, QEvent, QEventLoop, QMarginsF, QTimer, QUrl
    from PySide6.QtGui import QPageLayout, QPageSize
    from PySide6.QtWebEngineCore import QWebEnginePage
    from PySide6.QtWidgets import QApplication

    path = Path(path).resolve()
    app = QApplication.instance() or QApplication([])
    page = QWebEnginePage()
    loop = QEventLoop()
    state = {"ok": False}

    def done(ok: bool) -> None:
        state["ok"] = ok
        loop.quit()

    def run(start) -> None:
        QTimer.singleShot(timeout_ms, loop.quit)
        start()
        loop.exec()

    page.loadFinished.connect(done)
    run(lambda: page.setHtml(render_html(report), QUrl("file:///")))
    if not state["ok"]:
        raise RuntimeError("could not render the report")
    state["ok"] = False
    page.pdfPrintingFinished.connect(lambda _file, ok: done(ok))
    layout = QPageLayout(QPageSize(QPageSize.PageSizeId.A4), QPageLayout.Orientation.Portrait,
                         QMarginsF(15, 18, 15, 20), QPageLayout.Unit.Millimeter)
    run(lambda: page.printToPdf(str(path), layout))
    page.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
    if not state["ok"] or not path.exists():
        raise RuntimeError(f"could not write {path}")
    return path
