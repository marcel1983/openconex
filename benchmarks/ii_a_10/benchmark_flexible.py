# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Bolt-flexibility sensitivity of the II.A-10 connection.

The baseline benchmark uses rigid bolt patches. Here each patch is replaced
by a short elastic cylinder (a "pad") whose modulus controls the shear
stiffness of the bolt/support path. This is not a contact or pretension model;
it brackets how much the A/B split can move when the bolt and support are not
infinitely stiff.

Run with the optional benchmark dependencies::

    pip install gmsh meshio numpy
    python benchmarks/ii_a_10/benchmark_flexible.py --ccx /path/to/ccx
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
from pathlib import Path

import gmsh
import meshio
import numpy as np

TW = 0.455
T_PLATE = 0.375
H_PLATE = 8.5
W_A, W_B = 7.25, 6.75
LEG_A, LEG_B = 4.4375, 3.5625
L_BEAM = 5.0
H_BEAM = 12.0
SKEW = math.atan(6 / 12)
R = 80.0
PAD_RADIUS = 0.75
PAD_THICKNESS = 0.10
BOLT_ROWS = (3.75, -2.25)
BOLT_Y = (-3.0, 0.0, 3.0)
PAD_MODULI = (50.0, 150.0, 500.0, 1500.0)


def build_mesh(out: Path, hmax: float, hmin: float) -> Path:
    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    gmsh.model.add("ii_a_10_flex")
    occ = gmsh.model.occ
    beam = occ.addBox(0, -H_BEAM / 2, -TW / 2, L_BEAM, H_BEAM, TW)
    a_bolt = occ.addBox(0, -H_PLATE / 2, TW / 2, T_PLATE, H_PLATE, W_A)
    a_weld = occ.addBox(0, -H_PLATE / 2, TW / 2, LEG_A, H_PLATE, T_PLATE)
    b_bolt = occ.addBox(0, -H_PLATE / 2, -TW / 2 - W_B, T_PLATE, H_PLATE, W_B)
    b_weld = occ.addBox(0, -H_PLATE / 2, -TW / 2 - T_PLATE, LEG_B, H_PLATE, T_PLATE)
    for tag in (beam, a_weld, b_weld):
        occ.rotate([(3, tag)], 0, 0, 0, 0, 1, 0, SKEW)
    pads = []
    for z in BOLT_ROWS:
        for y in BOLT_Y:
            pads.append(occ.addCylinder(-PAD_THICKNESS, y, z, PAD_THICKNESS, 0, 0,
                                        PAD_RADIUS))
    occ.synchronize()
    solids = [(3, beam), (3, a_bolt), (3, a_weld), (3, b_bolt), (3, b_weld)]
    solids += [(3, tag) for tag in pads]
    occ.fragment(solids[:1], solids[1:])
    occ.synchronize()
    steel, pad_volumes = [], []
    for dim, tag in gmsh.model.getEntities(3):
        cx, _cy, _cz = occ.getCenterOfMass(dim, tag)
        volume = occ.getMass(3, tag)
        if cx < 0 and volume < 0.3:
            pad_volumes.append(tag)
        else:
            steel.append(tag)
    gmsh.model.addPhysicalGroup(3, steel, name="STEEL")
    gmsh.model.addPhysicalGroup(3, pad_volumes, name="PAD")
    gmsh.option.setNumber("Mesh.MeshSizeMax", hmax)
    gmsh.option.setNumber("Mesh.MeshSizeMin", hmin)
    gmsh.model.mesh.generate(3)
    path = out / "model_flex.msh"
    gmsh.write(str(path))
    gmsh.finalize()
    return path


def _pad_nodes(points: np.ndarray, z0: float) -> np.ndarray:
    ids = []
    for y0 in BOLT_Y:
        radial = (points[:, 1] - y0) ** 2 + (points[:, 2] - z0) ** 2
        ids.append(np.where((np.abs(points[:, 0] + PAD_THICKNESS) < 0.01)
                            & (radial <= PAD_RADIUS**2))[0])
    return np.unique(np.concatenate(ids))


def _load_nodes(points: np.ndarray) -> np.ndarray:
    ca, sa = math.cos(SKEW), math.sin(SKEW)
    lx = ca * points[:, 0] - sa * points[:, 2]
    lz = sa * points[:, 0] + ca * points[:, 2]
    return np.where((np.abs(np.abs(lz) - TW / 2) < 0.03) & (lx >= -0.01)
                    & (lx <= max(LEG_A, LEG_B))
                    & (np.abs(points[:, 1]) <= H_PLATE / 2 + 0.01))[0]


def write_input(mesh_path: Path, out: Path, e_pad: float) -> Path:
    mesh = meshio.read(mesh_path)
    points = mesh.points
    fix_a = _pad_nodes(points, BOLT_ROWS[0])
    fix_b = _pad_nodes(points, BOLT_ROWS[1])
    load = _load_nodes(points)
    block_names = [None] * len(mesh.cells)
    for name, indices in mesh.cell_sets.items():
        if name.startswith("gmsh"):
            continue
        for index, cells in enumerate(indices):
            if len(cells):
                block_names[index] = name
    lines = ["*Heading", f"II.A-10 flexible pads E={e_pad:g} ksi", "*NODE"]
    for i, point in enumerate(points, 1):
        lines.append(f"{i}, {point[0]:.9g}, {point[1]:.9g}, {point[2]:.9g}")
    element_id = 1
    for block, name in zip(mesh.cells, block_names, strict=True):
        if block.type != "tetra":
            continue
        lines.append(f"*ELEMENT, TYPE=C3D4, ELSET={name or 'EALL'}")
        for element in block.data:
            lines.append(f"{element_id}, {element[0]+1}, {element[1]+1}, "
                         f"{element[2]+1}, {element[3]+1}")
            element_id += 1
    for name, ids in (("FIX_A", fix_a), ("FIX_B", fix_b), ("LOAD", load)):
        lines.append(f"*NSET, NSET={name}")
        ids = ids + 1
        for start in range(0, len(ids), 10):
            lines.append(", ".join(str(int(value)) for value in ids[start:start + 10]))
    lines += [
        "*MATERIAL, NAME=STEEL", "*ELASTIC", "29000., 0.3",
        "*MATERIAL, NAME=PAD", "*ELASTIC", f"{e_pad}, 0.3",
        "*SOLID SECTION, ELSET=STEEL, MATERIAL=STEEL",
        "*SOLID SECTION, ELSET=PAD, MATERIAL=PAD",
        "*STEP", "*STATIC", "*BOUNDARY", "FIX_A, 1, 3", "FIX_B, 1, 3",
        "*CLOAD",
    ]
    for node in load:
        lines.append(f"{int(node)+1}, 2, {R/len(load):.9g}")
    lines += ["*NODE PRINT, NSET=FIX_A, TOTALS=ONLY", "RF",
              "*NODE PRINT, NSET=FIX_B, TOTALS=ONLY", "RF",
              "*NODE FILE", "U", "*EL FILE", "S", "*END STEP"]
    inp = out / f"model_{e_pad:g}.inp"
    inp.write_text("\n".join(lines) + "\n", encoding="ascii")
    return inp


def read_reactions(dat_path: Path) -> dict[str, float]:
    lines = dat_path.read_text(errors="ignore").splitlines()
    out = {}
    for index, line in enumerate(lines):
        if "for set FIX_A" in line:
            out["A"] = float(lines[index + 2].split()[1])
        if "for set FIX_B" in line:
            out["B"] = float(lines[index + 2].split()[1])
    return out


def find_ccx(explicit: str | None) -> str | None:
    for candidate in (explicit, os.environ.get("CCX"), shutil.which("ccx"),
                      shutil.which("ccx_static")):
        if candidate and Path(candidate).exists():
            return str(candidate)
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="benchmarks/ii_a_10/out_flex",
                        help="output directory")
    parser.add_argument("--hmax", type=float, default=0.18)
    parser.add_argument("--hmin", type=float, default=0.05)
    parser.add_argument("--ccx", default=None)
    parser.add_argument("--no-run", action="store_true")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    mesh_path = build_mesh(out, args.hmax, args.hmin)
    print(f"mesh: {mesh_path}")
    if args.no_run:
        for e_pad in PAD_MODULI:
            print(f"input: {write_input(mesh_path, out, e_pad)}")
        return 0
    ccx = find_ccx(args.ccx)
    if ccx is None:
        print("CalculiX ccx not found; use --ccx or set CCX. The mesh is ready.")
        return 2
    results = []
    for e_pad in PAD_MODULI:
        inp = write_input(mesh_path, out, e_pad)
        run = subprocess.run([ccx, inp.stem], cwd=out, capture_output=True, text=True)
        if run.returncode != 0:
            print(run.stdout[-2000:])
            return run.returncode
        reactions = read_reactions(out / f"model_{e_pad:g}.dat")
        total = abs(reactions["A"]) + abs(reactions["B"])
        share = {"A": abs(reactions["A"]) / total, "B": abs(reactions["B"]) / total}
        results.append({"pad_modulus_ksi": e_pad, "reactions_kip": reactions,
                        "share": share})
        print(f"E_pad = {e_pad:7.1f} ksi  A = {abs(reactions['A']):6.2f} kip  "
              f"B = {abs(reactions['B']):6.2f} kip  share_B = {share['B']:.3f}")
    (out / "results_flexible.json").write_text(
        json.dumps({"mesh": {"hmax": args.hmax, "hmin": args.hmin},
                    "results": results}, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
