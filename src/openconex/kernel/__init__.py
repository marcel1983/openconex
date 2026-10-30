# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Design checks shared by every connection type (AISC 360-22 Chapter J, Manual Parts 7-9).

All inputs and results are in internal units (N, mm, MPa). Each check returns a
:class:`~openconex.core.checks.CheckResult` with its calculation trace.
"""
