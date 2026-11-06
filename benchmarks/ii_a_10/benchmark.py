# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenConex contributors
"""Linear-elastic benchmark of the II.A-10 skewed double bent-plate connection.

The model is deliberately separate from the normative calculation in
``openconex.connections.shear.bent_plate``. It studies the global load split
between plates A and B and the nominal stress in the plates; it does not
replace the AISC checks.

Geometry (inches, kip, ksi):

* beam web W16x77, ``t_w = 0.455``, represented by a 12 in high, 5 in long
  stub;
* two bent plates, ``t = 3/8``, height ``8 1/2``, widths ``7 1/4`` and
  ``6 3/4``, welded legs ``4 7/16`` and ``3 9/16``;
* skew ``6:12`` (26.565°);
* three bolt rows at 3 in, with the rows 6.00 in apart (the statics lever
  arm of II.A-10);
* the bolts are represented by fixed circular patches of radius 3/4 in on
  the girder face of each plate. The girder web and the bolt shanks are not
  modelled, so the bolt group is rigid. This is the baseline model.

The beam end reaction (80 kip) is applied as a uniform shear flow along the
weld interface of each plate. The weld itself is a bonded interface; the
fillet is not modelled. The model is linear elastic and is intended for
global load distribution and nominal stresses, not for local weld-toe or
bearing stresses.

Run with the optional benchmark dependencies::

    pip install gmsh meshio numpy
    python benchmarks/ii_a_10/benchmark.py --ccx /path/to/ccx

If CalculiX is not available, ``--no-run`` writes the mesh and input deck.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
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
BOLT_R = 0.75
BOLT_ROW = 3.0
BOLT_Y = (-3.0, 0.0, 3.0)


def _local(points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Local beam coordinates (x along the beam, z across the beam web)."""
    ca, sa = math.cos(SKEW), math.sin(SKEW)
    return ca * points[:, 0] - sa * points[:, 2], sa * points[:, 0] + ca * points[:, 2]


def build_mesh(out: Path, hmax: float, hmin: float) -> Path:
    """Build the fused solid and write a Gmsh mesh."""
    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    gmsh.model.add("ii_a_10")
    occ = gmsh.model.occ
    beam = occ.addBox(0, -H_BEAM / 2, -TW / 2, L_BEAM, H_BEAM, TW)
    a_bolt = occ.addBox(0, -H_PLATE / 2, TW / 2, T_PLATE, H_PLATE, W_A)
    a_weld = occ.addBox(0, -H_PLATE / 2, TW / 2, LEG_A, H_PLATE, T_PLATE)
    b_bolt = occ.addBox(0, -H_PLATE / 2, -TW / 2 - W_B, T_PLATE, H_PLATE, W_B)
    b_weld = occ.addBox(0, -H_PLATE / 2, -TW / 2 - T_PLATE, LEG_B, H_PLATE, T_PLATE)
    for tag in (beam, a_weld, b_weld):
        occ.rotate([(3, tag)], 0, 0, 0, 0, 1, 0, SKEW)
    occ.synchronize()
    fused, _ = occ.fuse([(3, beam)], [(3, a_bolt), (3, a_weld), (3, b_bolt), (3, b_weld)])
    occ.synchronize()
    gmsh.model.addPhysicalGroup(3, [fused[0][1]], name="STEEL")
    gmsh.option.setNumber("Mesh.MeshSizeMax", hmax)
    gmsh.option.setNumber("Mesh.MeshSizeMin", hmin)
    gmsh.model.mesh.generate(3)
    path = out / "model.msh"
    gmsh.write(str(path))
    gmsh.finalize()
    return path


def _bolt_nodes(points: np.ndarray, sign: int) -> np.ndarray:
    z0 = sign * BOLT_ROW
    ids = []
    for y0 in BOLT_Y:
        d2 = (points[:, 0]) ** 2 + (points[:, 1] - y0) ** 2 + (points[:, 2] - z0) ** 2
        ids.append(np.where((d2 <= BOLT_R**2) & (np.abs(points[:, 0]) < 0.02))[0])
    return np.unique(np.concatenate(ids))


def _load_nodes(points: np.ndarray) -> np.ndarray:
    lx, lz = _local(points)
    return np.where(
        (np.abs(np.abs(lz) - TW / 2) < 0.03)
        & (lx >= -0.01)
        & (lx <= max(LEG_A, LEG_B))
        & (np.abs(points[:, 1]) <= H_PLATE / 2 + 0.01)
    )[0]


def write_input(mesh_path: Path, out: Path) -> tuple[Path, dict[str, int]]:
    """Write a CalculiX input deck with fixed bolt patches and a shear flow load."""
    mesh = meshio.read(mesh_path)
    blocks = mesh.cells
    tet_i = next(i for i, block in enumerate(blocks) if block.type == "tetra")
    tets = blocks[tet_i].data
    points = mesh.points
    sets = {
        "FIX_A": _bolt_nodes(points, +1),
        "FIX_B": _bolt_nodes(points, -1),
        "LOAD": _load_nodes(points),
    }
    if any(len(ids) == 0 for ids in sets.values()):
        raise RuntimeError("empty node set; check the mesh and the geometry")
    lines = ["*Heading", "II.A-10 benchmark, rigid bolt patches", "*NODE"]
    for i, point in enumerate(points, 1):
        lines.append(f"{i}, {point[0]:.9g}, {point[1]:.9g}, {point[2]:.9g}")
    lines.append("*ELEMENT, TYPE=C3D4, ELSET=EALL")
    for i, element in enumerate(tets, 1):
        lines.append(f"{i}, {element[0]+1}, {element[1]+1}, {element[2]+1}, {element[3]+1}")
    for name, ids in sets.items():
        lines.append(f"*NSET, NSET={name}")
        ids = ids + 1
        for start in range(0, len(ids), 10):
            lines.append(", ".join(str(int(value)) for value in ids[start:start + 10]))
    lines += [
        "*MATERIAL, NAME=STEEL",
        "*ELASTIC",
        "29000., 0.3",
        "*SOLID SECTION, ELSET=EALL, MATERIAL=STEEL",
        "*STEP",
        "*STATIC",
        "*BOUNDARY",
        "FIX_A, 1, 3",
        "FIX_B, 1, 3",
        "*CLOAD",
    ]
    load = sets["LOAD"]
    for node in load:
        lines.append(f"{int(node)+1}, 2, {R/len(load):.9g}")
    lines += [
        "*NODE PRINT, NSET=FIX_A, TOTALS=ONLY",
        "RF",
        "*NODE PRINT, NSET=FIX_B, TOTALS=ONLY",
        "RF",
        "*NODE FILE",
        "U",
        "*EL FILE",
        "S",
        "*END STEP",
    ]
    inp = out / "model.inp"
    inp.write_text("\n".join(lines) + "\n", encoding="ascii")
    return inp, {name: len(ids) for name, ids in sets.items()}


def find_ccx(explicit: str | None) -> str | None:
    for candidate in (explicit, os.environ.get("CCX"), shutil.which("ccx"),
                      shutil.which("ccx_static")):
        if candidate and Path(candidate).exists():
            return str(candidate)
    return None


def read_reactions(dat_path: Path) -> dict[str, float]:
    """Total vertical reaction of FIX_A and FIX_B from the CalculiX .dat file."""
    lines = dat_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    reactions: dict[str, float] = {}
    for index, line in enumerate(lines):
        match = re.search(r"for set (FIX_[AB])", line)
        if not match:
            continue
        for value_line in lines[index + 1:]:
            if value_line.strip():
                reactions[match.group(1)] = float(value_line.split()[1])
                break
    return reactions


def convert_frd(frd_path: Path) -> Path | None:
    """Convert .frd to .vtu when ccx2paraview is available (optional)."""
    tool = shutil.which("ccx2paraview")
    if tool is None:
        return None
    result = subprocess.run([tool, str(frd_path), "vtu"], capture_output=True, text=True)
    if result.returncode != 0:
        return None
    return frd_path.with_suffix(".vtu")


def stress_summary(vtu_path: Path, reactions: dict[str, float]) -> dict[str, float]:
    """Nominal shear and a representative interior von Mises value (optional)."""
    mesh = meshio.read(vtu_path)
    points = mesh.points
    mises = mesh.point_data["S_Mises"]
    summary: dict[str, float] = {}
    for name, sign, leg, _width in (("A", +1, LEG_A, W_A), ("B", -1, LEG_B, W_B)):
        force = abs(reactions.get(f"FIX_{name}", 0.0))
        summary[f"{name}_nominal_shear_ksi"] = force / (H_PLATE * T_PLATE)
        # Interior sample: middle of the welded leg, mid-height, away from corners.
        target_x = leg / 2 * math.cos(SKEW) + sign * (TW / 2 + T_PLATE / 2) * math.sin(SKEW)
        target_z = -leg / 2 * math.sin(SKEW) + sign * (TW / 2 + T_PLATE / 2) * math.cos(SKEW)
        distance = ((points[:, 0] - target_x) ** 2 + points[:, 1] ** 2
                    + (points[:, 2] - target_z) ** 2)
        summary[f"{name}_welded_leg_vm_ksi"] = float(mises[np.argmin(distance)])
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="benchmarks/ii_a_10/out", help="output directory")
    parser.add_argument("--hmax", type=float, default=0.30, help="maximum mesh size [in]")
    parser.add_argument("--hmin", type=float, default=0.08, help="minimum mesh size [in]")
    parser.add_argument("--ccx", default=None, help="path to the CalculiX ccx executable")
    parser.add_argument("--no-run", action="store_true", help="write the mesh and deck only")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    mesh_path = build_mesh(out, args.hmax, args.hmin)
    inp_path, node_counts = write_input(mesh_path, out)
    print(f"mesh: {mesh_path}")
    print(f"input: {inp_path}")
    print(f"node sets: {node_counts}")
    if args.no_run:
        return 0
    ccx = find_ccx(args.ccx)
    if ccx is None:
        print("CalculiX ccx not found; use --ccx or set CCX. The input deck is ready.")
        return 2
    result = subprocess.run([ccx, inp_path.stem], cwd=out, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout[-3000:])
        print(result.stderr[-2000:])
        return result.returncode
    dat_path = out / "model.dat"
    reactions = read_reactions(dat_path)
    total = sum(abs(value) for value in reactions.values())
    if total > 0:
        share = {name: abs(value) / total for name, value in reactions.items()}
    else:
        share = {}
    summary = {
        "mesh": {"hmax": args.hmax, "hmin": args.hmin},
        "node_counts": node_counts,
        "reactions_kip": reactions,
        "share": share,
        "nominal_statics_kip": {"FIX_A": 30.0, "FIX_B": 50.0},
    }
    vtu = convert_frd(out / "model.frd")
    if vtu is not None:
        summary["stress"] = stress_summary(vtu, reactions)
    (out / "results.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
