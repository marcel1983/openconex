# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
import json

from openconex.cli import main

from .conftest import EXAMPLE


def test_baseplate_outputs(tmp_path, capsys):
    out = tmp_path / "result"
    code = main(["baseplate", str(EXAMPLE), "-o", str(out), "--html", "--docx", "--dxf",
                 "--lang", "en"])
    assert code == 0
    for ext in (".html", ".docx", ".dxf"):
        assert out.with_suffix(ext).exists()
    printed = capsys.readouterr().out
    assert "Concrete bearing under the plate" in printed


def test_failing_project_exit_code(tmp_path):
    data = json.loads(EXAMPLE.read_text())
    data["base_plate"]["tp"] = "1 in"
    path = tmp_path / "thin.ocnx"
    path.write_text(json.dumps(data))
    assert main(["baseplate", str(path), "-o", str(tmp_path / "thin")]) == 1


def test_hss_example_outputs(tmp_path):
    path = EXAMPLE.with_name("base_plate_hss_round.ocnx")
    out = tmp_path / "hss"
    assert main(["baseplate", str(path), "-o", str(out), "--html", "--dxf"]) == 0
    assert out.with_suffix(".html").exists()
    assert out.with_suffix(".dxf").exists()
