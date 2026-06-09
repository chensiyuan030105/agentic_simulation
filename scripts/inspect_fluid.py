#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect a fluid simulation run bundle.")
    parser.add_argument("run_dir", type=Path, help="Fluid run directory under outputs/runs/.")
    return parser.parse_args()


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    args = parse_args()
    run_dir = args.run_dir.expanduser().resolve()
    manifest = _read_json(run_dir / "manifest.json")
    metrics = _read_json(run_dir / "metrics.json")

    with np.load(run_dir / "fields.npz") as bundle:
        shapes = {name: tuple(bundle[name].shape) for name in bundle.files}

    print(f"run_dir       : {run_dir}")
    print(f"run_name      : {manifest.get('run_name')}")
    print(f"created       : {manifest.get('created_at')}")
    print(f"frames        : {manifest.get('frames')}")
    print(f"fps           : {manifest.get('fps')}")
    print(f"grid          : {metrics.get('grid')}")
    print(f"free cells    : {metrics.get('free_cell_count')}")
    print(f"solid cells   : {metrics.get('solid_cell_count')}")
    print(f"mass range    : {metrics.get('mass_range'):.6e}")
    print(f"rel mass range: {metrics.get('mass_relative_range'):.6e}")
    print(f"max |height|  : {metrics.get('height_max_abs_over_time'):.6f}")
    print("arrays:")
    for name, shape in shapes.items():
        print(f"  {name:12s} {shape}")


if __name__ == "__main__":
    main()
