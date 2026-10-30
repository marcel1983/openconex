# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
from pathlib import Path

import pytest

from openconex.io.project import load_project

EXAMPLE = Path(__file__).parents[2] / "examples" / "base_plate_dg1_4_7_11.ocnx"


@pytest.fixture
def project():
    return load_project(EXAMPLE)
